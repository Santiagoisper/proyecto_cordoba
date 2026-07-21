from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import Patient, Visit
from .forms import PatientForm, VisitForm


def _scoped_patients(user):
    """
    QuerySet de pacientes visible para el usuario.
    Superusuario y site_admin ven todo; el resto solo su site.
    Usuarios operativos sin site asignado no ven ningún paciente (IDOR).
    """
    qs = Patient.objects.select_related('protocol')
    if user.is_superuser or user.is_site_admin:
        return qs
    if not user.site_id:
        return qs.none()
    return qs.filter(protocol__site_id=user.site_id)


def _scoped_visits(user):
    """QuerySet de visitas visible para el usuario (misma regla que pacientes)."""
    qs = Visit.objects.select_related('patient__protocol', 'visit_type')
    if user.is_superuser or user.is_site_admin:
        return qs
    if not user.site_id:
        return qs.none()
    return qs.filter(patient__protocol__site_id=user.site_id)


@login_required
def patient_create(request):
    """Crear nuevo paciente."""
    if not (request.user.is_superuser or request.user.is_site_admin):
        return HttpResponseForbidden("No tenés permiso para crear pacientes.")

    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            patient = form.save(commit=False)
            patient.created_by = request.user
            patient.save()
            messages.success(request, f"Paciente {patient.patient_code} creado exitosamente.")
            return redirect('patients:patient_detail', pk=patient.pk)
    else:
        form = PatientForm()

    return render(request, 'patients/patient_form.html', {'form': form, 'title': 'Crear paciente'})


@login_required
def patient_detail(request, pk):
    """Ver detalles del paciente y sus visitas. Restringido al site del usuario."""
    patient = get_object_or_404(_scoped_patients(request.user), pk=pk)
    visits = patient.visits.select_related('visit_type').order_by('-scheduled_date')
    return render(request, 'patients/patient_detail.html', {'patient': patient, 'visits': visits})


@login_required
def patient_edit(request, pk):
    """Editar paciente."""
    if not (request.user.is_superuser or request.user.is_site_admin):
        return HttpResponseForbidden("No tenés permiso para editar pacientes.")
    patient = get_object_or_404(_scoped_patients(request.user), pk=pk)

    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            messages.success(request, "Paciente actualizado exitosamente.")
            return redirect('patients:patient_detail', pk=patient.pk)
    else:
        form = PatientForm(instance=patient)

    return render(request, 'patients/patient_form.html', {'form': form, 'title': 'Editar paciente', 'patient': patient})


@login_required
def visit_create(request, patient_pk=None):
    """Crear nueva visita para un paciente."""
    if not (request.user.is_superuser or request.user.is_site_admin or request.user.is_coordinator):
        return HttpResponseForbidden("No tenés permiso para crear visitas.")

    patient = None
    if patient_pk:
        patient = get_object_or_404(_scoped_patients(request.user), pk=patient_pk)

    if request.method == 'POST':
        form = VisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            # El paciente elegido en el form también debe pertenecer al site del usuario.
            if not _scoped_patients(request.user).filter(pk=visit.patient_id).exists():
                return HttpResponseForbidden("No tenés permiso para crear visitas de este paciente.")
            visit.created_by = request.user
            visit.save()
            messages.success(request, f"Visita creada exitosamente para {visit.patient}.")
            return redirect('patients:patient_detail', pk=visit.patient.pk)
    else:
        form = VisitForm()
        if patient:
            form.fields['patient'].initial = patient

    return render(request, 'patients/visit_form.html', {'form': form, 'patient': patient, 'title': 'Crear visita'})


@login_required
def visit_edit(request, pk):
    """Editar visita."""
    if not (request.user.is_superuser or request.user.is_site_admin or request.user.is_coordinator):
        return HttpResponseForbidden("No tenés permiso para editar visitas.")
    visit = get_object_or_404(_scoped_visits(request.user), pk=pk)

    if request.method == 'POST':
        form = VisitForm(request.POST, instance=visit)
        if form.is_valid():
            form.save()
            messages.success(request, "Visita actualizada exitosamente.")
            return redirect('patients:patient_detail', pk=visit.patient.pk)
    else:
        form = VisitForm(instance=visit)

    return render(request, 'patients/visit_form.html', {'form': form, 'visit': visit, 'title': 'Editar visita'})
