from django.db import models


class ChannelContact(models.Model):
    """
    Remitente autorizado de un canal de ingesta.
    Solo teléfonos de PERSONAL del site (asistentes, coordinadores).
    Nunca cargar acá teléfonos de pacientes: los comprobantes que llegan
    por WhatsApp los envía el staff, no el paciente.
    """
    CHANNEL_CHOICES = [
        ('whatsapp', 'WhatsApp'),
    ]

    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='whatsapp')
    phone = models.CharField(
        max_length=30, unique=True,
        help_text="Número internacional sin '+', tal como lo reporta Meta. Ej: 5493511234567",
    )
    display_name = models.CharField(max_length=200, blank=True)
    site = models.ForeignKey(
        'protocols.Site',
        on_delete=models.CASCADE,
        related_name='channel_contacts',
        help_text="Site al que se imputan los tickets recibidos de este número",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Contacto de canal'
        verbose_name_plural = 'Contactos de canal'

    def __str__(self):
        return f"{self.display_name or self.phone} → {self.site.code}"


class InboundMessage(models.Model):
    """
    Mensaje entrante crudo de un canal externo.
    Sirve como registro de idempotencia (external_id único) y auditoría
    de todo lo que llegó, incluso lo ignorado.
    """
    STATUS_CHOICES = [
        ('received', 'Recibido'),
        ('processed', 'Procesado'),
        ('ignored', 'Ignorado'),
        ('failed', 'Fallido'),
    ]

    channel = models.CharField(max_length=20, default='whatsapp')
    external_id = models.CharField(
        max_length=200, unique=True,
        help_text="ID del mensaje en el canal (wamid...) para no procesar dos veces",
    )
    sender = models.CharField(max_length=30, blank=True)
    message_type = models.CharField(max_length=30, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    error = models.TextField(blank=True)

    reception_ticket = models.ForeignKey(
        'expenses.ReceptionTicket',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inbound_messages',
    )

    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Mensaje entrante'
        verbose_name_plural = 'Mensajes entrantes'

    def __str__(self):
        return f"{self.channel} {self.external_id} ({self.get_status_display()})"
