import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.protocols.models import Protocol
from apps.patients.models import Patient, Visit

from .models import Expense, ExpensePeriod, TicketFile, AuditLog
from .forms import ExpenseCreateForm, ExpenseReviewForm, ObservedCorrectionForm
from .tasks import process_ocr_for_ticket
from .services import ExpenseValidationService, close_period as close_period_service

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _can_coordinate(user):
    """True si el usuario puede aprobar/rechazar/observar gastos."""
    return user.is_superuser or user.is_site_admin or user.is_coordinator


def _period_locked_response(expense):
    """
    Retorna un HttpResponse(422) si el gasto pertenece a un período cerrado o exportado.
    Retorna None si la mutación está permitida.
    Llamar DESPUÉS de haber hecho select_related('period') en el queryset.
    """
    if expense.period_id is not None and expense.period.status != 'open':
        msg = (
            f'Este gasto pertenece al período «{expense.period.name}» '
            f'({expense.period.get_status_display().lower()}). '
            f'Los períodos cerrados son inmutables.'
        )
        return HttpResponse(
            f'<p class="text-red-600 text-sm px-4 py-2">{msg}</p>',
            status=422,
        )
    return None


# ─── Expense list ─────────────────────────────────────────────────────────────

@login_required
def expense_list(request):
    """Lista de gastos del asistente autenticado."""
    user = request.user

    if _can_coordinate(user):
        qs = Expense.objects.select_related(
            'visit__patient__protocol', 'visit__visit_type', 'submitted_by'
        ).order_by('-created_at')
        title = 'Todos los gastos'
    else:
        qs = Expense.objects.filter(submitted_by=user).select_related(
            'visit__patient__protocol', 'visit__visit_type'
        ).order_by('-created_at')
        title = 'Mis gastos'

    return render(request, 'expenses/list.html', {
        'expenses': qs[:50],
        'title': title,
    })


# ─── Expense create ───────────────────────────────────────────────────────────

@login_required
def expense_create(request):
    """
    Wizard de carga: protocolo → paciente (HTMX) → visita (HTMX) + foto.
    POST: crea el Expense con status ocr_pending y lanza OCR.
    """
    protocols = Protocol.objects.filter(is_active=True).order_by('code')

    if request.method == 'POST':
        form = ExpenseCreateForm(request.POST, request.FILES)
        if form.is_valid():
            visit_id = form.cleaned_data['visit']
            visit = get_object_or_404(Visit, pk=visit_id)

            expense = Expense.objects.create(
                visit=visit,
                category=form.cleaned_data['category'],
                amount=0,
                expense_date=form.cleaned_data['expense_date'],
                description=form.cleaned_data['description'],
                status='ocr_pending',
                submitted_by=request.user,
            )

            uploaded = request.FILES['ticket_file']
            ticket = TicketFile.objects.create(
                expense=expense,
                file=uploaded,
                original_filename=uploaded.name,
                file_size=uploaded.size,
                mime_type=uploaded.content_type,
                uploaded_by=request.user,
                ocr_status='pending',
            )

            AuditLog.objects.create(
                user=request.user,
                action='created',
                content_type='Expense',
                object_id=expense.pk,
                object_repr=str(expense),
                details={'visit_id': visit.pk, 'category': expense.category, 'ticket_file_id': ticket.pk},
                ip_address=_get_client_ip(request),
            )

            try:
                process_ocr_for_ticket.delay(ticket.pk)
            except Exception as e:
                logger.warning("No se pudo encolar tarea OCR: %s", e)
                expense.status = 'pending_review'
                expense.save(update_fields=['status'])

            messages.success(request, 'Ticket cargado. Revisá los datos extraídos.')
            return redirect('expenses:review', pk=expense.pk)

        return render(request, 'expenses/create.html', {'form': form, 'protocols': protocols})

    return render(request, 'expenses/create.html', {
        'form': ExpenseCreateForm(),
        'protocols': protocols,
    })


# ─── Expense review (OCR) ─────────────────────────────────────────────────────

