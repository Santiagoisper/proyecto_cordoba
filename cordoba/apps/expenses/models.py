from django.db import models
from django.conf import settings
from apps.patients.models import Visit, Patient
from apps.protocols.models import Protocol


class ExpensePeriod(models.Model):
    """
    Período de rendición. Agrupa gastos para generación de PDF y cierre.
    Un período cerrado no puede modificarse.
    """
    protocol = models.ForeignKey(
        Protocol, on_delete=models.PROTECT, related_name='expense_periods'
    )
    name = models.CharField(max_length=100, help_text="Ej: 'Período Q1 2025'")
    date_from = models.DateField()
    date_to = models.DateField()

    STATUS_CHOICES = [
        ('open', 'Abierto'),
        ('closed', 'Cerrado'),
        ('exported', 'Exportado'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')

    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='periods_closed'
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='periods_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_from']
        verbose_name = 'Período de rendición'
        verbose_name_plural = 'Períodos de rendición'

    def __str__(self):
        return f"{self.protocol.code} — {self.name}"


class ProtocolBudgetItem(models.Model):
    """
    Presupuesto operativo por protocolo, categoría y opcionalmente visita.
    Se expresa en USD para poder comparar tickets cargados en ARS/USD.
    """
    protocol = models.ForeignKey(
        Protocol, on_delete=models.CASCADE, related_name='budget_items'
    )
    visit_type = models.ForeignKey(
        'protocols.VisitType',
        on_delete=models.CASCADE,
        related_name='budget_items',
        null=True,
        blank=True,
        help_text="Si queda vacío aplica a todas las visitas del protocolo",
    )
    category = models.CharField(max_length=20, choices=[
        ('transport', 'Transporte'),
        ('meals', 'Comidas'),
        ('accommodation', 'Alojamiento'),
        ('other', 'Otro'),
    ])
    amount_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Monto máximo permitido en USD",
    )
    notes = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='budget_items_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['protocol__code', 'category', 'visit_type__order']
        verbose_name = 'Ítem de presupuesto'
        verbose_name_plural = 'Ítems de presupuesto'
        unique_together = ['protocol', 'visit_type', 'category']

    def __str__(self):
        scope = self.visit_type.name if self.visit_type_id else 'Todas las visitas'
        return f"{self.protocol.code} — {scope} — {self.get_category_display()}: USD {self.amount_usd}"


class Expense(models.Model):
    """
    Gasto individual vinculado a una visita de un paciente.
    Corazón del sistema de viáticos.
    """
    CATEGORY_CHOICES = [
        ('transport', 'Transporte'),
        ('meals', 'Comidas'),
        ('accommodation', 'Alojamiento'),
        ('other', 'Otro'),
    ]

    STATUS_CHOICES = [
        ('ocr_pending', 'Procesando OCR'),
        ('pending_review', 'Pendiente de revisión'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('observed', 'Observado'),
        ('settled', 'Liquidado'),
        ('exported', 'Exportado'),
    ]

    visit = models.ForeignKey(
        Visit, on_delete=models.PROTECT, related_name='expenses'
    )
    period = models.ForeignKey(
        ExpensePeriod, on_delete=models.PROTECT,
        related_name='expenses', null=True, blank=True
    )

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='ARS')
    exchange_rate_to_usd = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Cantidad de moneda original equivalente a 1 USD. Ej: ARS por USD.",
    )
    amount_usd = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monto convertido a USD para control contra budget.",
    )
    expense_date = models.DateField(help_text="Fecha del gasto según el ticket")
    description = models.CharField(max_length=500, blank=True)
    vendor = models.CharField(max_length=200, blank=True, help_text="Nombre del comercio o proveedor")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ocr_pending')

    # Datos crudos del OCR (incluye extracted + confidence como JSON anidado)
    ocr_raw_data = models.JSONField(null=True, blank=True, help_text="Datos del OCR (extracted + confidence)")
    ocr_confidence = models.FloatField(null=True, blank=True, help_text="Confianza global del OCR (0-1)")
    ocr_processed_at = models.DateTimeField(null=True, blank=True)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='expenses_submitted'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='expenses_reviewed'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']
        verbose_name = 'Gasto'
        verbose_name_plural = 'Gastos'
        indexes = [
            models.Index(fields=['status'], name='expense_status_idx'),
            models.Index(fields=['expense_date'], name='expense_date_idx'),
            models.Index(fields=['status', 'expense_date'], name='expense_status_date_idx'),
        ]

    def __str__(self):
        return (
            f"{self.visit.patient} — {self.get_category_display()} "
            f"${self.amount} ({self.expense_date})"
        )

    @property
    def ocr_extracted(self) -> dict:
        """Devuelve el dict de campos extraídos por OCR."""
        if self.ocr_raw_data and 'extracted' in self.ocr_raw_data:
            return self.ocr_raw_data['extracted']
        return {}

    @property
    def ocr_confidence_per_field(self) -> dict:
        """Devuelve el dict de confianza por campo."""
        if self.ocr_raw_data and 'confidence' in self.ocr_raw_data:
            return self.ocr_raw_data['confidence']
        return {}

    def confidence_badge(self, field: str) -> str:
        """Retorna clase CSS del badge según nivel de confianza del campo."""
        confidence = self.ocr_confidence_per_field.get(field, 0.0)
        if confidence >= 0.7:
            return 'green'
        elif confidence >= 0.4:
            return 'yellow'
        else:
            return 'red'


