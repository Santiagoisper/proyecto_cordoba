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
    1. Llama al OCRService (propaga excepciones → Celery hace retry)
    2. Guarda campos extraídos en Expense
    3. Actualiza estado a 'pending_review'
    4. Registra AuditLog con 'ocr_completed' o 'ocr_failed'
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
        # process_file() propaga excepciones de API/red → Celery retry automático
        result = service.process_file(ticket.file.path)

        # Guardar metadatos OCR en ocr_raw_data
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
            'success': True,
        }
        expense.ocr_raw_data = ocr_meta
        expense.ocr_processed_at = timezone.now()

        # Pre-completar campos de alta confianza (>= 0.7)
        if result.amount is not None and result.confidence_amount >= 0.7:
            if not expense.amount or expense.amount == 0:
                expense.amount = result.amount
        if result.expense_date is not None and result.confidence_date >= 0.7:
            expense.expense_date = result.expense_date
        if result.vendor and result.confidence_vendor >= 0.7:
            if not expense.vendor:
                expense.vendor = result.vendor

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
                'mock_mode': result.raw_response.get('mock', False),
                'fields_pre_filled': {
                    'amount': result.confidence_amount >= 0.7,
                    'date': result.confidence_date >= 0.7,
                    'vendor': result.confidence_vendor >= 0.7,
                },
            },
        )
        logger.info("OCR completado para TicketFile %s (Expense %s)", ticket_file_id, expense.pk)

    except Exception as exc:
        logger.error(
            "OCR falló para TicketFile %s (intento %s/%s): %s",
            ticket_file_id, self.request.retries + 1, self.max_retries + 1, exc,
            exc_info=True,
        )

        is_final_attempt = self.request.retries >= self.max_retries

        if is_final_attempt:
            # Máximo de reintentos alcanzado → marcar como fallido definitivamente
            ticket.ocr_status = 'failed'
            ticket.save(update_fields=['ocr_status'])

            expense.ocr_raw_data = {'success': False, 'error': str(exc), 'mock': False}
            expense.status = 'pending_review'
            expense.save(update_fields=['ocr_raw_data', 'status'])

            AuditLog.objects.create(
                user=ticket.uploaded_by,
                action='ocr_failed',
                content_type='Expense',
                object_id=expense.pk,
                object_repr=str(expense),
                details={
                    'ticket_file_id': ticket_file_id,
                    'error': str(exc),
                    'retries_exhausted': True,
                },
            )
            logger.error("OCR: máximo de reintentos alcanzado para TicketFile %s", ticket_file_id)
        else:
            # Reintento disponible → propagar para que Celery espere y reintente
            raise self.retry(exc=exc)
