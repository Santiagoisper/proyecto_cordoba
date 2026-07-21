import csv
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST


PENDING_STATUSES = ['ocr_pending', 'pending_review']

ACTIVE_EXPENSE_STATUSES = [
    'ocr_pending', 'pending_review', 'approved', 'observed', 'settled', 'exported'
]

VISIT_STATUS_LABELS = {
    'scheduled': 'Programada',
    'completed': 'Realizada',
}

COMPROBANTE_LABELS = {
    'sin_comprobante': 'Sin comprobante',
    'rechazado': 'Rechazado',
    'cargado': 'Cargado',
}


@login_required
def dashboard(request):
    user = request.user
    context = {'user': user}

    if user.is_superuser or user.is_site_admin:
        context.update(_admin_context(user))
        return render(request, 'dashboard/admin.html', context)

    if user.is_coordinator:
        context.update(_coordinator_context(user))
        return render(request, 'dashboard/coordinator.html', context)

    if user.is_assistant:
        context.update(_assistant_context(user))
        return render(request, 'dashboard/assistant.html', context)

    if user.is_auditor:
        context.update(_auditor_context(user))
        return render(request, 'dashboard/auditor.html', context)

    return render(request, 'dashboard/no_role.html', context)


def _admin_context(user):
    from apps.protocols.models import Protocol
    from apps.patients.models import Patient
    from apps.expenses.models import Expense

    return {
        'total_protocols': Protocol.objects.filter(is_active=True).count(),
        'total_patients': Patient.objects.filter(is_active=True).count(),
        'pending_expenses': Expense.objects.filter(status__in=PENDING_STATUSES).count(),
        'total_expenses': Expense.objects.count(),
        'recent_expenses': Expense.objects.select_related(
            'visit__patient__protocol', 'submitted_by'
        ).order_by('-created_at')[:10],
    }


def _annotated_visits_for(user):
    """Visitas activas anotadas con conteo de comprobantes, con scope de site."""
    from apps.patients.models import Visit

    visits_qs = (
        Visit.objects.filter(
            status__in=['scheduled', 'completed'],
            patient__protocol__is_active=True,
        )
        .select_related('patient__protocol', 'visit_type')
        .annotate(
            total_expenses=Count('expenses'),
            active_expenses=Count(
                'expenses',
                filter=Q(expenses__status__in=ACTIVE_EXPENSE_STATUSES),
            ),
        )
        .order_by('patient__protocol__code', 'patient__patient_code', 'scheduled_date')
    )

    if not user.is_superuser and not user.is_site_admin and user.site_id:
        visits_qs = visits_qs.filter(patient__protocol__site_id=user.site_id)

    return visits_qs


def _comprobante_status(visit):
    if visit.total_expenses == 0:
        return 'sin_comprobante'
    if visit.active_expenses == 0:
        return 'rechazado'
    return 'cargado'


