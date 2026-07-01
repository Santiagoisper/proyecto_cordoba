import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.protocols.models import Protocol, VisitType
from apps.patients.models import Patient, Visit

from .models import Expense, ExpensePeriod, TicketFile, AuditLog, ReceptionTicket
from .forms import (
    ExpenseCreateForm,
    ExpenseReviewForm,
    ObservedCorrectionForm,
    ReceptionTicketUploadForm,
    ReceptionTicketAssignForm,
)
from .tasks import process_ocr_for_ticket
from .services import (
    ExpenseValidationService,
    calculate_amount_usd,
    close_period as close_period_service,
)

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _can_coordinate(user):
    """True si el usuario puede revisar gastos (ver lista de pendientes)."""
    return user.is_superuser or user.is_site_admin or user.is_coordinator


def _can_review(user):
    """True si el usuario puede REVISAR gastos (admin/site_admin, pero no aprobar)."""
    return user.is_superuser or user.is_site_admin


def _can_approve(user):
    """True si el usuario puede APROBAR gastos (solo coordinadores)."""
    return user.is_coordinator or user.is_site_admin or user.is_superuser


def _can_work_reception(user):
    """True si el usuario puede subir o imputar tickets de recepción."""
    return user.is_superuser or user.is_site_admin or user.is_coordinator or user.is_assistant


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


def _site_scope_expenses(user, qs):
    """
    Restringe el QuerySet de Expense al site del usuario.
    Protección IDOR: roles operativos sin site asignado no reciben acceso global.
    """
    if not user.is_superuser and not user.is_site_admin:
        if not user.site_id:
            return qs.none()
        qs = qs.filter(visit__patient__protocol__site_id=user.site_id)
    return qs


def _site_scope_periods(user, qs):
    """
    Restringe el QuerySet de ExpensePeriod al site del usuario.
    Roles operativos sin site asignado no reciben acceso global.
    """
    if not user.is_superuser and not user.is_site_admin:
        if not user.site_id:
            return qs.none()
        qs = qs.filter(protocol__site_id=user.site_id)
    return qs


def _site_scope_reception_tickets(user, qs):
    """Restringe tickets de recepción al site del usuario."""
    if not user.is_superuser and not user.is_site_admin:
        if not user.site_id:
            return qs.none()
        qs = qs.filter(site_id=user.site_id)
    return qs


def _protocols_for_user(user):
    protocols = Protocol.objects.filter(is_active=True).order_by('code')
    if not user.is_superuser and not user.is_site_admin:
        protocols = protocols.filter(site_id=user.site_id) if user.site_id else protocols.none()
    return protocols


def _create_expense_from_assignment(request, form, patient, visit_type, ticket_file=None):
    visit_actual_date = form.cleaned_data.get('visit_actual_date')
    visit, created = Visit.objects.get_or_create(
        patient=patient,
        visit_type=visit_type,
        defaults={
            'scheduled_date': timezone.now().date(),
            'actual_date': visit_actual_date,
            'status': 'scheduled',
            'created_by': request.user,
        },
    )
    if not created and visit_actual_date:
        visit.actual_date = visit_actual_date
        visit.save(update_fields=['actual_date'])

    if visit.expenses.exclude(status='rejected').exists():
        form.add_error(
            None,
            f'La visita "{visit_type.name}" de {patient.patient_code} ya tiene '
            'un comprobante cargado. Solo podés agregar uno nuevo si el anterior es rechazado.',
        )
        return None, None

    expense = Expense.objects.create(
        visit=visit,
        category=form.cleaned_data['category'],
        amount=0,
        expense_date=form.cleaned_data['expense_date'],
        description=form.cleaned_data['description'],
        status='ocr_pending',
        submitted_by=request.user,
    )

    if ticket_file is not None:
        ticket = TicketFile.objects.create(
            expense=expense,
            file=ticket_file.file,
            original_filename=ticket_file.original_filename,
            file_size=ticket_file.file_size,
            mime_type=ticket_file.mime_type,
            uploaded_by=request.user,
            ocr_status='pending',
        )
    else:
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
        details={
            'visit_id': visit.pk,
            'visit_type': visit_type.name,
            'patient_code': patient.patient_code,
            'category': expense.category,
            'ticket_file_id': ticket.pk,
        },
        ip_address=_get_client_ip(request),
    )
    return expense, ticket


# ─── Expense list ─────────────────────────────────────────────────────────────

