"""
Generadores de PDF y Excel para Proyecto Córdoba.
PDF: xhtml2pdf (puro Python, sin libpango/cairo).
Excel: openpyxl.
Principio de privacidad: solo código de paciente, nunca nombre real.
"""
import base64
import logging
from io import BytesIO
from decimal import Decimal
from datetime import datetime
from collections import defaultdict

from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

REPORT_STATUSES = ('approved', 'settled', 'exported')
CATEGORY_LABELS = {
    'transport': 'Transporte',
    'meals': 'Comidas',
    'accommodation': 'Alojamiento',
    'other': 'Otro',
}


def _ticket_to_base64(ticket) -> str | None:
    """Convierte el archivo del ticket a data URI base64 para incrustar en el PDF."""
    if not ticket or not ticket.file:
        return None
    try:
        mime = ticket.mime_type or 'image/jpeg'
        if 'pdf' in mime:
            return None  # No se incrusta PDF en el PDF
        with ticket.file.open('rb') as f:
            data = f.read()
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception as e:
        logger.warning("No se pudo convertir ticket a base64: %s", e)
        return None


def _calc_totals(expenses) -> dict:
    """Calcula totales por categoría y total general."""
    by_category = defaultdict(Decimal)
    for exp in expenses:
        by_category[exp.category] += exp.amount
    total = sum(by_category.values())
    return {
        'by_category': {
            cat: {'label': CATEGORY_LABELS.get(cat, cat), 'amount': amt}
            for cat, amt in sorted(by_category.items())
        },
        'total': total,
    }


def _render_pdf(template_name: str, context: dict) -> bytes:
    """Renderiza un template HTML a PDF usando xhtml2pdf."""
    from xhtml2pdf import pisa

    html = render_to_string(template_name, context)
    buffer = BytesIO()
    status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8')
    if status.err:
        raise RuntimeError(f"Error xhtml2pdf ({status.err}): verifica el template {template_name}")
    return buffer.getvalue()


def _mark_expenses_exported(expenses, user, report_type: str, report_label: str):
    """
    Marca los gastos como 'exported' y crea un AuditLog por cada uno.
    Idempotente: no crea duplicados si el gasto ya estaba exported.
    """
    from apps.expenses.models import AuditLog

    expense_ids = [e.pk for e in expenses]
    AuditLog.objects.bulk_create([
        AuditLog(
            user=user,
            action='exported',
            content_type='Expense',
            object_id=exp.pk,
            object_repr=str(exp),
            details={
                'report_type': report_type,
                'report_label': report_label,
                'prev_status': exp.status,
            },
        )
        for exp in expenses
    ])
    # Actualizar status en bulk
    from apps.expenses.models import Expense
    Expense.objects.filter(pk__in=expense_ids, status='approved').update(status='exported')


# ─── PDF por paciente ──────────────────────────────────────────────────────────

def generate_patient_pdf(patient, period, requested_by) -> bytes:
    """
    Genera el PDF de rendición de un paciente en un período.
    Solo incluye gastos con status en REPORT_STATUSES.
    Incrusta miniaturas de tickets como base64.
    Marca los gastos como 'exported' y crea AuditLog.
    """
    from apps.expenses.models import Expense

    expenses = list(
        Expense.objects.filter(
            visit__patient=patient,
            expense_date__gte=period.date_from,
            expense_date__lte=period.date_to,
            status__in=REPORT_STATUSES,
        ).select_related(
            'visit__visit_type',
        ).prefetch_related('ticket_files')
        .order_by('expense_date', 'visit__visit_type__order')
    )

    if not expenses:
        raise ValueError(
            f"No hay gastos aprobados para {patient.patient_code} en el período {period.name}."
        )

    # Preparar datos de gastos con imagen base64
    expense_rows = []
    for exp in expenses:
        ticket = exp.ticket_files.first()
        expense_rows.append({
            'expense': exp,
            'ticket_b64': _ticket_to_base64(ticket),
            'ticket_filename': ticket.original_filename if ticket else '',
        })

    totals = _calc_totals(expenses)

    context = {
        'patient': patient,
        'period': period,
        'protocol': patient.protocol,
        'expenses': expense_rows,
        'totals': totals,
        'generated_by': requested_by,
        'generated_at': timezone.now(),
        'report_type': 'patient',
    }

    pdf_bytes = _render_pdf('reports/pdf_patient.html', context)
    report_label = f"PDF paciente {patient.patient_code} / {patient.protocol.code} / {period.name}"
    _mark_expenses_exported(expenses, requested_by, 'patient_pdf', report_label)

    return pdf_bytes


# ─── PDF consolidado del site ─────────────────────────────────────────────────