def _coordinator_context(user):
    from datetime import timedelta
    from apps.expenses.models import Expense
    from apps.expenses.services import ExpenseValidationService
    from itertools import groupby

    today = timezone.now().date()

    # ── Datos reales para gráficos (métricas por conteo: libres de moneda) ──
    scoped_expenses = Expense.objects.all()
    if not user.is_superuser and not user.is_site_admin and user.site_id:
        scoped_expenses = scoped_expenses.filter(
            visit__patient__protocol__site_id=user.site_id
        )

    chart_protocols = list(
        scoped_expenses
        .exclude(status='rejected')
        .values('visit__patient__protocol__code')
        .annotate(count=Count('id'))
        .order_by('-count')[:6]
    )
    chart_protocols = [
        {'label': row['visit__patient__protocol__code'], 'count': row['count']}
        for row in chart_protocols
    ]

    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    daily_counts = dict(
        scoped_expenses
        .filter(created_at__date__gte=days[0])
        .values_list('created_at__date')
        .annotate(count=Count('id'))
    )
    chart_daily = [
        {'label': d.strftime('%d/%m'), 'count': daily_counts.get(d, 0)}
        for d in days
    ]

    pending_qs = Expense.objects.filter(status='pending_review').select_related(
        'visit__patient__protocol',
        'visit__visit_type',
        'submitted_by',
    ).prefetch_related('ticket_files').order_by('created_at')

    observed_qs = Expense.objects.filter(status='observed').select_related(
        'visit__patient__protocol',
        'visit__visit_type',
        'submitted_by',
        'reviewed_by',
    ).order_by('-reviewed_at')

    svc = ExpenseValidationService()
    pending_with_alerts = []
    for expense in pending_qs[:30]:
        alerts = svc.validate(expense)
        pending_with_alerts.append({
            'expense': expense,
            'alerts': alerts,
            'has_errors': any(a.level == 'error' for a in alerts),
            'has_warnings': any(a.level == 'warning' for a in alerts),
            'ticket': expense.ticket_files.first(),
        })

    visit_rows = []
    for v in _annotated_visits_for(user):
        v.comprobante_status = _comprobante_status(v)
        visit_rows.append(v)

    visits_by_protocol = []
    for protocol, group in groupby(visit_rows, key=lambda v: v.patient.protocol):
        group_list = list(group)
        visits_by_protocol.append({
            'protocol': protocol,
            'visits': group_list,
            'sin_comprobante_count': sum(1 for v in group_list if v.comprobante_status == 'sin_comprobante'),
            'rechazado_count': sum(1 for v in group_list if v.comprobante_status == 'rechazado'),
            'cargado_count': sum(1 for v in group_list if v.comprobante_status == 'cargado'),
        })

    visits_sin_comprobante = sum(
        1 for v in visit_rows if v.comprobante_status == 'sin_comprobante'
    )

    return {
        'pending_count': pending_qs.count(),
        'observed_count': observed_qs.count(),
        'approved_today': Expense.objects.filter(
            status='approved', reviewed_by=user, reviewed_at__date=today
        ).count(),
        'rejected_today': Expense.objects.filter(
            status='rejected', reviewed_by=user, reviewed_at__date=today
        ).count(),
        'visits_sin_comprobante': visits_sin_comprobante,
        'pending_with_alerts': pending_with_alerts,
        'observed_expenses': list(observed_qs[:10]),
        'visits_by_protocol': visits_by_protocol,
        'chart_protocols': chart_protocols,
        'chart_daily': chart_daily,
    }


def _assistant_context(user):
    from apps.expenses.models import Expense

    my_expenses = Expense.objects.filter(submitted_by=user).select_related(
        'visit__patient__protocol', 'visit__visit_type'
    ).order_by('-created_at')

    return {
        'my_expenses': my_expenses[:10],
        'pending_count': my_expenses.filter(status__in=PENDING_STATUSES).count(),
        'approved_count': my_expenses.filter(status='approved').count(),
        'rejected_count': my_expenses.filter(status='rejected').count(),
        'observed_count': my_expenses.filter(status='observed').count(),
    }


def _auditor_context(user):
    from apps.protocols.models import Protocol
    from apps.expenses.models import Expense, ExpensePeriod

    return {
        'protocols': Protocol.objects.filter(is_active=True).order_by('code'),
        'open_periods': ExpensePeriod.objects.filter(status='open').select_related('protocol').count(),
        'total_expenses': Expense.objects.count(),
    }