@login_required
def reception_upload(request):
    """Carga rápida de comprobante en recepción, todavía sin imputar."""
    if not _can_work_reception(request.user):
        return HttpResponseForbidden("No tenés permiso para subir tickets de recepción.")
    if not request.user.is_superuser and not request.user.is_site_admin and not request.user.site_id:
        return HttpResponseForbidden("No tenés un site asignado para subir tickets.")

    if request.method == 'POST':
        form = ReceptionTicketUploadForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            uploaded = request.FILES['file']
            ticket.original_filename = uploaded.name
            ticket.file_size = uploaded.size
            ticket.mime_type = uploaded.content_type
            ticket.uploaded_by = request.user
            ticket.site = None if (request.user.is_superuser or request.user.is_site_admin) else request.user.site
            ticket.save()
            AuditLog.objects.create(
                user=request.user,
                action='reception_uploaded',
                content_type='ReceptionTicket',
                object_id=ticket.pk,
                object_repr=str(ticket),
                details={'original_filename': ticket.original_filename},
                ip_address=_get_client_ip(request),
            )
            messages.success(request, 'Ticket recibido. Quedó pendiente de imputación.')
            return redirect('expenses:reception_queue')
    else:
        form = ReceptionTicketUploadForm()

    return render(request, 'expenses/reception_upload.html', {'form': form})


@login_required
def reception_queue(request):
    """Bandeja de tickets subidos por recepción pendientes de imputación."""
    if not _can_work_reception(request.user):
        return HttpResponseForbidden("No tenés permiso para ver tickets de recepción.")

    tickets = _site_scope_reception_tickets(
        request.user,
        ReceptionTicket.objects.select_related('uploaded_by', 'site', 'assigned_expense')
        .filter(status='pending_assignment'),
    )
    return render(request, 'expenses/reception_queue.html', {'tickets': tickets[:100]})


@login_required
def reception_assign(request, pk):
    """Imputa un ticket de recepción a protocolo/paciente/visita y crea el Expense."""
    if not _can_work_reception(request.user):
        return HttpResponseForbidden("No tenés permiso para imputar tickets.")

    reception_ticket = get_object_or_404(
        _site_scope_reception_tickets(
            request.user,
            ReceptionTicket.objects.select_related('uploaded_by', 'site', 'assigned_expense'),
        ),
        pk=pk,
        status='pending_assignment',
    )
    protocols = _protocols_for_user(request.user)

    if request.method == 'POST':
        raw_patient_id = request.POST.get('patient', '').strip()
        if not request.user.is_superuser and not request.user.is_site_admin and not request.user.site_id:
            return HttpResponseForbidden("No tenés un site asignado para imputar tickets.")

        form = ReceptionTicketAssignForm(request.POST)
        if form.is_valid():
            if not raw_patient_id or not raw_patient_id.isdigit():
                form.add_error(None, 'Seleccioná un paciente.')
                return render(request, 'expenses/reception_assign.html', {
                    'form': form,
                    'protocols': protocols,
                    'reception_ticket': reception_ticket,
                })

            patient_qs = Patient.objects.all()
            if not request.user.is_superuser and not request.user.is_site_admin:
                patient_qs = patient_qs.filter(protocol__site_id=request.user.site_id)
            patient = get_object_or_404(patient_qs, pk=raw_patient_id)
            visit_type = get_object_or_404(
                VisitType,
                pk=form.cleaned_data['visit_type_id'],
                protocol=patient.protocol,
            )
            expense, ticket = _create_expense_from_assignment(
                request, form, patient, visit_type, ticket_file=reception_ticket
            )
            if expense is None:
                return render(request, 'expenses/reception_assign.html', {
                    'form': form,
                    'protocols': protocols,
                    'reception_ticket': reception_ticket,
                })

            reception_ticket.status = 'assigned'
            reception_ticket.assigned_expense = expense
            reception_ticket.assigned_by = request.user
            reception_ticket.assigned_at = timezone.now()
            reception_ticket.save(update_fields=[
                'status', 'assigned_expense', 'assigned_by', 'assigned_at',
            ])
            AuditLog.objects.create(
                user=request.user,
                action='reception_assigned',
                content_type='ReceptionTicket',
                object_id=reception_ticket.pk,
                object_repr=str(reception_ticket),
                details={
                    'expense_id': expense.pk,
                    'patient_code': patient.patient_code,
                    'protocol': patient.protocol.code,
                    'visit_type': visit_type.name,
                },
                ip_address=_get_client_ip(request),
            )
            try:
                process_ocr_for_ticket.delay(ticket.pk)
            except Exception as e:
                logger.warning("No se pudo encolar tarea OCR: %s", e)
                expense.status = 'pending_review'
                expense.save(update_fields=['status'])
            messages.success(request, 'Ticket imputado. Revisá los datos extraídos por OCR.')
            return redirect('expenses:review', pk=expense.pk)
    else:
        form = ReceptionTicketAssignForm()

    return render(request, 'expenses/reception_assign.html', {
        'form': form,
        'protocols': protocols,
        'reception_ticket': reception_ticket,
    })


