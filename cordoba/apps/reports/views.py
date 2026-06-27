import logging
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from apps.protocols.models import Protocol
from apps.patients.models import Patient
from apps.expenses.models import ExpensePeriod

logger = logging.getLogger(__name__)


def _can_report(user):
    """Coordinadores, admins y auditores pueden generar reportes."""
    return (
        user.is_superuser or user.is_site_admin
        or user.is_coordinator or user.is_auditor
    )


def _protocols_ctx():
    return Protocol.objects.filter(is_active=True).order_by('code')


@login_required
def reports_index(request):
    """Selector de reportes: protocolo, paciente y período."""
    if not _can_report(request.user):
        return HttpResponseForbidden("No tenés permiso para generar reportes.")

    return render(request, 'reports/index.html', {'protocols': _protocols_ctx()})


@login_required
@require_POST
def patient_pdf(request):
    """
    POST — Genera y descarga el PDF de rendición de un paciente en un período.
    Recibe patient_id y period_id en el cuerpo del formulario (CSRF protegido).
    La mutación de estado (approved/settled → exported) solo ocurre vía POST.
    """
    if not _can_report(request.user):
        return HttpResponseForbidden("No tenés permiso para generar reportes.")

    patient_id = request.POST.get('patient_id')
    period_id = request.POST.get('period_id')

    if not patient_id or not period_id:
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': 'Seleccioná un paciente y un período antes de generar el reporte.',
        })

    patient = get_object_or_404(Patient, pk=patient_id)
    period = get_object_or_404(ExpensePeriod, pk=period_id, protocol=patient.protocol)

    try:
        from .generators import generate_patient_pdf
        pdf_bytes = generate_patient_pdf(patient, period, request.user)
    except ValueError as e:
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': str(e),
        })
    except Exception as e:
        logger.exception("Error generando PDF de paciente %s: %s", patient_id, e)
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': f'Error al generar el PDF: {e}',
        })

    filename = f"viaticos_{patient.patient_code}_{patient.protocol.code}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def site_pdf(request):
    """
    POST — Genera y descarga el PDF consolidado del protocolo en un período.
    Recibe protocol_id y period_id en el cuerpo del formulario (CSRF protegido).
    """
    if not _can_report(request.user):
        return HttpResponseForbidden("No tenés permiso para generar reportes.")

    protocol_id = request.POST.get('protocol_id')
    period_id = request.POST.get('period_id')

    if not protocol_id or not period_id:
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': 'Seleccioná un protocolo y un período antes de generar el reporte.',
        })

    protocol = get_object_or_404(Protocol, pk=protocol_id)
    period = get_object_or_404(ExpensePeriod, pk=period_id, protocol=protocol)

    try:
        from .generators import generate_site_pdf
        pdf_bytes = generate_site_pdf(protocol, period, request.user)
    except ValueError as e:
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': str(e),
        })
    except Exception as e:
        logger.exception("Error generando PDF consolidado %s: %s", protocol_id, e)
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': f'Error al generar el PDF: {e}',
        })

    filename = f"consolidado_{protocol.code}_{period.name.replace(' ', '_')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def site_excel(request):
    """
    POST — Genera y descarga el Excel consolidado del protocolo en un período.
    Recibe protocol_id y period_id en el cuerpo del formulario (CSRF protegido).
    """
    if not _can_report(request.user):
        return HttpResponseForbidden("No tenés permiso para generar reportes.")

    protocol_id = request.POST.get('protocol_id')
    period_id = request.POST.get('period_id')

    if not protocol_id or not period_id:
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': 'Seleccioná un protocolo y un período antes de generar el reporte.',
        })

    protocol = get_object_or_404(Protocol, pk=protocol_id)
    period = get_object_or_404(ExpensePeriod, pk=period_id, protocol=protocol)

    try:
        from .generators import generate_site_excel
        xlsx_bytes = generate_site_excel(protocol, period, request.user)
    except ValueError as e:
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': str(e),
        })
    except Exception as e:
        logger.exception("Error generando Excel %s: %s", protocol_id, e)
        return render(request, 'reports/index.html', {
            'protocols': _protocols_ctx(),
            'error': f'Error al generar el Excel: {e}',
        })

    filename = f"consolidado_{protocol.code}_{period.name.replace(' ', '_')}.xlsx"
    response = HttpResponse(
        xlsx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─── HTMX chained selects ────────────────────────────────────────────────────

@login_required
@require_GET
def htmx_periods_for_protocol(request):
    """Períodos de rendición de un protocolo (para selector de consolidado)."""
    if not _can_report(request.user):
        return HttpResponseForbidden()
    protocol_id = request.GET.get('protocol')
    periods = []
    if protocol_id:
        periods = ExpensePeriod.objects.filter(
            protocol_id=protocol_id
        ).order_by('-date_from')
    return render(request, 'reports/partials/period_options.html', {'periods': periods})


@login_required
@require_GET
def htmx_patients_for_protocol(request):
    """Pacientes activos de un protocolo (para selector de PDF por paciente)."""
    if not _can_report(request.user):
        return HttpResponseForbidden()
    protocol_id = request.GET.get('protocol')
    patients = []
    if protocol_id:
        patients = Patient.objects.filter(
            protocol_id=protocol_id, is_active=True
        ).order_by('patient_code')
    return render(request, 'reports/partials/patient_options.html', {'patients': patients})


@login_required
@require_GET
def htmx_periods_for_patient(request):
    """Períodos disponibles para un paciente (filtra por protocolo del paciente)."""
    if not _can_report(request.user):
        return HttpResponseForbidden()
    patient_id = request.GET.get('patient_id')
    periods = []
    if patient_id:
        try:
            patient = Patient.objects.select_related('protocol').get(pk=patient_id)
            periods = ExpensePeriod.objects.filter(
                protocol=patient.protocol
            ).order_by('-date_from')
        except Patient.DoesNotExist:
            pass
    return render(request, 'reports/partials/period_options.html', {'periods': periods})