@login_required
def expense_review(request, pk):
    """Revisión OCR: muestra campos extraídos con badges de confianza."""
    expense = get_object_or_404(
        Expense.objects.select_related('visit__patient__protocol', 'visit__visit_type', 'period'),
        pk=pk,
    )

    if not (request.user == expense.submitted_by or _can_coordinate(request.user)):
        return HttpResponseForbidden("No tenés permiso para ver este gasto.")

    ticket = expense.ticket_files.first()
    ocr_extracted = expense.ocr_extracted
    ocr_confidence = expense.ocr_confidence_per_field

    if request.method == 'POST':
        lock_response = _period_locked_response(expense)
        if lock_response:
            messages.error(request, 'El período de este gasto está cerrado. No se permiten modificaciones.')
            return redirect('expenses:detail', pk=expense.pk)

        form = ExpenseReviewForm(request.POST, instance=expense)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.status = 'pending_review'
            updated.save()
            AuditLog.objects.create(
                user=request.user,
                action='updated',
                content_type='Expense',
                object_id=expense.pk,
                object_repr=str(expense),
                details={'action': 'ocr_review_confirmed', 'amount': str(updated.amount),
                         'vendor': updated.vendor, 'expense_date': str(updated.expense_date)},
                ip_address=_get_client_ip(request),
            )
            messages.success(request, 'Gasto confirmado y enviado para revisión del coordinador.')
            return redirect('expenses:list')
    else:
        initial = {
            'amount': ocr_extracted.get('amount'),
            'expense_date': ocr_extracted.get('date') or expense.expense_date,
            'vendor': ocr_extracted.get('vendor') or expense.vendor,
        }
        form = ExpenseReviewForm(instance=expense, initial=initial)

    def _badge(f):
        c = ocr_confidence.get(f, 0.0)
        if c >= 0.7:
            return {'css': 'bg-green-100 text-green-700 border-green-200', 'label': f'Confianza alta ({c:.0%})'}
        elif c >= 0.4:
            return {'css': 'bg-amber-100 text-amber-700 border-amber-200', 'label': f'Confianza media ({c:.0%})'}
        elif c > 0:
            return {'css': 'bg-red-100 text-red-600 border-red-200', 'label': f'Confianza baja ({c:.0%})'}
        return {'css': 'bg-slate-100 text-slate-500 border-slate-200', 'label': 'Sin dato OCR — completar manualmente'}

    return render(request, 'expenses/review.html', {
        'expense': expense,
        'ticket': ticket,
        'form': form,
        'ocr_extracted': ocr_extracted,
        'is_mock': expense.ocr_raw_data.get('mock', False) if expense.ocr_raw_data else True,
        'badges': {f: _badge(f) for f in ['amount', 'date', 'vendor', 'cuit', 'receipt']},
        'cuit': ocr_extracted.get('cuit', ''),
        'receipt_number': ocr_extracted.get('receipt_number', ''),
    })


# ─── Expense detail ──────────────────────────────────────────────────────────

@login_required
def expense_detail(request, pk):
    """
    Detalle completo del gasto: datos, ticket, alertas de validación, timeline auditoría.
    Accesible para el asistente que lo cargó y para coordinadores/admins.
    """
    expense = get_object_or_404(
        Expense.objects.select_related(
            'visit__patient__protocol', 'visit__visit_type',
            'submitted_by', 'reviewed_by', 'period'
        ).prefetch_related('ticket_files'),
        pk=pk,
    )

    if not (request.user == expense.submitted_by or _can_coordinate(request.user)
            or request.user.is_auditor):
        return HttpResponseForbidden("No tenés permiso para ver este gasto.")

    ticket = expense.ticket_files.first()
    audit_logs = AuditLog.objects.filter(
        content_type='Expense', object_id=expense.pk
    ).order_by('timestamp')

    svc = ExpenseValidationService()
    alerts = svc.validate(expense)

    return render(request, 'expenses/detail.html', {
        'expense': expense,
        'ticket': ticket,
        'audit_logs': audit_logs,
        'alerts': alerts,
    })


# ─── Observed correction (asistente) ─────────────────────────────────────────

@login_required
def expense_correct(request, pk):
    """
    Permite al asistente corregir un gasto 'observed' y reenviarlo a revisión.
    """
    expense = get_object_or_404(
        Expense.objects.select_related('period'), pk=pk, status='observed'
    )

    if not (request.user == expense.submitted_by or _can_coordinate(request.user)):
        return HttpResponseForbidden("No tenés permiso para corregir este gasto.")

    lock_response = _period_locked_response(expense)
    if lock_response and request.method == 'POST':
        messages.error(request, 'El período de este gasto está cerrado. No se permiten correcciones.')
        return redirect('expenses:detail', pk=expense.pk)

    if request.method == 'POST':
        form = ObservedCorrectionForm(request.POST, instance=expense)
        if form.is_valid():
            prev_notes = expense.review_notes
            updated = form.save(commit=False)
            updated.status = 'pending_review'
            updated.reviewed_by = None
            updated.reviewed_at = None
            updated.review_notes = ''
            updated.save()
            AuditLog.objects.create(
                user=request.user,
                action='corrected',
                content_type='Expense',
                object_id=expense.pk,
                object_repr=str(expense),
                details={'prev_notes': prev_notes},
                ip_address=_get_client_ip(request),
            )
            messages.success(request, 'Correcciones enviadas. El gasto vuelve a revisión del coordinador.')
            return redirect('expenses:list')
    else:
        form = ObservedCorrectionForm(instance=expense)

    ticket = expense.ticket_files.first()
    return render(request, 'expenses/correct.html', {
        'expense': expense,
        'form': form,
        'ticket': ticket,
    })