def generate_site_pdf(protocol, period, requested_by) -> bytes:
    """
    Genera el PDF consolidado de todos los pacientes del protocolo en el período.
    Primera página: resumen ejecutivo con totales.
    Sección por paciente: detalle de gastos.
    """
    from apps.patients.models import Patient
    from apps.expenses.models import Expense

    patients = Patient.objects.filter(
        protocol=protocol,
        is_active=True,
    ).order_by('patient_code')

    all_expenses = []
    patient_sections = []

    for patient in patients:
        expenses = list(
            Expense.objects.filter(
                visit__patient=patient,
                expense_date__gte=period.date_from,
                expense_date__lte=period.date_to,
                status__in=REPORT_STATUSES,
            ).select_related('visit__visit_type')
            .prefetch_related('ticket_files')
            .order_by('expense_date')
        )
        if not expenses:
            continue

        expense_rows = []
        for exp in expenses:
            ticket = exp.ticket_files.first()
            expense_rows.append({
                'expense': exp,
                'ticket_b64': _ticket_to_base64(ticket),
                'ticket_filename': ticket.original_filename if ticket else '',
            })

        totals = _calc_totals(expenses)
        patient_sections.append({
            'patient': patient,
            'expenses': expense_rows,
            'totals': totals,
        })
        all_expenses.extend(expenses)

    if not all_expenses:
        raise ValueError(
            f"No hay gastos aprobados para ningún paciente de {protocol.code} en {period.name}."
        )

    # Resumen ejecutivo: totales por paciente
    executive_summary = []
    grand_total = Decimal('0')
    for section in patient_sections:
        grand_total += section['totals']['total']
        executive_summary.append({
            'patient_code': section['patient'].patient_code,
            'totals_by_cat': section['totals']['by_category'],
            'total': section['totals']['total'],
        })

    context = {
        'protocol': protocol,
        'period': period,
        'patient_sections': patient_sections,
        'executive_summary': executive_summary,
        'grand_total': grand_total,
        'generated_by': requested_by,
        'generated_at': timezone.now(),
        'report_type': 'site',
    }

    pdf_bytes = _render_pdf('reports/pdf_site.html', context)
    report_label = f"PDF consolidado {protocol.code} / {period.name}"
    _mark_expenses_exported(all_expenses, requested_by, 'site_pdf', report_label)

    return pdf_bytes


# ─── Excel consolidado ────────────────────────────────────────────────────────

