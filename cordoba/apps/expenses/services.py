"""
Servicios para Proyecto Córdoba.
- OCRService: adaptador Veryfi con modo mock.
- ExpenseValidationService: validaciones automáticas de gastos.
- close_period: cierre de período de rendición con trazabilidad completa.
"""
import re
import json
import hmac
import base64
import hashlib
import logging
import requests
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Optional, List

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

CUIT_REGEX = re.compile(r'\b(\d{2}-\d{8}-\d)\b')


# ─── OCR ──────────────────────────────────────────────────────────────────────

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
    Acepta bytes del archivo para ser compatible con almacenamiento local y S3.
    """

    VERYFI_BASE_URL = 'https://api.veryfi.com/api/v8'

    def __init__(self):
        self.client_id = getattr(settings, 'VERYFI_CLIENT_ID', '') or ''
        self.client_secret = getattr(settings, 'VERYFI_CLIENT_SECRET', '') or ''
        self.username = getattr(settings, 'VERYFI_USERNAME', '') or ''
        self.api_key = getattr(settings, 'VERYFI_API_KEY', '') or ''

    def has_credentials(self) -> bool:
        return all([self.client_id, self.client_secret, self.username, self.api_key])

    def process_bytes(self, file_bytes: bytes, filename: str = 'ticket') -> OCRResult:
        if not self.has_credentials():
            logger.info("OCR: sin credenciales Veryfi — modo mock activado")
            return self._mock_result()
        return self._veryfi_process(file_bytes, filename)

    def _veryfi_process(self, file_bytes: bytes, filename: str) -> OCRResult:
        file_b64 = base64.b64encode(file_bytes).decode('utf-8')
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
        return self._parse_veryfi_response(response.json())

    def _normalize_amount(self, amount_str: str) -> str:
        """
        Normaliza números en formato argentino o americano a formato Python.
        - Argentino: 40.200,50 → 40200.50 (punto=miles, coma=decimal)
        - Americano: 40,200.50 → 40200.50 (coma=miles, punto=decimal)
        - Sin separadores: 40 → 40
        - Veryfi corrupto: 40.200 → 40200 (detecta que es miles, no decimal)

        Detecta automáticamente basado en la cantidad de dígitos después del separador.
        Si hay 3 dígitos después del último separador → es separador de miles (siempre).
        Si hay ≤2 dígitos → es separador decimal.
        """
        # Remover espacios
        amount_str = amount_str.strip()

        # Si no tiene separadores, devolver como está
        if ',' not in amount_str and '.' not in amount_str:
            return amount_str

        # Contar dígitos después del último separador
        last_sep_idx = max(amount_str.rfind(','), amount_str.rfind('.'))
        if last_sep_idx == -1:
            return amount_str

        digits_after_sep = sum(1 for c in amount_str[last_sep_idx+1:] if c.isdigit())
        last_sep = amount_str[last_sep_idx]

        # Si hay exactamente 3 dígitos después del último separador → es separador de miles
        # Ej: 40.200 o 1,000 o 1000 siempre tiene 3 dígitos de miles
        if digits_after_sep == 3:
            # Es separador de miles: remover todos los separadores de miles
            normalized = amount_str.replace(last_sep, '').replace('.', '').replace(',', '')
            # Si quedó un decimal, protegerlo
            if '.' not in normalized:
                return normalized
            return normalized

        # Si ≤2 dígitos después del último separador → es decimal
        if digits_after_sep <= 2:
            # El último separador es el decimal, todos los otros son miles
            if last_sep == ',':
                # Argentino: 40.200,50 → 40200.50
                normalized = amount_str.replace('.', '').replace(',', '.')
                return normalized
            elif last_sep == '.':
                # Americano: 40,200.50 → 40200.50
                normalized = amount_str.replace(',', '')
                return normalized

        return amount_str

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
        result = OCRResult(raw_response=data)
        total = data.get('total')
        if total is not None:
            try:
                # Normalizar número: detectar si es formato argentino (punto=miles, coma=decimal)
                # o formato americano (punto=decimal, coma=miles)
                total_str = str(total).strip()
                normalized = self._normalize_amount(total_str)
                result.amount = Decimal(normalized)
                result.confidence_amount = 0.9
            except InvalidOperation:
                pass
        date_str = data.get('date')
        if date_str:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y'):
                try:
                    result.expense_date = datetime.strptime(date_str[:10], fmt).date()
                    result.confidence_date = 0.85
                    break
                except ValueError:
                    continue
        vendor = data.get('vendor', {})
        if isinstance(vendor, dict):
            result.vendor = vendor.get('name', '')
        elif isinstance(vendor, str):
            result.vendor = vendor
        if result.vendor:
            result.confidence_vendor = 0.8
        raw_text = json.dumps(data)
        cuit_match = CUIT_REGEX.search(raw_text)
        if cuit_match:
            result.cuit = cuit_match.group(1)
            result.confidence_cuit = 0.75
        invoice_number = data.get('invoice_number') or data.get('reference_number', '')
        if invoice_number:
            result.receipt_number = str(invoice_number)
            result.confidence_receipt = 0.7
        result.success = True
        return result

    def _mock_result(self) -> OCRResult:
        return OCRResult(
            raw_response={'mock': True, 'message': 'Modo desarrollo — sin credenciales Veryfi'},
            success=True,
        )


# ─── Validaciones automáticas ─────────────────────────────────────────────────

@dataclass
class ValidationAlert:
    level: str      # 'error' | 'warning'
    code: str       # identificador único de la alerta
    message: str    # mensaje legible para el coordinador


class ExpenseValidationService:
    """
    Valida un gasto contra las reglas de negocio del protocolo.
    Retorna una lista de ValidationAlert (puede estar vacía si todo está bien).
    """

    def validate(self, expense) -> List[ValidationAlert]:
        alerts: List[ValidationAlert] = []
        alerts.extend(self._check_date_window(expense))
        alerts.extend(self._check_amount_cap(expense))
        alerts.extend(self._check_budget_usd(expense))
        alerts.extend(self._check_duplicate(expense))
        return alerts

    def _check_date_window(self, expense) -> List[ValidationAlert]:
        """Valida que la fecha del ticket esté dentro de la ventana de la visita."""
        try:
            window_start = expense.visit.get_ticket_window_start()
            window_end = expense.visit.get_ticket_window_end()
            exp_date = expense.expense_date
            if exp_date < window_start or exp_date > window_end:
                return [ValidationAlert(
                    level='warning',
                    code='date_out_of_window',
                    message=(
                        f'Fecha fuera de ventana de visita: '
                        f'{exp_date:%d/%m/%Y} (ventana: {window_start:%d/%m/%Y} – {window_end:%d/%m/%Y})'
                    ),
                )]
        except Exception:
            pass
        return []

    def _check_amount_cap(self, expense) -> List[ValidationAlert]:
        """Valida que el monto no supere el tope diario de la categoría."""
        try:
            protocol = expense.visit.patient.protocol
            cap = None
            if expense.category == 'meals':
                cap = protocol.max_daily_meals
            elif expense.category == 'transport':
                cap = protocol.max_daily_transport
            elif expense.category == 'accommodation':
                cap = protocol.max_daily_accommodation

            if cap is not None and expense.amount > cap:
                return [ValidationAlert(
                    level='error',
                    code='amount_exceeds_cap',
                    message=(
                        f'Monto supera el tope diario: '
                        f'${expense.amount:.2f} > ${cap:.2f} ({expense.get_category_display()})'
                    ),
                )]
        except Exception:
            pass
        return []

    def _check_duplicate(self, expense) -> List[ValidationAlert]:
        """
        Detecta posibles duplicados: mismo gasto (visita, categoría, fecha, monto)
        excluyendo rechazados y el propio gasto.
        """
        try:
            from .models import Expense
            duplicates = Expense.objects.filter(
                visit=expense.visit,
                category=expense.category,
                expense_date=expense.expense_date,
                amount=expense.amount,
            ).exclude(
                pk=expense.pk,
            ).exclude(
                status='rejected',
            )
            if duplicates.exists():
                return [ValidationAlert(
                    level='error',
                    code='possible_duplicate',
                    message=(
                        f'Posible duplicado: ya existe un gasto de '
                        f'${expense.amount:.2f} ({expense.get_category_display()}) '
                        f'para esta visita y fecha.'
                    ),
                )]
        except Exception:
            pass
        return []

    def _check_budget_usd(self, expense) -> List[ValidationAlert]:
        """Compara el gasto convertido a USD contra el budget del protocolo."""
        try:
            from .models import ProtocolBudgetItem
            budget = (
                ProtocolBudgetItem.objects
                .filter(
                    protocol=expense.visit.patient.protocol,
                    category=expense.category,
                )
                .filter(visit_type=expense.visit.visit_type)
                .first()
            )
            if not budget:
                budget = (
                    ProtocolBudgetItem.objects
                    .filter(
                        protocol=expense.visit.patient.protocol,
                        category=expense.category,
                        visit_type__isnull=True,
                    )
                    .first()
                )
            if not budget:
                return []

            amount_usd = expense.amount_usd
            if amount_usd is None:
                amount_usd = calculate_amount_usd(
                    expense.amount, expense.currency, expense.exchange_rate_to_usd
                )
            if amount_usd is None:
                return [ValidationAlert(
                    level='warning',
                    code='missing_exchange_rate',
                    message=(
                        f'Hay budget en USD para {expense.get_category_display()}, '
                        'pero falta el tipo de cambio para comparar el ticket.'
                    ),
                )]
            if amount_usd > budget.amount_usd:
                return [ValidationAlert(
                    level='error',
                    code='budget_exceeded_usd',
                    message=(
                        f'Gasto fuera de budget: USD {amount_usd:.2f} > '
                        f'USD {budget.amount_usd:.2f} ({expense.get_category_display()})'
                    ),
                )]
        except Exception:
            pass
        return []


def calculate_amount_usd(amount, currency: str, exchange_rate_to_usd=None):
    """Convierte el monto del ticket a USD si hay datos suficientes."""
    if amount is None:
        return None
    try:
        value = Decimal(str(amount))
        if currency == 'USD':
            return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if not exchange_rate_to_usd:
            return None
        rate = Decimal(str(exchange_rate_to_usd))
        if rate <= 0:
            return None
        return (value / rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ZeroDivisionError, TypeError, ValueError):
        return None


# ─── Cierre de período ────────────────────────────────────────────────────────

def close_period(period_id: int, user) -> 'ExpensePeriod':
    """
    Cierra un período de rendición de forma atómica.

    Reglas de negocio:
    - El período debe estar en estado 'open'.
    - No puede haber gastos en estado 'pending_review' dentro del período.
    - Todos los gastos 'approved' del período pasan a 'settled'.
    - Se crean AuditLog inmutables por cada gasto y para el período en sí.
    - closed_by / closed_at se registran en el período.

    Levanta ValueError con mensaje legible si no se cumplen las precondiciones.
    """
    from .models import ExpensePeriod, Expense, AuditLog

    with transaction.atomic():
        period = ExpensePeriod.objects.select_for_update().get(pk=period_id)

        if period.status != 'open':
            raise ValueError(
                f"El período «{period.name}» ya está {period.get_status_display().lower()} "
                f"y no puede cerrarse nuevamente."
            )

        pending_count = period.expenses.filter(status='pending_review').count()
        if pending_count > 0:
            raise ValueError(
                f"No se puede cerrar: hay {pending_count} gasto(s) pendiente(s) de revisión "
                f"dentro del período. Aprobá o rechazá todos los gastos antes de cerrar."
            )

        approved_expenses = list(
            period.expenses.filter(status='approved').select_related('visit__patient')
        )

        if approved_expenses:
            AuditLog.objects.bulk_create([
                AuditLog(
                    user=user,
                    action='period_closed',
                    content_type='Expense',
                    object_id=exp.pk,
                    object_repr=str(exp),
                    details={
                        'period_id': period.pk,
                        'period_name': period.name,
                        'prev_status': 'approved',
                        'new_status': 'settled',
                    },
                )
                for exp in approved_expenses
            ])

            expense_ids = [e.pk for e in approved_expenses]
            Expense.objects.filter(pk__in=expense_ids).update(status='settled')

        period.status = 'closed'
        period.closed_by = user
        period.closed_at = timezone.now()
        period.save(update_fields=['status', 'closed_by', 'closed_at'])

        AuditLog.objects.create(
            user=user,
            action='period_closed',
            content_type='ExpensePeriod',
            object_id=period.pk,
            object_repr=str(period),
            details={
                'expenses_settled': len(approved_expenses),
                'protocol': period.protocol.code,
                'date_from': str(period.date_from),
                'date_to': str(period.date_to),
            },
        )

        logger.info(
            "Período #%s «%s» cerrado por %s. Gastos liquidados: %d",
            period.pk, period.name, user, len(approved_expenses),
        )
        return period
