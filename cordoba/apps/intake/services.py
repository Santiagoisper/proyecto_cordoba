"""
Cliente de WhatsApp Cloud API (Meta Graph).
Todo el I/O externo del canal vive acá, con timeouts y errores explícitos.
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_BASE = 'https://graph.facebook.com/v21.0'
REQUEST_TIMEOUT = 20


class WhatsAppError(Exception):
    """Error de comunicación con la Cloud API."""


def verify_signature(app_secret: str, body: bytes, signature_header: str) -> bool:
    """
    Valida X-Hub-Signature-256 (sha256=<hex>) contra el cuerpo crudo.
    Comparación en tiempo constante.
    """
    if not signature_header or not signature_header.startswith('sha256='):
        return False
    expected = hmac.new(
        app_secret.encode('utf-8'), body, hashlib.sha256
    ).hexdigest()
    received = signature_header.split('=', 1)[1]
    return hmac.compare_digest(expected, received)


class WhatsAppClient:
    def __init__(self):
        self.access_token = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '') or ''
        self.phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '') or ''

    def _headers(self):
        return {'Authorization': f'Bearer {self.access_token}'}

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        """
        Descarga un media de WhatsApp en dos pasos:
        1. GET /{media_id} → URL efímera + mime_type
        2. GET url (con Bearer) → bytes
        Retorna (contenido, mime_type). Levanta WhatsAppError si falla.
        """
        try:
            meta_resp = requests.get(
                f'{GRAPH_BASE}/{media_id}',
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT,
            )
            meta_resp.raise_for_status()
            meta = meta_resp.json()
            url = meta.get('url')
            mime_type = meta.get('mime_type', 'application/octet-stream')
            if not url:
                raise WhatsAppError(f'Media {media_id} sin URL en la respuesta')

            file_resp = requests.get(
                url, headers=self._headers(), timeout=REQUEST_TIMEOUT,
            )
            file_resp.raise_for_status()
            return file_resp.content, mime_type
        except requests.RequestException as exc:
            raise WhatsAppError(f'Descarga de media {media_id} falló: {exc}') from exc

    def send_text(self, to_phone: str, body: str) -> None:
        """
        Respuesta de cortesía al remitente. Best effort:
        si falla solo se loguea, nunca corta el procesamiento del ticket.
        """
        if not self.access_token or not self.phone_number_id:
            return
        try:
            resp = requests.post(
                f'{GRAPH_BASE}/{self.phone_number_id}/messages',
                headers={**self._headers(), 'Content-Type': 'application/json'},
                json={
                    'messaging_product': 'whatsapp',
                    'to': to_phone,
                    'type': 'text',
                    'text': {'body': body},
                },
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning('No se pudo responder por WhatsApp a %s: %s', to_phone, exc)
