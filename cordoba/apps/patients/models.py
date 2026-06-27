from datetime import timedelta
from django.db import models
from django.conf import settings
from apps.protocols.models import Protocol, VisitType


class Patient(models.Model):
    """
    Paciente en un ensayo clínico.
    NUNCA almacenar nombre completo aquí. Solo código e iniciales.
    Los datos identificatorios viven en Alpha CR (futura integración).
    """
    protocol = models.ForeignKey(
        Protocol, on_delete=models.PROTECT, related_name='patients'
    )
    patient_code = models.CharField(
        max_length=50,
        help_text="Código de identificación del paciente. Ej: 001-001"
    )
    initials = models.CharField(
        max_length=5, blank=True,
        help_text="Iniciales del paciente (referencia interna, no identificatorias)"
    )
    is_active = models.BooleanField(default=True)
    enrolled_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='patients_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    external_patient_id = models.CharField(max_length=100, blank=True, null=True,
        help_text="ID en Alpha CR para futura integración")

    class Meta:
        ordering = ['protocol', 'patient_code']
        unique_together = ['protocol', 'patient_code']
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'

    def __str__(self):
        return f"{self.protocol.code} / {self.patient_code}"


class Visit(models.Model):
    """
    Visita concreta de un paciente (instancia de VisitType).
    """
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name='visits'
    )
    visit_type = models.ForeignKey(
        VisitType, on_delete=models.PROTECT, related_name='visits'
    )
    scheduled_date = models.DateField()
    actual_date = models.DateField(null=True, blank=True)

    STATUS_CHOICES = [
        ('scheduled', 'Programada'),
        ('completed', 'Realizada'),
        ('cancelled', 'Cancelada'),
        ('missed', 'No asistió'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='visits_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    external_visit_id = models.CharField(max_length=100, blank=True, null=True,
        help_text="ID en Alpha CR para futura integración")

    class Meta:
        ordering = ['scheduled_date']
        verbose_name = 'Visita'
        verbose_name_plural = 'Visitas'

    def __str__(self):
        return f"{self.patient} — {self.visit_type.name} ({self.scheduled_date})"

    def get_ticket_window_start(self):
        """Fecha mínima aceptable de un ticket para esta visita."""
        base = self.actual_date or self.scheduled_date
        return base - timedelta(days=self.visit_type.window_before_days)

    def get_ticket_window_end(self):
        """Fecha máxima aceptable de un ticket para esta visita."""
        base = self.actual_date or self.scheduled_date
        return base + timedelta(days=self.visit_type.window_after_days)