# ─── Coordinator action endpoints (HTMX) ─────────────────────────────────────

@login_required
@require_POST
def approve_expense(request, pk):
    """Aprueba un gasto. Solo coordinadores/admins. Retorna HTML parcial para HTMX."""
    if not _can_coordinate(request.user):
        return HttpResponseForbidden("No tenés permiso para aprobar gastos.")

    expense = get_object_or_404(
        Expense.objects.select_related('period'), pk=pk, status='pending_review'
    )
    lock_response = _period_locked_response(expense)
    if lock_response:
        return lock_response
    prev_status = expense.status

    expense.status = 'approved'
    expense.reviewed_by = request.user
    expense.reviewed_at = timezone.now()
    expense.review_notes = request.POST.get('notes', '')
    expense.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])

    AuditLog.objects.create(
        user=request.user,
        action='approved',
        content_type='Expense',
        object_id=expense.pk,
        object_repr=str(expense),
        details={'prev_status': prev_status, 'notes': expense.review_notes},
        ip_address=_get_client_ip(request),
    )

    return render(request, 'expenses/partials/expense_action_done.html', {
        'expense': expense,
        'action': 'approved',
        'action_label': 'Aprobado',
    })


@login_required
@require_POST
def reject_expense(request, pk):
    """Rechaza un gasto con comentario obligatorio. Retorna HTML parcial para HTMX."""
    if not _can_coordinate(request.user):
        return HttpResponseForbidden("No tenés permiso para rechazar gastos.")

    expense = get_object_or_404(
        Expense.objects.select_related('period'), pk=pk, status='pending_review'
    )
    lock_response = _period_locked_response(expense)
    if lock_response:
        return lock_response
    notes = request.POST.get('notes', '').strip()
    if not notes:
        return HttpResponse(
            '<p class="text-red-600 text-sm px-4 py-2">El motivo de rechazo es obligatorio.</p>',
            status=422,
        )

    prev_status = expense.status
    expense.status = 'rejected'
    expense.reviewed_by = request.user
    expense.reviewed_at = timezone.now()
    expense.review_notes = notes
    expense.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])

    AuditLog.objects.create(
        user=request.user,
        action='rejected',
        content_type='Expense',
        object_id=expense.pk,
        object_repr=str(expense),
        details={'prev_status': prev_status, 'notes': notes},
        ip_address=_get_client_ip(request),
    )

    return render(request, 'expenses/partials/expense_action_done.html', {
        'expense': expense,
        'action': 'rejected',
        'action_label': 'Rechazado',
    })


@login_required
@require_POST
def observe_expense(request, pk):
    """Observa un gasto con comentario obligatorio. Retorna HTML parcial para HTMX."""
    if not _can_coordinate(request.user):
        return HttpResponseForbidden("No tenés permiso para observar gastos.")

    expense = get_object_or_404(
        Expense.objects.select_related('period'), pk=pk, status='pending_review'
    )
    lock_response = _period_locked_response(expense)
    if lock_response:
        return lock_response
    notes = request.POST.get('notes', '').strip()
    if not notes:
        return HttpResponse(
            '<p class="text-red-600 text-sm px-4 py-2">El comentario de observación es obligatorio.</p>',
            status=422,
        )

    prev_status = expense.status
    expense.status = 'observed'
    expense.reviewed_by = request.user
    expense.reviewed_at = timezone.now()
    expense.review_notes = notes
    expense.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])

    AuditLog.objects.create(
        user=request.user,
        action='observed',
        content_type='Expense',
        object_id=expense.pk,
        object_repr=str(expense),
        details={'prev_status': prev_status, 'notes': notes},
        ip_address=_get_client_ip(request),
    )

    return render(request, 'expenses/partials/expense_action_done.html', {
        'expense': expense,
        'action': 'observed',
        'action_label': 'Observado',
    })


