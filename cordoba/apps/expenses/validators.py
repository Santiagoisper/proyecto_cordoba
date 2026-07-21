"""
Validación server-side de archivos de tickets.
El atributo `accept` del input HTML es solo una sugerencia del navegador:
la validación real ocurre acá.
"""
from django.core.exceptions import ValidationError

MAX_TICKET_SIZE_MB = 15
MAX_TICKET_SIZE_BYTES = MAX_TICKET_SIZE_MB * 1024 * 1024

ALLOWED_TICKET_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/heic',
    'image/heif',
    'image/avif',
    'application/pdf',
}

ALLOWED_TICKET_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.avif', '.pdf',
}


def validate_ticket_file(uploaded_file):
    """
    Valida tamaño y tipo del archivo de ticket.
    Usable como validator de FileField o llamable desde clean_<field>.
    """
    if uploaded_file.size and uploaded_file.size > MAX_TICKET_SIZE_BYTES:
        raise ValidationError(
            f'El archivo pesa {uploaded_file.size / (1024 * 1024):.1f} MB '
            f'y el máximo permitido es {MAX_TICKET_SIZE_MB} MB. '
            'Sacá la foto en calidad normal o comprimila.'
        )

    content_type = getattr(uploaded_file, 'content_type', '') or ''
    name = (uploaded_file.name or '').lower()
    extension = '.' + name.rsplit('.', 1)[-1] if '.' in name else ''

    if content_type not in ALLOWED_TICKET_CONTENT_TYPES and extension not in ALLOWED_TICKET_EXTENSIONS:
        raise ValidationError(
            'Formato no soportado. Aceptamos fotos (JPG, PNG, WEBP, HEIC, AVIF) o PDF.'
        )
