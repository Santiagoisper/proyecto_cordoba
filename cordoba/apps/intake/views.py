"""
Webhook de WhatsApp Cloud API.
GET  → verificación del webhook (hub.challenge) al configurarlo en Meta.
POST → recepción de mensajes. Valida firma, deduplica y encola procesamiento.
"""
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import InboundMessage
from .services import verify_signature
from .tasks import process_inbound_whatsapp_message

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def whatsapp_webhook(request):
    if request.method == 'GET':
        return _handle_verification(request)
    return _handle_event(request)


def _handle_verification(request):
    """Meta llama con hub.mode=subscribe y el verify_token que configuramos."""
    mode = request.GET.get('hub.mode')
    token = request.GET.get('hub.verify_token')
    challenge = request.GET.get('hub.challenge', '')

    expected = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', '') or ''
    if mode == 'subscribe' and token and expected and token == expected:
        return HttpResponse(challenge, content_type='text/plain')
    logger.warning("WhatsApp webhook: verificación fallida (mode=%s)", mode)
    return HttpResponseForbidden('Verificación fallida')


def _handle_event(request):
    app_secret = getattr(settings, 'WHATSAPP_APP_SECRET', '') or ''
    signature = request.headers.get('X-Hub-Signature-256', '')

    # Si hay app_secret configurado, la firma es obligatoria.
    if app_secret and not verify_signature(app_secret, request.body, signature):
        logger.warning("WhatsApp webhook: firma inválida")
        return HttpResponseForbidden('Firma inválida')

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    for message, sender in _iter_messages(data):
        external_id = message.get('id')
        if not external_id:
            continue

        inbound, created = InboundMessage.objects.get_or_create(
            external_id=external_id,
            defaults={
                'channel': 'whatsapp',
                'sender': sender,
                'message_type': message.get('type', ''),
                'payload': message,
            },
        )
        if created:
            try:
                process_inbound_whatsapp_message.delay(inbound.pk)
            except Exception as exc:  # broker caído: no perder el 200 a Meta
                logger.error("No se pudo encolar procesamiento WhatsApp: %s", exc)

    # WhatsApp exige 200 rápido; el trabajo real corre asíncrono.
    return JsonResponse({'status': 'ok'})


def _iter_messages(data: dict):
    """
    Recorre el payload de WhatsApp y produce (message, sender_phone).
    Estructura: entry[].changes[].value.messages[].
    """
    if not isinstance(data, dict) or data.get('object') != 'whatsapp_business_account':
        return
    for entry in data.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            for message in value.get('messages', []):
                sender = message.get('from', '')
                yield message, sender