def generate_site_excel(protocol, period, requested_by) -> bytes:
    """
    Genera un archivo Excel con hoja de resumen y hoja por paciente.
    Usa openpyxl con estilos básicos.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from apps.patients.models import Patient
    from apps.expenses.models import Expense

    wb = openpyxl.Workbook()

    # Estilo de cabecera
    HEADER_FONT = Font(bold=True, color='FFFFFF', size=11)
    HEADER_FILL = PatternFill('solid', fgColor='1E3A8A')  # primary-900
    CENTER = Alignment(horizontal='center', vertical='center')
    THIN = Side(style='thin', color='CCCCCC')
    BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

    def style_header(cell):
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER
        cell.border = BORDER

    def style_cell(cell):
        cell.border = BORDER
        cell.alignment = Alignment(vertical='center')

    # ── Hoja de resumen ejecutivo ──────────────────────────────────────────────
    ws_summary = wb.active
    ws_summary.title = 'Resumen'
    ws_summary.column_dimensions['A'].width = 20
    ws_summary.column_dimensions['B'].width = 16
    ws_summary.column_dimensions['C'].width = 16
    ws_summary.column_dimensions['D'].width = 16
    ws_summary.column_dimensions['E'].width = 16
    ws_summary.column_dimensions['F'].width = 16

    # Título
    ws_summary['A1'] = f'Proyecto Córdoba — Reporte Consolidado'
    ws_summary['A1'].font = Font(bold=True, size=14)
    ws_summary['A2'] = f'Protocolo: {protocol.code} — {protocol.name}'
    ws_summary['A3'] = f'Período: {period.name} ({period.date_from} — {period.date_to})'
    ws_summary['A4'] = f'Generado: {timezone.now().strftime("%d/%m/%Y %H:%M")} UTC'
    ws_summary['A4'].font = Font(italic=True, color='888888')

    ws_summary.row_dimensions[6].height = 18
    headers = ['Paciente', 'Transporte', 'Comidas', 'Alojamiento', 'Otro', 'TOTAL']
    for col, h in enumerate(headers, 1):
        cell = ws_summary.cell(row=6, column=col, value=h)
        style_header(cell)

    patients = Patient.objects.filter(protocol=protocol, is_active=True).order_by('patient_code')
    all_expenses = []
    row_num = 7
    grand_totals = defaultdict(Decimal)

    for patient in patients:
        expenses = list(
            Expense.objects.filter(
                visit__patient=patient,
                expense_date__gte=period.date_from,
                expense_date__lte=period.date_to,
                status__in=REPORT_STATUSES,
            ).select_related('visit__visit_type')
            .prefetch_related('ticket_files')
            .order_by('expense_date')
        )
        if not expenses:
            continue

        all_expenses.extend(expenses)
        totals = _calc_totals(expenses)
        row = [patient.patient_code]
        for cat in ('transport', 'meals', 'accommodation', 'other'):
            amt = totals['by_category'].get(cat, {}).get('amount', Decimal('0'))
            grand_totals[cat] += amt
            row.append(float(amt))
        row.append(float(totals['total']))

        for col, val in enumerate(row, 1):
            cell = ws_summary.cell(row=row_num, column=col, value=val)
            style_cell(cell)
            if col > 1:
                cell.number_format = '#,##0.00'

        row_num += 1

    # Fila de totales
    if row_num > 7:
        grand_row = ['TOTAL GENERAL']
        for cat in ('transport', 'meals', 'accommodation', 'other'):
            grand_row.append(float(grand_totals[cat]))
        grand_row.append(float(sum(grand_totals.values())))
        for col, val in enumerate(grand_row, 1):
            cell = ws_summary.cell(row=row_num, column=col, value=val)
            cell.font = Font(bold=True)
            cell.fill = PatternFill('solid', fgColor='DBEAFE')
            cell.border = BORDER
            if col > 1:
                cell.number_format = '#,##0.00'

    if not all_expenses:
        raise ValueError(
            f"No hay gastos aprobados para {protocol.code} en {period.name}."
        )

    # ── Hojas por paciente ─────────────────────────────────────────────────────
    patients_with_expenses = Patient.objects.filter(
        protocol=protocol,
        is_active=True,
        visits__expenses__expense_date__gte=period.date_from,
        visits__expenses__expense_date__lte=period.date_to,
        visits__expenses__status__in=REPORT_STATUSES,
    ).distinct().order_by('patient_code')

    expense_detail_headers = [
        'Fecha', 'Visita', 'Categoría', 'Proveedor', 'CUIT',
        'N° Comprobante', 'Monto', 'Moneda', 'Estado',
    ]

    for patient in patients_with_expenses:
        expenses = list(
            Expense.objects.filter(
                visit__patient=patient,
                expense_date__gte=period.date_from,
                expense_date__lte=period.date_to,
                status__in=REPORT_STATUSES,
            ).select_related('visit__visit_type')
            .order_by('expense_date')
        )
        if not expenses:
            continue

        sheet_name = patient.patient_code[:31]  # Excel max 31 chars
        ws = wb.create_sheet(title=sheet_name)
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 16
        ws.column_dimensions['C'].width = 14
        ws.column_dimensions['D'].width = 20
        ws.column_dimensions['E'].width = 16
        ws.column_dimensions['F'].width = 16
        ws.column_dimensions['G'].width = 12
        ws.column_dimensions['H'].width = 8
        ws.column_dimensions['I'].width = 14

        ws['A1'] = f'Paciente: {patient.patient_code}'
        ws['A1'].font = Font(bold=True, size=12)
        ws['A2'] = f'Protocolo: {protocol.code} — Período: {period.name}'

        for col, h in enumerate(expense_detail_headers, 1):
            cell = ws.cell(row=4, column=col, value=h)
            style_header(cell)

        for row_i, exp in enumerate(expenses, 5):
            ocr = exp.ocr_extracted if hasattr(exp, 'ocr_extracted') else {}
            row_data = [
                exp.expense_date.strftime('%d/%m/%Y'),
                exp.visit.visit_type.name,
                CATEGORY_LABELS.get(exp.category, exp.category),
                exp.vendor or '',
                ocr.get('cuit', '') if ocr else '',
                ocr.get('receipt_number', '') if ocr else '',
                float(exp.amount),
                exp.currency,
                exp.get_status_display(),
            ]
            for col_i, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_i, column=col_i, value=val)
                style_cell(cell)
                if col_i == 7:
                    cell.number_format = '#,##0.00'

        # Fila de total
        totals = _calc_totals(expenses)
        total_row = row_i + 1 if expenses else 5
        ws.cell(row=total_row, column=6, value='TOTAL').font = Font(bold=True)
        total_cell = ws.cell(row=total_row, column=7, value=float(totals['total']))
        total_cell.font = Font(bold=True)
        total_cell.number_format = '#,##0.00'
        total_cell.fill = PatternFill('solid', fgColor='DBEAFE')

    # Guardar y retornar bytes
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    report_label = f"Excel consolidado {protocol.code} / {period.name}"
    _mark_expenses_exported(all_expenses, requested_by, 'site_excel', report_label)

    return buffer.getvalue()
