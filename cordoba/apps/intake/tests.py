"""
Tests del canal de ingesta por WhatsApp.
No tocan la red: WhatsAppClient.download_media y send_text se mockean.
"""
import json
import hashlib
import hmac
from unittest import mock

from django.test import TestCase, Client, override_settings
from django.urls import reverse

from apps.protocols.models import Site
from apps.expenses.models import ReceptionTicket, AuditLog
from .models import ChannelContact, InboundMessage
from .services import verify_signature


def _wa_payload(external_id='wamid.TEST1', sender='5493511234567', media_type='image', media_id='MEDIA1'):
    message = {'id': external_id, 'from': sender, 'type': media_type}
    if media_type == 'image':
        message['image'] = {'id': media_id, 'mime_type': 'image/jpeg'}
    elif media_type == 'document':
        message['document'] = {'id': media_id, 'mime_type': 'application/pdf', 'filename': 'factura.pdf'}
    elif media_type == 'text':
        message['text'] = {'body': 'hola'}
    return {
        'object': 'whatsapp_business_account',
        'entry': [{'changes': [{'value': {'messages': [message]}}]}],
    }


class SignatureTests(TestCase):
    def test_valid_signature(self):
        secret = 'topsecret'
        body = b'{"a":1}'
        sig = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_signature(secret, body, sig))

    def test_invalid_signature(self):
        self.assertFalse(verify_signature('s', b'body', 'sha256=deadbeef'))

    def test_missing_signature(self):
        self.assertFalse(verify_signature('s', b'body', ''))


@override_settings(WHATSAPP_VERIFY_TOKEN='verify-me', WHATSAPP_APP_SECRET='')
class WebhookVerificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('intake:whatsapp_webhook')

    def test_verification_success(self):
        resp = self.client.get(self.url, {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'verify-me',
            'hub.challenge': '31337',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'31337')

    def test_verification_wrong_token(self):
        resp = self.client.get(self.url, {
            'hub.mode': 'subscribe',
            'hub.verify_token': 'wrong',
            'hub.challenge': '31337',
        })
        self.assertEqual(resp.status_code, 403)


@override_settings(WHATSAPP_APP_SECRET='', WHATSAPP_VERIFY_TOKEN='v')
class WebhookEventTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('intake:whatsapp_webhook')
        self.site = Site.objects.create(code='CINME-01', name='Site Uno')
        self.contact = ChannelContact.objects.create(
            phone='5493511234567', display_name='Asistente Ana', site=self.site,
        )

    def _post(self, payload):
        return self.client.post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )

    @mock.patch('apps.intake.services.WhatsAppClient')
    def test_authorized_image_creates_reception_ticket(self, MockClient):
        instance = MockClient.return_value
        instance.download_media.return_value = (b'\xff\xd8\xff-jpeg-bytes', 'image/jpeg')

        resp = self._post(_wa_payload())
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(ReceptionTicket.objects.count(), 1)
        ticket = ReceptionTicket.objects.first()
        self.assertEqual(ticket.site, self.site)
        self.assertEqual(ticket.status, 'pending_assignment')
        self.assertEqual(ticket.mime_type, 'image/jpeg')

        msg = InboundMessage.objects.get(external_id='wamid.TEST1')
        self.assertEqual(msg.status, 'processed')
        self.assertEqual(msg.reception_ticket_id, ticket.pk)
        self.assertTrue(
            AuditLog.objects.filter(action='reception_uploaded', object_id=ticket.pk).exists()
        )

    @mock.patch('apps.intake.services.WhatsAppClient')
    def test_unauthorized_sender_ignored(self, MockClient):
        payload = _wa_payload(sender='5490000000000')
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ReceptionTicket.objects.count(), 0)
        msg = InboundMessage.objects.get(external_id='wamid.TEST1')
        self.assertEqual(msg.status, 'ignored')

    @mock.patch('apps.intake.services.WhatsAppClient')
    def test_text_message_ignored(self, MockClient):
        resp = self._post(_wa_payload(media_type='text'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ReceptionTicket.objects.count(), 0)
        self.assertEqual(InboundMessage.objects.get(external_id='wamid.TEST1').status, 'ignored')

    @mock.patch('apps.intake.services.WhatsAppClient')
    def test_duplicate_message_processed_once(self, MockClient):
        instance = MockClient.return_value
        instance.download_media.return_value = (b'jpeg', 'image/jpeg')
        self._post(_wa_payload())
        self._post(_wa_payload())  # mismo external_id
        self.assertEqual(InboundMessage.objects.count(), 1)
        self.assertEqual(ReceptionTicket.objects.count(), 1)

    @override_settings(WHATSAPP_APP_SECRET='sekret')
    @mock.patch('apps.intake.services.WhatsAppClient')
    def test_bad_signature_rejected(self, MockClient):
        resp = self.client.post(
            self.url,
            data=json.dumps(_wa_payload()),
            content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256='sha256=bad',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(InboundMessage.objects.count(), 0)

    @override_settings(WHATSAPP_APP_SECRET='sekret')
    @mock.patch('apps.intake.services.WhatsAppClient')
    def test_good_signature_accepted(self, MockClient):
        instance = MockClient.return_value
        instance.download_media.return_value = (b'jpeg', 'image/jpeg')
        body = json.dumps(_wa_payload()).encode()
        sig = 'sha256=' + hmac.new(b'sekret', body, hashlib.sha256).hexdigest()
        resp = self.client.post(
            self.url, data=body, content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=sig,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ReceptionTicket.objects.count(), 1)