@login_required
def export_visits_csv(request):
    """Exporta a CSV el seguimiento de visitas con su estado de comprobante."""
    user = request.user
    if not (user.is_superuser or user.is_site_admin or user.is_coordinator):
        return HttpResponseForbidden()

    visits_qs = _annotated_visits_for(user)

    protocol_filter = request.GET.get('protocol', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if protocol_filter:
        visits_qs = visits_qs.filter(patient__protocol__code=protocol_filter)

    rows = []
    for v in visits_qs:
        comprobante_status = _comprobante_status(v)
        if status_filter and comprobante_status != status_filter:
            continue
        rows.append([
            v.patient.protocol.code,
            v.patient.patient_code,
            v.visit_type.name,
            v.scheduled_date.strftime('%d/%m/%Y') if v.scheduled_date else '',
            VISIT_STATUS_LABELS.get(v.status, v.status),
            COMPROBANTE_LABELS.get(comprobante_status, comprobante_status),
        ])

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="visitas_comprobantes.csv"'
    response.write('﻿')

    writer = csv.writer(response)
    writer.writerow([
        'Protocolo',
        'Código paciente',
        'Tipo de visita',
        'Fecha programada',
        'Estado visita',
        'Estado comprobante',
    ])
    writer.writerows(rows)

    return response


@login_required
def auditor_viaticos_dashboard(request):
    """Dashboard del auditor: gestión de topes y tracking de viáticos por paciente."""
    user = request.user
    if not (user.is_superuser or user.is_site_admin or user.is_auditor):
        return HttpResponseForbidden("No tenés acceso a esta página")

    from apps.patients.models import Patient
    from apps.protocols.models import Protocol

    protocol_id = request.GET.get('protocol_id')
    search_query = request.GET.get('search', '').strip()

    patients_qs = Patient.objects.select_related('protocol').filter(is_active=True)

    if not user.is_superuser and not user.is_site_admin:
        if not user.site_id:
            patients_qs = patients_qs.none()
        else:
            patients_qs = patients_qs.filter(protocol__site_id=user.site_id)

    if protocol_id and protocol_id.isdigit():
        patients_qs = patients_qs.filter(protocol_id=protocol_id)
    else:
        protocol_id = None

    if search_query:
        patients_qs = patients_qs.filter(
            Q(patient_code__icontains=search_query) | Q(initials__icontains=search_query)
        )

    patients_with_summary = []
    for patient in patients_qs.order_by('protocol__code', 'patient_code'):
        total_viaticos = patient.get_total_viaticos()
        patients_with_summary.append({
            'patient': patient,
            'total_viaticos': total_viaticos,
            'remaining': patient.viatic_cap - Decimal(str(total_viaticos)),
            'percentage': patient.get_viaticos_percentage(),
            'status': patient.get_viaticos_status(),
        })

    protocols = Protocol.objects.filter(is_active=True).order_by('code')
    if not user.is_superuser and not user.is_site_admin:
        protocols = protocols.filter(site_id=user.site_id) if user.site_id else protocols.none()

    return render(request, 'dashboard/auditor_viaticos.html', {
        'patients_with_summary': patients_with_summary,
        'protocols': protocols,
        'selected_protocol_id': int(protocol_id) if protocol_id else None,
        'search_query': search_query,
        'total_patients': len(patients_with_summary),
    })


@login_required
@require_POST
def update_patient_viatic_cap(request, patient_id):
    """Actualiza el tope de viáticos de un paciente (POST)."""
    from apps.patients.models import Patient

    user = request.user
    if not (user.is_superuser or user.is_site_admin or user.is_auditor):
        return HttpResponseForbidden()

    patient_qs = Patient.objects.select_related('protocol')
    if not user.is_superuser and not user.is_site_admin:
        if not user.site_id:
            patient_qs = patient_qs.none()
        else:
            patient_qs = patient_qs.filter(protocol__site_id=user.site_id)
    patient = get_object_or_404(patient_qs, pk=patient_id)

    new_cap = request.POST.get('viatic_cap', '').strip()
    if not new_cap:
        return HttpResponse('El tope no puede estar vacío', status=400)

    try:
        cap_value = Decimal(new_cap)
    except InvalidOperation:
        return HttpResponse('Tope inválido', status=400)
    if cap_value < 0:
        return HttpResponse('El tope no puede ser negativo', status=400)

    patient.viatic_cap = cap_value
    patient.save(update_fields=['viatic_cap'])

    from apps.expenses.models import AuditLog
    AuditLog.objects.create(
        user=user,
        action='updated',
        content_type='Patient',
        object_id=patient.pk,
        object_repr=str(patient),
        details={'field': 'viatic_cap', 'new_value': str(cap_value)},
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return HttpResponse(f'Tope actualizado a ${cap_value}', status=200)