class TicketFile(models.Model):
    """
    Archivo de ticket (foto/scan) asociado a un gasto.
    Separado del gasto para permitir múltiples archivos por gasto.
    """
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name='ticket_files'
    )
    file = models.FileField(upload_to='tickets/%Y/%m/', help_text="Foto o scan del ticket (imagen o PDF)")
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True, help_text="Tamaño en bytes")
    mime_type = models.CharField(max_length=100, blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='ticket_files_uploaded'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    ocr_task_id = models.CharField(max_length=100, blank=True,
        help_text="ID de la tarea Celery de OCR")
    ocr_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pendiente'),
            ('processing', 'Procesando'),
            ('done', 'Completado'),
            ('failed', 'Fallido'),
        ],
        default='pending'
    )

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Archivo de ticket'
        verbose_name_plural = 'Archivos de ticket'

    def __str__(self):
        return f"Ticket de {self.expense} — {self.uploaded_at:%Y-%m-%d %H:%M}"


class ReceptionTicket(models.Model):
    """
    Comprobante subido en recepción, todavía sin imputar a protocolo/paciente/visita.
    El asistente lo revisa y lo convierte en Expense.
    """
    STATUS_CHOICES = [
        ('pending_assignment', 'Pendiente de imputación'),
        ('assigned', 'Imputado'),
        ('discarded', 'Descartado'),
    ]

    file = models.FileField(
        upload_to='reception_tickets/%Y/%m/',
        help_text="Foto o scan del ticket recibido en recepción",
    )
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending_assignment',
    )

    site = models.ForeignKey(
        'protocols.Site',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reception_tickets',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reception_tickets_uploaded',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    assigned_expense = models.OneToOneField(
        Expense,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reception_ticket',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reception_tickets_assigned',
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Ticket de recepción'
        verbose_name_plural = 'Tickets de recepción'

    def __str__(self):
        return f"Ticket recepción #{self.pk} — {self.get_status_display()}"


class AuditLog(models.Model):
    """
    Log de auditoría inmutable. GCP-compliant.
    NUNCA actualizar ni borrar registros de esta tabla.
    """
    ACTION_CHOICES = [
        ('created', 'Creado'),
        ('updated', 'Actualizado'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('observed', 'Observado'),
        ('corrected', 'Corregido'),
        ('exported', 'Exportado'),
        ('sent_to_coordinator', 'Enviado al coordinador'),
        ('ocr_completed', 'OCR completado'),
        ('ocr_failed', 'OCR fallido'),
        ('period_closed', 'Período cerrado'),
        ('pdf_generated', 'PDF generado'),
        ('reception_uploaded', 'Ticket subido en recepción'),
        ('reception_assigned', 'Ticket imputado'),
        ('login', 'Inicio de sesión'),
        ('logout', 'Cierre de sesión'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    content_type = models.CharField(max_length=100, blank=True,
        help_text="Tipo de objeto afectado (ej: Expense, ExpensePeriod)")
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=500, blank=True,
        help_text="Representación textual del objeto en el momento del evento")

    details = models.JSONField(default=dict, blank=True,
        help_text="Datos adicionales del evento en formato JSON")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Registro de auditoría'
        verbose_name_plural = 'Registros de auditoría'
        indexes = [
            models.Index(fields=['content_type', 'object_id'], name='auditlog_object_idx'),
            models.Index(fields=['timestamp'], name='auditlog_timestamp_idx'),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} — {self.user} — {self.get_action_display()}"

    def save(self, *args, **kwargs):
        # Inmutabilidad Part 11: solo se permiten inserciones, nunca updates.
        if self.pk is not None:
            raise PermissionError("AuditLog es inmutable: no se permiten modificaciones.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("AuditLog es inmutable: no se permiten borrados.")
