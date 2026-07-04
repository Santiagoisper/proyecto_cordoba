import csv
from datetime import timedelta
from decimal import Decimal

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
def global_board(request):
    """
    Tablero global de control: cuánto está destinando y pagando el centro
    a todos los pacientes, de todos los protocolos y de todas las visitas.
    Acceso: superusuario, site_admin, coordinador y auditor (scoped a su site).
    """
    user = request.user
    if not (user.is_superuser or user.is_site_admin or user.is_coordinator or user.is_auditor):
        return HttpResponseForbidden("No tenés acceso al tablero global.")

    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth
    from apps.expenses.models import Expense

    COMMITTED = ['approved', 'settled', 'exported']
    PENDING = ['ocr_pending', 'pending_review', 'observed']

    qs = Expense.objects.select_related(
        'visit__patient__protocol', 'visit__visit_type'
    )
    if not user.is_superuser and not user.is_site_admin:
        if not user.site_id:
            qs = qs.none()
        else:
            qs = qs.filter(visit__patient__protocol__site_id=user.site_id)

    committed_qs = qs.filter(status__in=COMMITTED)
    pending_qs = qs.filter(status__in=PENDING)

    # ── KPIs generales ────────────────────────────────────────────────────
    committed_by_currency = list(
        committed_qs.values('currency')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('currency')
    )
    total_usd = committed_qs.aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')
    usd_missing_count = committed_qs.filter(amount_usd__isnull=True).count()

    pending_by_currency = list(
        pending_qs.values('currency')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('currency')
    )

    kpis = {
        'committed_by_currency': committed_by_currency,
        'committed_count': committed_qs.count(),
        'total_usd': total_usd,
        'usd_missing_count': usd_missing_count,
        'pending_by_currency': pending_by_currency,
        'pending_count': pending_qs.count(),
        'patients_with_expenses': committed_qs.values('visit__patient').distinct().count(),
        'protocols_with_expenses': committed_qs.values('visit__patient__protocol').distinct().count(),
    }

    # ── Por protocolo ─────────────────────────────────────────────────────
    by_protocol = list(
        committed_qs.values(
            'visit__patient__protocol__id',
            'visit__patient__protocol__code',
            'visit__patient__protocol__name',
            'visit__patient__protocol__sponsor',
            'currency',
        )
        .annotate(
            total=Sum('amount'),
            count=Count('id'),
            patients=Count('visit__patient', distinct=True),
        )
        .order_by('visit__patient__protocol__code', 'currency')
    )
    max_protocol_total = max((row['total'] for row in by_protocol), default=Decimal('0'))
    for row in by_protocol:
        row['bar_pct'] = int(row['total'] / max_protocol_total * 100) if max_protocol_total else 0

    # ── Por visita (protocolo + tipo de visita) ───────────────────────────
    by_visit = list(
        committed_qs.values(
            'visit__patient__protocol__code',
            'visit__visit_type__name',
            'visit__visit_type__order',
            'currency',
        )
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('visit__patient__protocol__code', 'visit__visit_type__order', 'currency')
    )

    # ── Por categoría ─────────────────────────────────────────────────────
    by_category = list(
        committed_qs.values('category', 'currency')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('category', 'currency')
    )
    category_labels = dict(Expense.CATEGORY_CHOICES)
    max_category_total = max((row['total'] for row in by_category), default=Decimal('0'))
    for row in by_category:
        row['label'] = category_labels.get(row['category'], row['category'])
        row['bar_pct'] = int(row['total'] / max_category_total * 100) if max_category_total else 0

    # ── Por mes (últimos 12) ──────────────────────────────────────────────
    today = timezone.now().date()
    twelve_months_ago = (today.replace(day=1) - timedelta(days=365))
    by_month = list(
        committed_qs.filter(expense_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('expense_date'))
        .values('month', 'currency')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('month', 'currency')
    )
    max_month_total = max((row['total'] for row in by_month), default=Decimal('0'))
    for row in by_month:
        row['bar_pct'] = int(row['total'] / max_month_total * 100) if max_month_total else 0

    return render(request, 'dashboard/global_board.html', {
        'kpis': kpis,
        'by_protocol': by_protocol,
        'by_visit': by_visit,
        'by_category': by_category,
        'by_month': by_month,
        'recent_expenses': qs.order_by('-created_at')[:10],
    })


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


@login_required
def auditor_viaticos_dashboard(request):
    """Dashboard del auditor: gestión de topes y tracking de viáticos por paciente."""
    user = request.user
    if not (user.is_superuser or user.is_site_admin or user.is_auditor):
        return HttpResponseForbidden("No tenés acceso a esta página")

    from apps.patients.models import Patient
    from apps.protocols.models import Protocol
    from django.db.models import Q

    # Filtros
    protocol_id = request.GET.get('protocol_id')
    search_query = request.GET.get('search', '').strip()

    # Queryset base
    patients_qs = Patient.objects.select_related('protocol').filter(is_active=True)

    if not user.is_superuser and not user.is_site_admin and user.site_id:
        patients_qs = patients_qs.filter(protocol__site_id=user.site_id)

    if protocol_id:
        patients_qs = patients_qs.filter(protocol_id=protocol_id)

    if search_query:
        patients_qs = patients_qs.filter(
            Q(patient_code__icontains=search_query) | Q(initials__icontains=search_query)
        )

    patients_with_summary = []
    for patient in patients_qs.order_by('protocol__code', 'patient_code'):
        total_viaticos = patient.get_total_viaticos()
        percentage = patient.get_viaticos_percentage()
        status = patient.get_viaticos_status()

        patients_with_summary.append({
            'patient': patient,
            'total_viaticos': total_viaticos,
            'remaining': float(patient.viatic_cap) - float(total_viaticos),
            'percentage': percentage,
            'status': status,
        })

    protocols = Protocol.objects.filter(is_active=True).order_by('code')
    if not user.is_superuser and not user.is_site_admin and user.site_id:
        protocols = protocols.filter(site_id=user.site_id)

    return render(request, 'dashboard/auditor_viaticos.html', {
        'patients_with_summary': patients_with_summary,
        'protocols': protocols,
        'selected_protocol_id': int(protocol_id) if protocol_id else None,
        'search_query': search_query,
        'total_patients': len(patients_with_summary),
    })


@login_required
def update_patient_viatic_cap(request, patient_id):
    """Actualiza el tope de viáticos de un paciente (POST)."""
    from decimal import Decimal, InvalidOperation
    from django.shortcuts import get_object_or_404
    from apps.patients.models import Patient

    if request.method != 'POST':
        return HttpResponseForbidden()

    user = request.user
    if not (user.is_superuser or user.is_site_admin or user.is_auditor):
        return HttpResponseForbidden()

    patient = get_object_or_404(
        Patient.objects.select_related('protocol'), pk=patient_id
    )

    if not user.is_superuser and not user.is_site_admin and user.site_id:
        if patient.protocol.site_id != user.site_id:
            return HttpResponseForbidden()

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
        ip_address=request.META.get('REMOTE_ADDR')
    )

    return HttpResponse(f'Tope actualizado a ${cap_value}', status=200)
