import logging
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET

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


@login_required
def reports_index(request):
    """Selector de reportes: protocolo, paciente y período."""
    if not _can_report(request.user):
        return HttpResponseForbidden("No tenés permiso para generar reportes.")

    protocols = Protocol.objects.filter(is_active=True).order_by('code')
    return render(request, 'reports/index.html', {'protocols': protocols})


@login_required
def patient_pdf(request, patient_id, period_id):
    """Genera y descarga el PDF de rendición de un paciente en un período."""
    if not _can_report(request.user):
        return HttpResponseForbidden("No tenés permiso para generar reportes.")

    patient = get_object_or_404(Patient, pk=patient_id)
    period = get_object_or_404(ExpensePeriod, pk=period_id, protocol=patient.protocol)

    try:
        from .generators import generate_patient_pdf
        pdf_bytes = generate_patient_pdf(patient, period, request.user)
    except ValueError as e:
        return render(request, 'reports/index.html', {
            'protocols': Protocol.objects.filter(is_active=True).order_by('code'),
            'error': str(e),
        })
    except Exception as e:
        logger.exception("Error generando PDF de paciente %s: %s", patient_id, e)
        return render(request, 'reports/index.html', {
            'protocols': Protocol.objects.filter(is_active=True).order_by('code'),
            'error': f'Error al generar el PDF: {e}',
        })

    filename = f"viaticos_{patient.patient_code}_{patient.protocol.code}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def site_pdf(request, protocol_id, period_id):
    """Genera y descarga el PDF consolidado del protocolo en un período."""
    if not _can_report(request.user):
        return HttpResponseForbidden("No tenés permiso para generar reportes.")

    protocol = get_object_or_404(Protocol, pk=protocol_id)
    period = get_object_or_404(ExpensePeriod, pk=period_id, protocol=protocol)

    try:
        from .generators import generate_site_pdf
        pdf_bytes = generate_site_pdf(protocol, period, request.user)
    except ValueError as e:
        return render(request, 'reports/index.html', {
            'protocols': Protocol.objects.filter(is_active=True).order_by('code'),
            'error': str(e),
        })
    except Exception as e:
        logger.exception("Error generando PDF consolidado %s: %s", protocol_id, e)
        return render(request, 'reports/index.html', {
            'protocols': Protocol.objects.filter(is_active=True).order_by('code'),
            'error': f'Error al generar el PDF: {e}',
        })

    filename = f"consolidado_{protocol.code}_{period.name.replace(' ', '_')}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def site_excel(request, protocol_id, period_id):
    """Genera y descarga el Excel consolidado del protocolo en un período."""
    if not _can_report(request.user):
        return HttpResponseForbidden("No tenés permiso para generar reportes.")

    protocol = get_object_or_404(Protocol, pk=protocol_id)
    period = get_object_or_404(ExpensePeriod, pk=period_id, protocol=protocol)

    try:
        from .generators import generate_site_excel
        xlsx_bytes = generate_site_excel(protocol, period, request.user)
    except ValueError as e:
        return render(request, 'reports/index.html', {
            'protocols': Protocol.objects.filter(is_active=True).order_by('code'),
            'error': str(e),
        })
    except Exception as e:
        logger.exception("Error generando Excel %s: %s", protocol_id, e)
        return render(request, 'reports/index.html', {
            'protocols': Protocol.objects.filter(is_active=True).order_by('code'),
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
    patient_id = request.GET.get('patient')
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