@login_required
@require_GET
def action_modal(request, pk, action):
    """Retorna HTML del modal de comentario para rechazar/observar (HTMX GET)."""
    if not _can_coordinate(request.user):
        return HttpResponseForbidden()

    expense = get_object_or_404(Expense, pk=pk)
    return render(request, 'expenses/partials/action_modal.html', {
        'expense': expense,
        'action': action,
        'action_label': 'Rechazar' if action == 'reject' else 'Observar',
        'placeholder': (
            'Ej: el monto no coincide con el ticket, falta información...'
            if action == 'reject'
            else 'Ej: por favor adjuntar el comprobante original...'
        ),
    })


# ─── Period management ───────────────────────────────────────────────────────

@login_required
def period_list(request):
    """Lista de períodos de rendición. Solo coordinadores y admins."""
    if not _can_coordinate(request.user):
        return HttpResponseForbidden("No tenés permiso para ver períodos.")

    periods = (
        ExpensePeriod.objects
        .select_related('protocol', 'closed_by', 'created_by')
        .annotate(
            count_pending=Count('expenses', filter=Q(expenses__status='pending_review')),
            count_approved=Count('expenses', filter=Q(expenses__status='approved')),
            count_rejected=Count('expenses', filter=Q(expenses__status='rejected')),
            count_observed=Count('expenses', filter=Q(expenses__status='observed')),
            count_settled=Count('expenses', filter=Q(expenses__status='settled')),
            count_total=Count('expenses'),
        )
        .order_by('-date_from')
    )

    protocol_id = request.GET.get('protocol')
    if protocol_id:
        periods = periods.filter(protocol_id=protocol_id)

    protocols = Protocol.objects.filter(is_active=True).order_by('code')

    return render(request, 'expenses/periods.html', {
        'periods': periods,
        'protocols': protocols,
        'selected_protocol': protocol_id,
    })


@login_required
@require_POST
def close_period_view(request, pk):
    """
    Cierra un período de rendición. Solo coordinadores/admins.
    POST-only. Si la petición es HTMX retorna un partial con la fila actualizada;
    de lo contrario redirige a la lista de períodos.
    """
    if not _can_coordinate(request.user):
        return HttpResponseForbidden("No tenés permiso para cerrar períodos.")

    try:
        period = close_period_service(pk, request.user)
    except ExpensePeriod.DoesNotExist:
        return HttpResponse(
            '<div class="text-red-600 text-sm px-4 py-2">Período no encontrado.</div>',
            status=404,
        )
    except ValueError as exc:
        error_html = (
            f'<div id="period-error-{pk}" '
            f'class="text-red-700 text-sm px-4 py-3 bg-red-50 rounded-lg border border-red-200 mt-2">'
            f'<strong>No se pudo cerrar:</strong> {exc}</div>'
        )
        if request.headers.get('HX-Request'):
            return HttpResponse(error_html, status=422)
        messages.error(request, str(exc))
        return redirect('periods:list')
    except Exception as exc:
        logger.exception("Error inesperado cerrando período %s: %s", pk, exc)
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="text-red-600 text-sm px-4 py-2">Error interno. Contactá al administrador.</div>',
                status=500,
            )
        messages.error(request, "Error inesperado al cerrar el período.")
        return redirect('periods:list')

    if request.headers.get('HX-Request'):
        period_annotated = (
            ExpensePeriod.objects
            .filter(pk=period.pk)
            .select_related('protocol', 'closed_by')
            .annotate(
                count_pending=Count('expenses', filter=Q(expenses__status='pending_review')),
                count_approved=Count('expenses', filter=Q(expenses__status='approved')),
                count_settled=Count('expenses', filter=Q(expenses__status='settled')),
                count_total=Count('expenses'),
            )
            .first()
        )
        return render(request, 'expenses/partials/period_row.html', {
            'period': period_annotated,
        })

    messages.success(request, f"Período «{period.name}» cerrado correctamente.")
    return redirect('periods:list')


# ─── HTMX chained selects ────────────────────────────────────────────────────

@login_required
@require_GET
def htmx_patients_for_protocol(request):
    protocol_id = request.GET.get('protocol') or request.GET.get('protocol_id')
    patients = []
    if protocol_id:
        patients = Patient.objects.filter(
            protocol_id=protocol_id, is_active=True
        ).order_by('patient_code')
    return render(request, 'expenses/partials/patient_options.html', {'patients': patients})


@login_required
@require_GET
def htmx_visits_for_patient(request):
    patient_id = request.GET.get('patient') or request.GET.get('patient_id')
    visits = []
    if patient_id:
        visits = Visit.objects.filter(
            patient_id=patient_id
        ).select_related('visit_type').order_by('scheduled_date')
    return render(request, 'expenses/partials/visit_options.html', {'visits': visits})
