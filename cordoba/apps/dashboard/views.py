from django.shortcuts import render
from django.contrib.auth.decorators import login_required
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

    return {
        'pending_count': pending_qs.count(),
        'observed_count': observed_qs.count(),
        'approved_today': Expense.objects.filter(
            status='approved', reviewed_by=user, reviewed_at__date=today
        ).count(),
        'rejected_today': Expense.objects.filter(
            status='rejected', reviewed_by=user, reviewed_at__date=today
        ).count(),
        'pending_with_alerts': pending_with_alerts,
        'observed_expenses': list(observed_qs[:10]),
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
