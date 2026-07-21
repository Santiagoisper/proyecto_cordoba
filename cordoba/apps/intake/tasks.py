"""
Procesamiento asíncrono de mensajes entrantes de WhatsApp.
El webhook responde 200 al instante y deja el trabajo pesado (descarga de
media + creación de ReceptionTicket) para esta tarea.
En desarrollo corre eager, igual que el OCR.
"""
import logging

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)

# Extensión sugerida por mime para nombrar el archivo entrante.
MIME_EXTENSIONS = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'application/pdf': '.pdf',
}

ACK_OK = (
    'Recibimos tu comprobante. Quedó en la bandeja de recepción para imputarlo '
    'a un paciente. ¡Gracias!'
)
ACK_UNAUTHORIZED = (
    'Este número no está autorizado para enviar comprobantes. '
    'Contactá al coordinador del site.'
)
ACK_NO_MEDIA = (
    'No recibimos ninguna foto ni PDF. Mandá el comprobante como imagen o '
    'documento, por favor.'
)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    name='intake.process_inbound_whatsapp_message',
)
def process_inbound_whatsapp_message(self, inbound_message_id: int):
    """
    1. Carga el InboundMessage.
    2. Verifica que el remitente sea un ChannelContact activo.
    3. Extrae el media (image/document); descarga los bytes.
    4. Crea un ReceptionTicket en el site del contacto (pending_assignment).
    5. Registra AuditLog y responde por WhatsApp.
    """
    from apps.expenses.models import ReceptionTicket, AuditLog
    from .models import ChannelContact, InboundMessage
    from .services import WhatsAppClient, WhatsAppError

    try:
        msg = InboundMessage.objects.select_related('reception_ticket').get(pk=inbound_message_id)
    except InboundMessage.DoesNotExist:
        logger.error("process_inbound_whatsapp: InboundMessage %s no existe", inbound_message_id)
        return

    if msg.status == 'processed':
        logger.info("InboundMessage %s ya procesado, se omite", inbound_message_id)
        return

    client = WhatsAppClient()

    contact = ChannelContact.objects.filter(
        channel='whatsapp', phone=msg.sender, is_active=True
    ).select_related('site').first()

    if not contact:
        msg.status = 'ignored'
        msg.error = 'Remitente no autorizado'
        msg.processed_at = timezone.now()
        msg.save(update_fields=['status', 'error', 'processed_at'])
        client.send_text(msg.sender, ACK_UNAUTHORIZED)
        logger.warning("WhatsApp: remitente no autorizado %s", msg.sender)
        return

    media = _extract_media(msg.payload)
    if not media:
        msg.status = 'ignored'
        msg.error = 'Mensaje sin media (imagen/documento)'
        msg.processed_at = timezone.now()
        msg.save(update_fields=['status', 'error', 'processed_at'])
        client.send_text(msg.sender, ACK_NO_MEDIA)
        return

    try:
        content, mime_type = client.download_media(media['id'])
    except WhatsAppError as exc:
        logger.error("WhatsApp: descarga falló para msg %s: %s", inbound_message_id, exc)
        msg.status = 'failed'
        msg.error = str(exc)
        msg.save(update_fields=['status', 'error'])
        raise self.retry(exc=exc)

    extension = MIME_EXTENSIONS.get(mime_type, '')
    filename = media.get('filename') or f'whatsapp_{msg.external_id[-12:]}{extension}'

    ticket = ReceptionTicket(
        original_filename=filename,
        file_size=len(content),
        mime_type=mime_type,
        notes=f'Recibido por WhatsApp de {contact.display_name or contact.phone}',
        status='pending_assignment',
        site=contact.site,
        uploaded_by=None,
    )
    ticket.file.save(filename, ContentFile(content), save=True)

    msg.reception_ticket = ticket
    msg.status = 'processed'
    msg.processed_at = timezone.now()
    msg.save(update_fields=['reception_ticket', 'status', 'processed_at'])

    AuditLog.objects.create(
        user=None,
        action='reception_uploaded',
        content_type='ReceptionTicket',
        object_id=ticket.pk,
        object_repr=str(ticket),
        details={
            'channel': 'whatsapp',
            'sender': msg.sender,
            'site': contact.site.code,
            'external_id': msg.external_id,
        },
    )

    client.send_text(msg.sender, ACK_OK)
    logger.info("WhatsApp: ReceptionTicket %s creado desde msg %s", ticket.pk, inbound_message_id)


def _extract_media(payload: dict) -> dict | None:
    """
    Devuelve {'id': ..., 'filename': ...} del primer media soportado en el
    payload de un mensaje de WhatsApp, o None si no hay imagen/documento.
    """
    if not isinstance(payload, dict):
        return None
    msg_type = payload.get('type')
    if msg_type == 'image':
        image = payload.get('image', {})
        if image.get('id'):
            return {'id': image['id'], 'filename': None}
    if msg_type == 'document':
        document = payload.get('document', {})
        if document.get('id'):
            return {'id': document['id'], 'filename': document.get('filename')}
    return None
