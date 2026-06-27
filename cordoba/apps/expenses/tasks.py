"""
Celery tasks para procesamiento OCR asíncrono.
En desarrollo (CELERY_TASK_ALWAYS_EAGER=True) las tareas se ejecutan de forma síncrona.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='expenses.process_ocr_for_ticket',
)
def process_ocr_for_ticket(self, ticket_file_id: int):
    """
    Procesa el OCR de un TicketFile.
    1. Llama al OCRService
    2. Guarda campos extraídos en Expense
    3. Actualiza estado a 'pending_review'
    4. Registra AuditLog
    """
    from django.utils import timezone
    from .models import TicketFile, AuditLog
    from .services import OCRService

    try:
        ticket = TicketFile.objects.select_related('expense', 'uploaded_by').get(pk=ticket_file_id)
    except TicketFile.DoesNotExist:
        logger.error("process_ocr_for_ticket: TicketFile %s no encontrado", ticket_file_id)
        return

    # Marcar como procesando
    ticket.ocr_status = 'processing'
    ticket.save(update_fields=['ocr_status'])

    expense = ticket.expense

    try:
        service = OCRService()
        result = service.process_file(ticket.file.path)

        # Guardar resultados en el modelo Expense
        expense.ocr_raw_data = result.raw_response
        expense.ocr_processed_at = timezone.now()

        # Campos extraídos por OCR (guardados en el modelo extendido via ocr_raw_data)
        # También pre-completar el gasto si la confianza es alta (>= 0.7)
        if result.amount is not None and result.confidence_amount >= 0.7:
            if expense.amount == 0 or expense.amount is None:
                expense.amount = result.amount

        if result.expense_date is not None and result.confidence_date >= 0.7:
            expense.expense_date = result.expense_date

        if result.vendor and result.confidence_vendor >= 0.7:
            if not expense.vendor:
                expense.vendor = result.vendor

        # Guardar metadatos OCR extendidos
        ocr_meta = {
            'extracted': {
                'amount': str(result.amount) if result.amount else None,
                'date': str(result.expense_date) if result.expense_date else None,
                'vendor': result.vendor,
                'cuit': result.cuit,
                'receipt_number': result.receipt_number,
            },
            'confidence': {
                'amount': result.confidence_amount,
                'date': result.confidence_date,
                'vendor': result.confidence_vendor,
                'cuit': result.confidence_cuit,
                'receipt': result.confidence_receipt,
            },
            'mock': result.raw_response.get('mock', False),
            'success': result.success,
        }
        expense.ocr_raw_data = ocr_meta
        expense.status = 'pending_review'
        expense.save(update_fields=[
            'ocr_raw_data', 'ocr_processed_at', 'status',
            'amount', 'expense_date', 'vendor',
        ])

        ticket.ocr_status = 'done'
        ticket.save(update_fields=['ocr_status'])

        AuditLog.objects.create(
            user=ticket.uploaded_by,
            action='ocr_completed',
            content_type='Expense',
            object_id=expense.pk,
            object_repr=str(expense),
            details={
                'ticket_file_id': ticket_file_id,
                'ocr_success': result.success,
                'mock_mode': result.raw_response.get('mock', False),
            },
        )
        logger.info("OCR completado para TicketFile %s (Expense %s)", ticket_file_id, expense.pk)

    except Exception as exc:
        logger.error(
            "OCR falló para TicketFile %s: %s",
            ticket_file_id, exc, exc_info=True
        )
        ticket.ocr_status = 'failed'
        ticket.save(update_fields=['ocr_status'])

        expense.status = 'pending_review'
        expense.save(update_fields=['status'])

        AuditLog.objects.create(
            user=ticket.uploaded_by,
            action='ocr_failed',
            content_type='Expense',
            object_id=expense.pk,
            object_repr=str(expense),
            details={'ticket_file_id': ticket_file_id, 'error': str(exc)},
        )

        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error("OCR: máximo de reintentos alcanzado para TicketFile %s", ticket_file_id)
