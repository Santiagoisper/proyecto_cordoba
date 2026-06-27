"""
Servicio OCR para Proyecto Córdoba.
Adaptador Veryfi con modo mock para desarrollo sin API key.
Veryfi se llama directamente por HTTP (sin SDK).
"""
import re
import json
import hmac
import base64
import hashlib
import logging
import requests
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

CUIT_REGEX = re.compile(r'\b(\d{2}-\d{8}-\d)\b')


@dataclass
class OCRResult:
    amount: Optional[Decimal] = None
    expense_date: Optional[date] = None
    vendor: Optional[str] = None
    cuit: Optional[str] = None
    receipt_number: Optional[str] = None

    confidence_amount: float = 0.0
    confidence_date: float = 0.0
    confidence_vendor: float = 0.0
    confidence_cuit: float = 0.0
    confidence_receipt: float = 0.0

    raw_response: dict = field(default_factory=dict)
    success: bool = True
    error_message: str = ''


class OCRService:
    """
    Servicio OCR. Usa Veryfi si las credenciales están configuradas,
    de lo contrario retorna un resultado mock para desarrollo.
    """

    VERYFI_BASE_URL = 'https://api.veryfi.com/api/v8'

    def __init__(self):
        self.client_id = getattr(settings, 'VERYFI_CLIENT_ID', '') or ''
        self.client_secret = getattr(settings, 'VERYFI_CLIENT_SECRET', '') or ''
        self.username = getattr(settings, 'VERYFI_USERNAME', '') or ''
        self.api_key = getattr(settings, 'VERYFI_API_KEY', '') or ''

    def has_credentials(self) -> bool:
        return all([self.client_id, self.client_secret, self.username, self.api_key])

    def process_file(self, file_path: str) -> OCRResult:
        """
        Procesa un archivo de ticket y retorna los datos extraídos.
        En modo mock (sin credenciales), retorna datos vacíos con baja confianza.
        Errores de API/red se propagan como excepciones para que Celery los reintente.
        """
        if not self.has_credentials():
            logger.info("OCR: sin credenciales Veryfi — modo mock activado")
            return self._mock_result()

        # Las excepciones de Veryfi API se propagan para que Celery haga retry
        return self._veryfi_process(file_path)

    def _veryfi_process(self, file_path: str) -> OCRResult:
        """Llama a la API de Veryfi y parsea la respuesta."""
        with open(file_path, 'rb') as f:
            file_data = f.read()

        file_b64 = base64.b64encode(file_data).decode('utf-8')
        import os
        filename = os.path.basename(file_path)

        payload = {
            'file_name': filename,
            'file_data': file_b64,
            'categories': ['Transport', 'Meals', 'Accommodation', 'Other'],
            'auto_delete': False,
        }

        headers = self._build_headers(json.dumps(payload))
        response = requests.post(
            f'{self.VERYFI_BASE_URL}/partner/documents/',
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return self._parse_veryfi_response(data)

    def _build_headers(self, payload_str: str) -> dict:
        timestamp = int(datetime.now().timestamp() * 1000)
        signature_data = f'timestamp:{timestamp}'
        signature = base64.b64encode(
            hmac.new(
                self.client_secret.encode('utf-8'),
                signature_data.encode('utf-8'),
                hashlib.sha256,
            ).digest()
        ).decode('utf-8')

        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'CLIENT-ID': self.client_id,
            'AUTHORIZATION': f'apikey {self.username}:{self.api_key}',
            'X-Veryfi-Request-Timestamp': str(timestamp),
            'X-Veryfi-Request-Signature': signature,
        }

    def _parse_veryfi_response(self, data: dict) -> OCRResult:
        """Extrae y normaliza campos desde la respuesta de Veryfi."""
        result = OCRResult(raw_response=data)

        # Monto total
        total = data.get('total')
        if total is not None:
            try:
                result.amount = Decimal(str(total))
                result.confidence_amount = 0.9
            except InvalidOperation:
                pass

        # Fecha del ticket
        date_str = data.get('date')
        if date_str:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    result.expense_date = datetime.strptime(date_str[:10], fmt).date()
                    result.confidence_date = 0.85
                    break
                except ValueError:
                    continue

        # Proveedor/comercio
        vendor = data.get('vendor', {})
        if isinstance(vendor, dict):
            result.vendor = vendor.get('name', '')
        elif isinstance(vendor, str):
            result.vendor = vendor
        if result.vendor:
            result.confidence_vendor = 0.8

        # CUIT argentino (buscar en los datos crudos)
        raw_text = json.dumps(data)
        cuit_match = CUIT_REGEX.search(raw_text)
        if cuit_match:
            result.cuit = cuit_match.group(1)
            result.confidence_cuit = 0.75

        # Número de comprobante
        invoice_number = data.get('invoice_number') or data.get('reference_number', '')
        if invoice_number:
            result.receipt_number = str(invoice_number)
            result.confidence_receipt = 0.7

        result.success = True
        return result

    def _mock_result(self) -> OCRResult:
        """
        Resultado mock para desarrollo sin credenciales.
        Retorna campos vacíos con confianza 0 para que el asistente los complete.
        """
        return OCRResult(
            amount=None,
            expense_date=None,
            vendor='',
            cuit='',
            receipt_number='',
            confidence_amount=0.0,
            confidence_date=0.0,
            confidence_vendor=0.0,
            confidence_cuit=0.0,
            confidence_receipt=0.0,
            raw_response={'mock': True, 'message': 'Modo desarrollo — sin credenciales Veryfi'},
            success=True,
        )
