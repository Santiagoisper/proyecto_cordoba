from django.db import models
from django.conf import settings


class Site(models.Model):
    """
    Site de investigación (centro clínico).
    Permite la arquitectura multi-site futura.
    Los protocolos se ejecutan en uno o más sites.
    """
    code = models.CharField(max_length=20, unique=True, help_text="Ej: CINME-01")
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=400, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Argentina')
    is_active = models.BooleanField(default=True)

    contact_name = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']
        verbose_name = 'Site de investigación'
        verbose_name_plural = 'Sites de investigación'

    def __str__(self):
        return f"{self.code} — {self.name}"


class Protocol(models.Model):
    """
    Protocolo de ensayo clínico.
    Un protocol puede tener múltiples pacientes y visitas.
    """
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='protocols',
        help_text="Site de investigación donde se ejecuta este protocolo (multi-site futuro)"
    )
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=300)
    sponsor = models.CharField(max_length=200, blank=True)
    phase = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    currency = models.CharField(max_length=3, default='ARS', help_text="ISO 4217")
    max_daily_meals = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Tope diario para comidas en la moneda del protocolo"
    )
    max_daily_transport = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Tope diario para transporte"
    )
    max_daily_accommodation = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Tope diario para alojamiento"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='protocols_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    external_protocol_id = models.CharField(max_length=100, blank=True, null=True,
        help_text="ID en Alpha CR para futura integración")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Protocolo'
        verbose_name_plural = 'Protocolos'

    def __str__(self):
        return f"{self.code} — {self.name}"


class VisitType(models.Model):
    """
    Tipos de visita para un protocolo específico.
    Ej: Screening, V1, V2, End of Study, Unscheduled.
    """
    protocol = models.ForeignKey(
        Protocol, on_delete=models.CASCADE, related_name='visit_types'
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    order = models.PositiveIntegerField(default=0)
    window_before_days = models.PositiveIntegerField(
        default=3,
        help_text="Días antes de la visita en que se aceptan tickets"
    )
    window_after_days = models.PositiveIntegerField(
        default=3,
        help_text="Días después de la visita en que se aceptan tickets"
    )

    class Meta:
        ordering = ['order']
        unique_together = ['protocol', 'code']
        verbose_name = 'Tipo de visita'
        verbose_name_plural = 'Tipos de visita'

    def __str__(self):
        return f"{self.protocol.code} — {self.name}"
