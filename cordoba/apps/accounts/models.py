from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Usuario extendido del sistema Proyecto Córdoba.
    Roles manejados mediante Django Groups:
    - site_admin
    - coordinator
    - assistant
    - auditor
    """
    site = models.ForeignKey(
        'protocols.Site',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='users',
        help_text="Site de investigación al que pertenece este usuario (multisite)",
    )
    site_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    external_id = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Clave externa para futura integración con Alpha CR"
    )

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.username})"

    @property
    def is_coordinator(self):
        return self.groups.filter(name='coordinator').exists()

    @property
    def is_assistant(self):
        return self.groups.filter(name='assistant').exists()

    @property
    def is_site_admin(self):
        return self.groups.filter(name='site_admin').exists()

    @property
    def is_auditor(self):
        return self.groups.filter(name='auditor').exists()

    @property
    def role_display(self):
        if self.is_superuser:
            return 'Superusuario'
        if self.is_site_admin:
            return 'Admin del site'
        if self.is_coordinator:
            return 'Coordinador'
        if self.is_assistant:
            return 'Asistente'
        if self.is_auditor:
            return 'Auditor'
        return 'Sin rol'
