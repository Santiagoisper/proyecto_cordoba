import csv
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone


PENDING_STATUSES = ['ocr_pending', 'pending_review']


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


def _coordinator_context(user):
    from apps.expenses.models import Expense
    from apps.expenses.services import ExpenseValidationService
    from apps.patients.models import Visit
    from django.db.models import Count, Q
    from itertools import groupby

    today = timezone.now().date()

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

    # Seguimiento de visitas: estado de comprobante por visita
    ACTIVE_EXPENSE_STATUSES = [
        'ocr_pending', 'pending_review', 'approved', 'observed', 'settled', 'exported'
    ]
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

    # Site-scope: coordinators only see visits from their own site (same rule as expenses)
    if not user.is_superuser and not user.is_site_admin and user.site_id:
        visits_qs = visits_qs.filter(patient__protocol__site_id=user.site_id)

    visit_rows = []
    for v in visits_qs:
        if v.total_expenses == 0:
            v.comprobante_status = 'sin_comprobante'
        elif v.active_expenses == 0:
            v.comprobante_status = 'rechazado'
        else:
            v.comprobante_status = 'cargado'
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
    user = request.user
    if not (user.is_superuser or user.is_site_admin or user.is_coordinator):
        return HttpResponseForbidden()

    from apps.patients.models import Visit
    from django.db.models import Count, Q

    ACTIVE_EXPENSE_STATUSES = [
        'ocr_pending', 'pending_review', 'approved', 'observed', 'settled', 'exported'
    ]

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

    protocol_filter = request.GET.get('protocol', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if protocol_filter:
        visits_qs = visits_qs.filter(patient__protocol__code=protocol_filter)

    VISIT_STATUS_LABELS = {
        'scheduled': 'Programada',
        'completed': 'Realizada',
    }
    COMPROBANTE_LABELS = {
        'sin_comprobante': 'Sin comprobante',
        'rechazado': 'Rechazado',
        'cargado': 'Cargado',
    }

    rows = []
    for v in visits_qs:
        if v.total_expenses == 0:
            comprobante_status = 'sin_comprobante'
        elif v.active_expenses == 0:
            comprobante_status = 'rechazado'
        else:
            comprobante_status = 'cargado'

        if status_filter and comprobante_status != status_filter:
            continue

        rows.append({
            'protocol_code': v.patient.protocol.code,
            'patient_code': v.patient.patient_code,
            'visit_type': v.visit_type.name,
            'scheduled_date': v.scheduled_date.strftime('%d/%m/%Y') if v.scheduled_date else '',
            'visit_status': VISIT_STATUS_LABELS.get(v.status, v.status),
            'comprobante_status': COMPROBANTE_LABELS.get(comprobante_status, comprobante_status),
        })

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="visitas_comprobantes.csv"'
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'Protocolo',
        'Código paciente',
        'Tipo de visita',
        'Fecha programada',
        'Estado visita',
        'Estado comprobante',
    ])
    for row in rows:
        writer.writerow([
            row['protocol_code'],
            row['patient_code'],
            row['visit_type'],
            row['scheduled_date'],
            row['visit_status'],
            row['comprobante_status'],
        ])

    return response