@login_required
def expense_list(request):
    """Lista de gastos del asistente autenticado."""
    user = request.user

    if _can_coordinate(user):
        qs = Expense.objects.select_related(
            'visit__patient__protocol', 'visit__visit_type', 'submitted_by'
        ).order_by('-created_at')
        qs = _site_scope_expenses(user, qs)
        title = 'Todos los gastos'
    else:
        qs = Expense.objects.filter(submitted_by=user).select_related(
            'visit__patient__protocol', 'visit__visit_type'
        ).order_by('-created_at')
        qs = _site_scope_expenses(user, qs)
        title = 'Mis gastos'

    return render(request, 'expenses/list.html', {
        'expenses': qs[:50],
        'title': title,
    })


# ─── Expense create ───────────────────────────────────────────────────────────

@login_required
def expense_create(request):
    """
    Wizard de carga: protocolo → paciente (HTMX) → tipo de visita (HTMX) + foto.
    POST: resuelve/crea la instancia Visit, valida que no esté bloqueada,
          crea el Expense con status ocr_pending y lanza OCR.
    """
    user = request.user
    protocols = _protocols_for_user(user)

    if request.method == 'POST':
        raw_patient_id = request.POST.get('patient', '').strip()

        # IDOR: paciente debe pertenecer al site del usuario
        if not user.is_superuser and not user.is_site_admin:
            if not user.site_id:
                return HttpResponseForbidden(
                    "No tenés un site asignado para cargar gastos."
                )
            if raw_patient_id and raw_patient_id.isdigit():
                cross_site = (
                    Patient.objects.filter(pk=raw_patient_id)
                    .exclude(protocol__site_id=user.site_id)
                    .exists()
                )
                if cross_site:
                    return HttpResponseForbidden(
                        "No tenés permiso para cargar gastos en este protocolo."
                    )

        form = ExpenseCreateForm(request.POST, request.FILES)
        if form.is_valid():
            visit_type_id = form.cleaned_data['visit_type_id']

            # Obtener paciente
            if not raw_patient_id or not raw_patient_id.isdigit():
                form.add_error(None, 'Seleccioná un paciente.')
                return render(request, 'expenses/create.html', {'form': form, 'protocols': protocols})
            patient_qs = Patient.objects.all()
            if not user.is_superuser and not user.is_site_admin:
                patient_qs = patient_qs.filter(protocol__site_id=user.site_id)
            patient = get_object_or_404(patient_qs, pk=raw_patient_id)

            # Obtener tipo de visita y verificar que pertenece al protocolo del paciente
            visit_type = get_object_or_404(
                VisitType, pk=visit_type_id, protocol=patient.protocol
            )

            expense, ticket = _create_expense_from_assignment(request, form, patient, visit_type)
            if expense is None:
                return render(request, 'expenses/create.html', {'form': form, 'protocols': protocols})

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
        _site_scope_expenses(
            request.user,
            Expense.objects.select_related('visit__patient__protocol', 'visit__visit_type', 'period'),
        ),
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
        if expense.status not in {'ocr_pending', 'pending_review'}:
            messages.error(
                request,
                'Este gasto ya salió de la etapa OCR y no puede reabrirse desde esta pantalla.',
            )
            return redirect('expenses:detail', pk=expense.pk)

        form = ExpenseReviewForm(request.POST, instance=expense)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.status = 'pending_review'
            updated.amount_usd = calculate_amount_usd(
                updated.amount, updated.currency, updated.exchange_rate_to_usd
            )
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
        _site_scope_expenses(
            request.user,
            Expense.objects.select_related(
                'visit__patient__protocol', 'visit__visit_type',
                'submitted_by', 'reviewed_by', 'period'
            ).prefetch_related('ticket_files'),
        ),
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
        _site_scope_expenses(request.user, Expense.objects.select_related('period')),
        pk=pk, status='observed',
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
            updated.amount_usd = calculate_amount_usd(
                updated.amount, updated.currency, updated.exchange_rate_to_usd
            )
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
    """Aprueba un gasto. Solo coordinadores (no admin). Retorna HTML parcial para HTMX."""
    if not _can_approve(request.user) or (request.user.is_superuser and not request.user.is_coordinator):
        return HttpResponseForbidden("Solo los coordinadores pueden aprobar gastos.")

    expense = get_object_or_404(
        _site_scope_expenses(request.user, Expense.objects.select_related('period')),
        pk=pk, status='pending_review',
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
def send_to_coordinator(request, pk):
    """Admin envía un gasto al coordinador (de pending_review a pending_coordinator). Solo admin."""
    if not _can_review(request.user):
        return HttpResponseForbidden("Solo admin puede enviar al coordinador.")

    expense = get_object_or_404(
        _site_scope_expenses(request.user, Expense.objects.select_related('period')),
        pk=pk, status='pending_review',
    )
    lock_response = _period_locked_response(expense)
    if lock_response:
        return lock_response

    prev_status = expense.status
    notes = request.POST.get('notes', '').strip()

    # Crear un estado intermedio o simplemente pasar a pending con nota
    expense.reviewed_by = request.user
    expense.reviewed_at = timezone.now()
    expense.review_notes = f'[REVISADO POR ADMIN] {notes}' if notes else '[REVISADO POR ADMIN - Listo para coordinador]'
    expense.save(update_fields=['reviewed_by', 'reviewed_at', 'review_notes'])

    AuditLog.objects.create(
        user=request.user,
        action='sent_to_coordinator',
        content_type='Expense',
        object_id=expense.pk,
        object_repr=str(expense),
        details={'prev_status': prev_status, 'notes': notes},
        ip_address=_get_client_ip(request),
    )

    return render(request, 'expenses/partials/expense_action_done.html', {
        'expense': expense,
        'action': 'sent_to_coordinator',
        'action_label': 'Enviado al Coordinador',
    })


@login_required
@require_POST
def reject_expense(request, pk):
    """Rechaza un gasto con comentario obligatorio. Retorna HTML parcial para HTMX."""
    if not _can_coordinate(request.user):
        return HttpResponseForbidden("No tenés permiso para rechazar gastos.")

    expense = get_object_or_404(
        _site_scope_expenses(request.user, Expense.objects.select_related('period')),
        pk=pk, status='pending_review',
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
        _site_scope_expenses(request.user, Expense.objects.select_related('period')),
        pk=pk, status='pending_review',
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

    expense = get_object_or_404(
        _site_scope_expenses(request.user, Expense.objects.all()), pk=pk
    )
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

    user = request.user
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

    periods = _site_scope_periods(user, periods)

    protocols = Protocol.objects.filter(is_active=True).order_by('code')
    if not user.is_superuser and not user.is_site_admin:
        protocols = protocols.filter(site=user.site) if user.site_id else protocols.none()

    protocol_id = request.GET.get('protocol')
    if protocol_id:
        periods = periods.filter(protocol_id=protocol_id)

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

    get_object_or_404(
        _site_scope_periods(request.user, ExpensePeriod.objects.all()), pk=pk
    )

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
        user = request.user
        if not user.is_superuser and not user.is_site_admin:
            if not user.site_id:
                return render(request, 'expenses/partials/patient_options.html', {'patients': []})
            protocol = Protocol.objects.filter(
                pk=protocol_id, site_id=user.site_id
            ).first()
            if not protocol:
                return render(request, 'expenses/partials/patient_options.html', {'patients': []})
        patients = Patient.objects.filter(
            protocol_id=protocol_id, is_active=True
        ).order_by('patient_code')
    return render(request, 'expenses/partials/patient_options.html', {'patients': patients})


@login_required
@require_GET
def htmx_visits_for_patient(request):
    """
    Retorna los tipos de visita del protocolo del paciente, anotados con
    su estado de bloqueo (is_locked=True si ya tiene un comprobante activo).
    """
    patient_id = request.GET.get('patient') or request.GET.get('patient_id')
    visit_type_rows = []
    if patient_id:
        user = request.user
        if not user.is_superuser and not user.is_site_admin:
            if not user.site_id:
                return render(request, 'expenses/partials/visit_options.html', {'visit_type_rows': []})
            patient = Patient.objects.select_related('protocol').filter(
                pk=patient_id, protocol__site_id=user.site_id
            ).first()
            if not patient:
                return render(request, 'expenses/partials/visit_options.html', {'visit_type_rows': []})
        else:
            patient = Patient.objects.select_related('protocol').filter(pk=patient_id).first()
            if not patient:
                return render(request, 'expenses/partials/visit_options.html', {'visit_type_rows': []})

        visit_types = VisitType.objects.filter(
            protocol=patient.protocol
        ).order_by('order')

        existing_visits = {
            v.visit_type_id: v
            for v in Visit.objects.filter(patient=patient).prefetch_related('expenses')
        }

        for vt in visit_types:
            visit = existing_visits.get(vt.pk)
            is_locked = bool(
                visit and visit.expenses.exclude(status='rejected').exists()
            )
            visit_type_rows.append({'visit_type': vt, 'is_locked': is_locked})

    return render(request, 'expenses/partials/visit_options.html',
                  {'visit_type_rows': visit_type_rows})


@login_required
@require_GET
def htmx_protocol_info(request):
    """Retorna un panel con el resumen del protocolo (sponsor, fase, tipos de visita)."""
    protocol_id = request.GET.get('protocol') or request.GET.get('protocol_id')
    if not protocol_id:
        return render(request, 'expenses/partials/protocol_info.html', {'protocol': None})

    user = request.user
    qs = Protocol.objects.filter(pk=protocol_id, is_active=True)
    if not user.is_superuser and not user.is_site_admin:
        if not user.site_id:
            return render(request, 'expenses/partials/protocol_info.html', {'protocol': None})
        qs = qs.filter(site_id=user.site_id)
    protocol = qs.first()
    if not protocol:
        return render(request, 'expenses/partials/protocol_info.html', {'protocol': None})

    visit_types = VisitType.objects.filter(protocol=protocol).order_by('order')
    return render(request, 'expenses/partials/protocol_info.html', {
        'protocol': protocol,
        'visit_types': visit_types,
    })


@login_required
@require_GET
def htmx_load_patients(request):
    """Carga dinámicamente los pacientes de un protocolo seleccionado."""
    protocol_id = request.GET.get('protocol_id')
    if not protocol_id:
        return HttpResponse('<option value="">Selecciona un protocolo primero</option>')

    user = request.user
    protocol_qs = Protocol.objects.filter(pk=protocol_id, is_active=True)
    if not user.is_superuser and not user.is_site_admin:
        if not user.site_id:
            return HttpResponse('<option value="">Sin acceso</option>')
        protocol_qs = protocol_qs.filter(site_id=user.site_id)

    protocol = protocol_qs.first()
    if not protocol:
        return HttpResponse('<option value="">Protocolo no encontrado</option>')

    patients = Patient.objects.filter(
        protocol=protocol,
        is_active=True
    ).order_by('patient_code').values('id', 'patient_code', 'initials')

    html = '<option value="">Selecciona un paciente</option>'
    for p in patients:
        label = f"{p['patient_code']}"
        if p['initials']:
            label += f" ({p['initials']})"
        pid = p['id']
        html += f'<option value="{pid}">{label}</option>'

    return HttpResponse(html)


@login_required
@require_GET
def htmx_load_visits(request):
    """Carga dinámicamente las visitas de un paciente y protocolo."""
    patient_id = request.GET.get('patient_id')
    protocol_id = request.GET.get('protocol_id')

    if not patient_id or not protocol_id:
        return HttpResponse('<option value="">Selecciona paciente y protocolo</option>')

    user = request.user
    patient = Patient.objects.select_related('protocol').filter(
        pk=patient_id,
        protocol_id=protocol_id,
        is_active=True
    ).first()

    if not patient:
        return HttpResponse('<option value="">Paciente no encontrado</option>')

    # Verificar acceso del usuario al protocolo
    if not user.is_superuser and not user.is_site_admin:
        if patient.protocol.site_id != user.site_id:
            return HttpResponse('<option value="">Sin acceso a este protocolo</option>')

    # Cargar o crear visitas para este paciente
    visit_types = VisitType.objects.filter(protocol=patient.protocol).order_by('order')
    visits = Visit.objects.filter(patient=patient)
    existing_visit_type_ids = set(visits.values_list('visit_type_id', flat=True))

    html = '<option value="">Selecciona una visita</option>'
    for vt in visit_types:
        visit = visits.filter(visit_type_id=vt.id).first()
        if not visit:
            # Crear visita programada para este visit_type
            visit = Visit.objects.create(
                patient=patient,
                visit_type=vt,
                scheduled_date=timezone.now().date(),
                created_by=user
            )

        label = f"{vt.name} ({visit.scheduled_date.strftime('%d/%m/%Y')})"
        if visit.status != 'scheduled':
            label += f" [{visit.get_status_display()}]"

        # Marcar como deshabilitada si tiene gastos no-rechazados
        disabled = visit.expenses.exclude(status='rejected').exists()
        disabled_attr = ' disabled' if disabled else ''
        html += f'<option value="{visit.id}"{disabled_attr}>{label}</option>'

    return HttpResponse(html)
