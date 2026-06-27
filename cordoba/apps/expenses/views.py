import json
import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.protocols.models import Protocol
from apps.patients.models import Patient, Visit

from .models import Expense, TicketFile, AuditLog
from .forms import ExpenseCreateForm, ExpenseReviewForm
from .tasks import process_ocr_for_ticket

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@login_required
def expense_list(request):
    """Lista de gastos del asistente autenticado."""
    user = request.user

    if user.is_superuser or user.is_site_admin or user.is_coordinator:
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


@login_required
def expense_create(request):
    """
    Paso 1: selección de protocolo → paciente (HTMX) → visita (HTMX) + foto del ticket.
    POST: crea el Expense con status ocr_pending, sube el archivo y lanza OCR.
    """
    protocols = Protocol.objects.filter(is_active=True).order_by('code')

    if request.method == 'POST':
        form = ExpenseCreateForm(request.POST, request.FILES)
        if form.is_valid():
            visit_id = form.cleaned_data['visit']
            visit = get_object_or_404(Visit, pk=visit_id)

            # Crear el gasto con status inicial ocr_pending
            expense = Expense.objects.create(
                visit=visit,
                category=form.cleaned_data['category'],
                amount=0,
                expense_date=form.cleaned_data['expense_date'],
                description=form.cleaned_data['description'],
                status='ocr_pending',
                submitted_by=request.user,
            )

            # Guardar el archivo del ticket
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

            # Registrar en AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='created',
                content_type='Expense',
                object_id=expense.pk,
                object_repr=str(expense),
                details={
                    'visit_id': visit.pk,
                    'category': expense.category,
                    'ticket_file_id': ticket.pk,
                },
                ip_address=_get_client_ip(request),
            )

            # Lanzar tarea OCR (síncrona en dev con TASK_ALWAYS_EAGER, asíncrona en prod)
            try:
                process_ocr_for_ticket.delay(ticket.pk)
            except Exception as e:
                logger.warning("No se pudo encolar tarea OCR: %s", e)
                expense.status = 'pending_review'
                expense.save(update_fields=['status'])

            messages.success(request, 'Ticket cargado correctamente. Revisá los datos extraídos.')
            return redirect('expenses:review', pk=expense.pk)

        # Form inválido
        return render(request, 'expenses/create.html', {
            'form': form,
            'protocols': protocols,
        })

    form = ExpenseCreateForm()
    return render(request, 'expenses/create.html', {
        'form': form,
        'protocols': protocols,
    })


@login_required
def expense_review(request, pk):
    """
    Paso 2: pantalla de revisión OCR.
    Muestra campos extraídos con badges de confianza.
    El asistente puede corregir y confirmar.
    """
    expense = get_object_or_404(
        Expense.objects.select_related('visit__patient__protocol', 'visit__visit_type'),
        pk=pk,
    )

    # Solo el asistente que cargó el gasto, coordinadores y admins pueden ver
    if not (
        request.user == expense.submitted_by
        or request.user.is_superuser
        or request.user.is_site_admin
        or request.user.is_coordinator
    ):
        return HttpResponseForbidden("No tenés permiso para ver este gasto.")

    ticket = expense.ticket_files.first()
    ocr_extracted = expense.ocr_extracted
    ocr_confidence = expense.ocr_confidence_per_field

    if request.method == 'POST':
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
                details={
                    'action': 'ocr_review_confirmed',
                    'amount': str(updated.amount),
                    'vendor': updated.vendor,
                    'expense_date': str(updated.expense_date),
                },
                ip_address=_get_client_ip(request),
            )

            messages.success(request, 'Gasto confirmado y enviado para revisión del coordinador.')
            return redirect('expenses:list')

    else:
        # Pre-completar form con datos OCR si están disponibles
        initial = {
            'amount': ocr_extracted.get('amount'),
            'expense_date': ocr_extracted.get('date') or expense.expense_date,
            'vendor': ocr_extracted.get('vendor') or expense.vendor,
        }
        form = ExpenseReviewForm(instance=expense, initial=initial)

    def _badge(field):
        confidence = ocr_confidence.get(field, 0.0)
        if confidence >= 0.7:
            return {
                'css': 'bg-green-100 text-green-700 border-green-200',
                'label': f'Confianza alta ({confidence:.0%})',
            }
        elif confidence >= 0.4:
            return {
                'css': 'bg-amber-100 text-amber-700 border-amber-200',
                'label': f'Confianza media ({confidence:.0%})',
            }
        elif confidence > 0:
            return {
                'css': 'bg-red-100 text-red-600 border-red-200',
                'label': f'Confianza baja ({confidence:.0%})',
            }
        else:
            return {
                'css': 'bg-slate-100 text-slate-500 border-slate-200',
                'label': 'Sin dato OCR — completar manualmente',
            }

    badges = {
        'amount': _badge('amount'),
        'date': _badge('date'),
        'vendor': _badge('vendor'),
        'cuit': _badge('cuit'),
        'receipt': _badge('receipt'),
    }

    is_mock = expense.ocr_raw_data.get('mock', False) if expense.ocr_raw_data else True

    return render(request, 'expenses/review.html', {
        'expense': expense,
        'ticket': ticket,
        'form': form,
        'ocr_extracted': ocr_extracted,
        'ocr_confidence': ocr_confidence,
        'is_mock': is_mock,
        'badges': badges,
        'cuit': ocr_extracted.get('cuit', ''),
        'receipt_number': ocr_extracted.get('receipt_number', ''),
    })


# ─── HTMX endpoints ──────────────────────────────────────────────────────────

@login_required
@require_GET
def htmx_patients_for_protocol(request):
    """
    Devuelve HTML con opciones de <select> para pacientes de un protocolo.
    Usado por HTMX en el formulario de carga.
    """
    protocol_id = request.GET.get('protocol') or request.GET.get('protocol_id')
    patients = []
    if protocol_id:
        patients = Patient.objects.filter(
            protocol_id=protocol_id,
            is_active=True
        ).order_by('patient_code')

    return render(request, 'expenses/partials/patient_options.html', {
        'patients': patients,
    })


@login_required
@require_GET
def htmx_visits_for_patient(request):
    """
    Devuelve HTML con opciones de <select> para visitas de un paciente.
    Usado por HTMX en el formulario de carga.
    """
    patient_id = request.GET.get('patient') or request.GET.get('patient_id')
    visits = []
    if patient_id:
        visits = Visit.objects.filter(
            patient_id=patient_id,
        ).select_related('visit_type').order_by('scheduled_date')

    return render(request, 'expenses/partials/visit_options.html', {
        'visits': visits,
    })
