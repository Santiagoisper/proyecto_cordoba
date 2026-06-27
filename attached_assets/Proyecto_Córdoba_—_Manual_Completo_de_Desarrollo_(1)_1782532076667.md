# Proyecto Córdoba
## Manual Completo de Desarrollo — Bot de Viáticos para Investigación Clínica

**Versión:** 1.0  
**Fecha:** Junio 2026  
**Autor del proyecto:** Santiago Isbert Perlender — CINME / Innova Trials  
**Herramientas de desarrollo:** ClaudeCode + Codex  
**Metodología:** Sprints de 2 semanas con entregable funcional al cliente

***

## ÍNDICE GENERAL

1. Visión del producto y arquitectura
2. Stack tecnológico completo
3. Estructura de carpetas del proyecto
4. Modelo de datos completo
5. Etapa 1 — Fundación del proyecto
6. Etapa 2 — Captura de ticket
7. Etapa 3 — Motor OCR
8. Etapa 4 — Validaciones y estados
9. Etapa 5 — PDF por paciente
10. Etapa 6 — PDF consolidado del site
11. Etapa 7 — Cierre de período y auditoría
12. Etapa 8 — Pulido y hardening
13. Guía de verificación por etapa
14. Prompts listos para ClaudeCode / Codex

***

## 1. VISIÓN DEL PRODUCTO

### 1.1 Qué es Proyecto Córdoba

Proyecto Córdoba es un sistema web de gestión de viáticos para pacientes de ensayos clínicos. Permite que los asistentes del site de investigación escaneen tickets de gastos (transporte, comida, alojamiento), los vinculen a la visita clínica del paciente y al protocolo correspondiente, y generen automáticamente documentos PDF de rendición para presentar al sponsor y archivar como fuente GCP/ANMAT.

### 1.2 Actores del sistema

| Actor | Rol | Qué hace |
|---|---|---|
| **Asistente del site** | Operativo | Carga tickets, vincula a paciente/visita/protocolo |
| **Coordinador** | Supervisión | Revisa, aprueba, rechaza u observa gastos |
| **Admin del site** | Configuración | Crea protocolos, pacientes, visitas, topes |
| **Auditor (read-only)** | Consulta | Ve y descarga reportes, no modifica nada |

### 1.3 Flujo principal de una operación

```
Admin configura protocolo + visitas + pacientes
        ↓
Asistente selecciona protocolo → paciente → visita
        ↓
Asistente sube foto del ticket
        ↓
OCR extrae campos automáticamente
        ↓
Asistente corrige si es necesario y confirma
        ↓
Coordinador revisa en su dashboard
        ↓
Coordinador aprueba (o rechaza / observa)
        ↓
Coordinador cierra período
        ↓
Sistema genera PDF por paciente + PDF consolidado del site
```

### 1.4 Principios de diseño (no negociables)

- **Código de paciente, nunca nombre real** en PDFs ni reportes.
- **Cada gasto tiene un AuditLog inmutable**: quién lo creó, quién lo modificó, quién lo aprobó.
- **El coordinador revisa y aprueba, nunca retipea**.
- **Archivos de tickets cifrados** y separados de los metadatos.
- **El período cerrado no se puede modificar**.
- **La app es mobile-first**: el asistente usa el celular para cargar.

***

## 2. STACK TECNOLÓGICO COMPLETO

### 2.1 Backend

| Componente | Tecnología | Versión | Por qué |
|---|---|---|---|
| Framework principal | Django | 5.x | ORM robusto, admin gratis, ecosistema para clínica |
| API REST | Django REST Framework | 3.15.x | Para futura integración con Alpha CR y mobile |
| Base de datos | PostgreSQL | 16.x | Transaccional, auditoria, relaciones complejas |
| Cola de tareas | Celery | 5.x | Procesar OCR asíncrono sin bloquear UI |
| Broker de mensajes | Redis | 7.x | Simple, rápido, perfecto para Celery |
| Servidor WSGI | Gunicorn | 21.x | Producción estable con Django |
| Proxy reverso | Nginx (en prod) | — | Sirve archivos estáticos, SSL termination |

### 2.2 Frontend

| Componente | Tecnología | Por qué |
|---|---|---|
| Templates | Django Templates (Jinja2) | Sin build toolchain, vive dentro de Django |
| Interactividad | HTMX 2.x | Dinamismo sin React ni bundlers |
| Estilos | Tailwind CSS 4.x via CDN | Sin npm, sin build, rápido de usar |
| Iconos | Lucide Icons (CDN) | Limpio, SVG, sin dependencias |
| Previsualización foto | JavaScript nativo | No hace falta librería |

### 2.3 OCR y procesamiento

| Componente | Tecnología | Por qué |
|---|---|---|
| Motor OCR | Veryfi API (opción A) | Especializado en recibos, 3-5 seg, Python SDK |
| Motor OCR alternativo | Google Document AI (opción B) | Más flexible, HIPAA compliant |
| Procesamiento asíncrono | Celery task | OCR no bloquea la request del usuario |
| Almacenamiento archivos | Cloudinary (dev) / AWS S3 (prod) | Imágenes seguras, escalables |

### 2.4 Generación de PDF

| Componente | Tecnología | Por qué |
|---|---|---|
| Renderizado PDF | WeasyPrint | Python puro, HTML+CSS → PDF de alta calidad |
| Templates PDF | Django Templates | Mismo sistema que el frontend |
| Firma/marca | SVG inline en template | Sin dependencias externas |

### 2.5 Autenticación y seguridad

| Componente | Tecnología | Por qué |
|---|---|---|
| Autenticación | Django allauth | Roles, sesiones, recovery, todo listo |
| Roles y permisos | Django Groups + permisos custom | Granular por modelo y acción |
| CSRF | Django built-in | Activo por defecto |
| HTTPS | Let's Encrypt (prod) | Gratuito, automático en Railway/Render |
| Cifrado en reposo | PostgreSQL encryption + S3 SSE | Datos sensibles protegidos |

### 2.6 Deploy e infraestructura

| Componente | Tecnología | Por qué |
|---|---|---|
| Plataforma de deploy | Railway | Un `git push`, PostgreSQL incluido, $5/mes |
| CI/CD | GitHub Actions (básico) | En etapas avanzadas |
| Control de versiones | Git + GitHub | Repositorio privado |
| Gestión de secrets | Railway environment variables | Sin `.env` en el repo |
| Dominio (prod) | Namecheap o similar | Opcional en primeras etapas |

### 2.7 Herramientas de desarrollo

| Herramienta | Uso |
|---|---|
| ClaudeCode | Generación de modelos, views, tests |
| Codex (GitHub Copilot) | Autocompletado y templates HTMX |
| VS Code | Editor principal |
| Railway CLI | Deploy desde terminal |
| pgAdmin o TablePlus | Inspección de la base de datos |
| Postico (Mac) / DBeaver | Cliente PostgreSQL visual |

***

## 3. ESTRUCTURA DE CARPETAS DEL PROYECTO

```
proyecto_cordoba/
├── manage.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example              ← template de variables de entorno (sin valores reales)
├── .gitignore
├── README.md
│
├── config/                   ← Configuración principal del proyecto Django
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py           ← Configuración compartida
│   │   ├── development.py    ← SQLite o PostgreSQL local, DEBUG=True
│   │   └── production.py     ← PostgreSQL real, DEBUG=False, S3
│   ├── urls.py
│   ├── wsgi.py
│   └── celery.py             ← Configuración de Celery
│
├── apps/
│   ├── accounts/             ← Usuarios, roles, autenticación
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── templates/
│   │
│   ├── protocols/            ← Protocolos, visitas
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── templates/
│   │
│   ├── patients/             ← Pacientes, asignación a protocolos
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── templates/
│   │
│   ├── expenses/             ← Gastos, tickets, estados, auditoría
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── forms.py
│   │   ├── tasks.py          ← Celery tasks (OCR)
│   │   ├── services.py       ← Lógica de negocio (validaciones, OCR service)
│   │   └── templates/
│   │
│   ├── reports/              ← Generación de PDFs
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── generators.py     ← Lógica de WeasyPrint
│   │   └── templates/
│   │       ├── pdf_patient.html
│   │       └── pdf_site.html
│   │
│   └── dashboard/            ← Vistas de resumen para coordinador y admin
│       ├── views.py
│       ├── urls.py
│       └── templates/
│
├── static/
│   ├── css/
│   ├── js/
│   └── img/
│
├── media/                    ← Archivos subidos (tickets) — gitignored
│
└── templates/
    ├── base.html             ← Layout principal
    ├── components/           ← Partials HTMX reutilizables
    └── emails/               ← Templates de emails
```

***

## 4. MODELO DE DATOS COMPLETO

Este es el corazón del proyecto. **No modificar estos modelos después del Sprint 2 sin migración cuidadosa.**

### 4.1 App: accounts

```python
# apps/accounts/models.py

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
    site_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Clave externa opcional para futura integración con Alpha CR
    external_id = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"
    
    @property
    def is_coordinator(self):
        return self.groups.filter(name='coordinator').exists()
    
    @property
    def is_assistant(self):
        return self.groups.filter(name='assistant').exists()
    
    @property
    def is_site_admin(self):
        return self.groups.filter(name='site_admin').exists()
```

### 4.2 App: protocols

```python
# apps/protocols/models.py

from django.db import models
from django.conf import settings

class Protocol(models.Model):
    """
    Protocolo de ensayo clínico.
    Un protocol puede tener múltiples pacientes y visitas.
    """
    code = models.CharField(max_length=50, unique=True)     # Ej: "PROT-2024-001"
    name = models.CharField(max_length=300)
    sponsor = models.CharField(max_length=200, blank=True)
    phase = models.CharField(max_length=20, blank=True)      # Ej: "Phase II"
    is_active = models.BooleanField(default=True)
    
    # Configuración de gastos del protocolo
    currency = models.CharField(max_length=3, default='ARS')  # ISO 4217
    max_daily_meals = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Tope diario para comidas en la moneda del protocolo"
    )
    max_daily_transport = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    max_daily_accommodation = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, related_name='protocols_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Para futura integración con Alpha CR
    external_protocol_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
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
    name = models.CharField(max_length=100)         # Ej: "Visita 1"
    code = models.CharField(max_length=20)           # Ej: "V1"
    order = models.PositiveIntegerField(default=0)   # Para ordenar las visitas
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
    
    def __str__(self):
        return f"{self.protocol.code} — {self.name}"
```

### 4.3 App: patients

```python
# apps/patients/models.py

from django.db import models
from django.conf import settings
from apps.protocols.models import Protocol, VisitType

class Patient(models.Model):
    """
    Paciente en un ensayo clínico.
    NUNCA almacenar nombre completo aquí. Solo código.
    Los datos identificatorios del paciente viven en Alpha CR (futura integración).
    """
    protocol = models.ForeignKey(
        Protocol, on_delete=models.PROTECT, related_name='patients'
    )
    patient_code = models.CharField(
        max_length=50,
        help_text="Código de identificación del paciente en el protocolo. Ej: 001-001"
    )
    initials = models.CharField(
        max_length=5, blank=True,
        help_text="Iniciales del paciente (opcional, para referencia interna)"
    )
    is_active = models.BooleanField(default=True)
    enrolled_date = models.DateField(null=True, blank=True)
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, related_name='patients_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Para futura integración con Alpha CR
    external_patient_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['protocol', 'patient_code']
        unique_together = ['protocol', 'patient_code']
    
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
        on_delete=models.SET_NULL, null=True, related_name='visits_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Para futura integración con Alpha CR
    external_visit_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['scheduled_date']
    
    def __str__(self):
        return f"{self.patient} — {self.visit_type.name} ({self.scheduled_date})"
    
    def get_ticket_window_start(self):
        """Fecha mínima aceptable de un ticket para esta visita."""
        from datetime import timedelta
        base = self.actual_date or self.scheduled_date
        return base - timedelta(days=self.visit_type.window_before_days)
    
    def get_ticket_window_end(self):
        """Fecha máxima aceptable de un ticket para esta visita."""
        from datetime import timedelta
        base = self.actual_date or self.scheduled_date
        return base + timedelta(days=self.visit_type.window_after_days)
```

### 4.4 App: expenses (el corazón del sistema)

```python
# apps/expenses/models.py

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
    
    def __str__(self):
        return f"{self.protocol.code} — {self.name}"
    
    @property
    def is_editable(self):
        return self.status == 'open'


class Expense(models.Model):
    """
    Gasto/viático de un paciente vinculado a una visita.
    Este es el modelo central del sistema.
    """
    
    CATEGORY_CHOICES = [
        ('transport', 'Transporte'),
        ('meals', 'Comidas'),
        ('accommodation', 'Alojamiento'),
        ('pharmacy', 'Farmacia'),
        ('parking', 'Estacionamiento'),
        ('other', 'Otro'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('ocr_pending', 'Procesando OCR'),
        ('pending_review', 'Pendiente de Revisión'),
        ('observed', 'Observado'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('settled', 'Liquidado'),
        ('exported', 'Exportado'),
    ]
    
    # Contexto clínico
    visit = models.ForeignKey(
        Visit, on_delete=models.PROTECT, related_name='expenses'
    )
    period = models.ForeignKey(
        ExpensePeriod, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='expenses'
    )
    
    # Datos del gasto
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=300, blank=True)
    expense_date = models.DateField(help_text="Fecha del comprobante")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='ARS')
    
    # Datos del proveedor (extraídos por OCR o ingresados manualmente)
    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_cuit = models.CharField(max_length=20, blank=True,
        help_text="CUIT del proveedor extraído del comprobante")
    receipt_number = models.CharField(max_length=50, blank=True,
        help_text="Número del comprobante/factura")
    receipt_type = models.CharField(max_length=10, blank=True,
        help_text="Tipo de comprobante: A, B, C, Ticket, etc.")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2,
        null=True, blank=True, help_text="IVA u otros impuestos discriminados")
    
    # Estado y workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    coordinator_notes = models.TextField(blank=True,
        help_text="Observaciones del coordinador al aprobar/rechazar/observar")
    
    # Metadatos
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, related_name='expenses_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-expense_date']
    
    def __str__(self):
        return f"{self.visit.patient} — {self.get_category_display()} — {self.amount} {self.currency}"
    
    @property
    def patient(self):
        return self.visit.patient
    
    @property
    def protocol(self):
        return self.visit.patient.protocol
    
    def is_within_visit_window(self):
        """Valida que la fecha del ticket esté dentro de la ventana de visita."""
        start = self.visit.get_ticket_window_start()
        end = self.visit.get_ticket_window_end()
        return start <= self.expense_date <= end
    
    def exceeds_category_limit(self):
        """Valida que el monto no supere el tope de categoría del protocolo."""
        protocol = self.protocol
        limit_map = {
            'meals': protocol.max_daily_meals,
            'transport': protocol.max_daily_transport,
            'accommodation': protocol.max_daily_accommodation,
        }
        limit = limit_map.get(self.category)
        if limit is None:
            return False
        return self.amount > limit


class TicketFile(models.Model):
    """
    Archivo del comprobante asociado a un gasto.
    Separado del Expense para permitir múltiples archivos por gasto
    y para aislar el almacenamiento de archivos de los metadatos del gasto.
    """
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name='ticket_files'
    )
    
    # Archivo original
    file = models.FileField(upload_to='tickets/%Y/%m/%d/')
    file_type = models.CharField(max_length=10)  # 'jpg', 'png', 'pdf'
    file_size = models.PositiveIntegerField(null=True)  # bytes
    
    # Datos extraídos por OCR
    ocr_raw_json = models.JSONField(null=True, blank=True,
        help_text="Respuesta cruda del motor OCR")
    ocr_extracted_date = models.DateField(null=True, blank=True)
    ocr_extracted_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    ocr_extracted_vendor = models.CharField(max_length=200, blank=True)
    ocr_extracted_cuit = models.CharField(max_length=20, blank=True)
    ocr_extracted_receipt_number = models.CharField(max_length=50, blank=True)
    ocr_extracted_receipt_type = models.CharField(max_length=10, blank=True)
    
    # Nivel de confianza del OCR por campo (0.0 a 1.0)
    ocr_confidence_date = models.FloatField(null=True, blank=True)
    ocr_confidence_amount = models.FloatField(null=True, blank=True)
    ocr_confidence_vendor = models.FloatField(null=True, blank=True)
    
    # Estado del procesamiento OCR
    OCR_STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('completed', 'Completado'),
        ('failed', 'Fallido'),
    ]
    ocr_status = models.CharField(
        max_length=20, choices=OCR_STATUS_CHOICES, default='pending'
    )
    ocr_processed_at = models.DateTimeField(null=True, blank=True)
    ocr_error_message = models.TextField(blank=True)
    
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Ticket de {self.expense} ({self.ocr_status})"


class AuditLog(models.Model):
    """
    Log de auditoría inmutable. NUNCA borrar registros de esta tabla.
    Registra cada cambio de estado o acción significativa sobre un Expense.
    """
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name='audit_logs'
    )
    
    ACTION_CHOICES = [
        ('created', 'Creado'),
        ('submitted', 'Enviado a revisión'),
        ('ocr_completed', 'OCR completado'),
        ('ocr_failed', 'OCR fallido'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado'),
        ('observed', 'Observado'),
        ('corrected', 'Corregido'),
        ('settled', 'Liquidado'),
        ('exported', 'Exportado'),
        ('period_closed', 'Período cerrado'),
    ]
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    comment = models.TextField(blank=True)
    
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True
    )
    performed_at = models.DateTimeField(auto_now_add=True)
    
    # IP del usuario para trazabilidad adicional
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['performed_at']
        # Esta tabla nunca debe permitir UPDATE ni DELETE en producción
    
    def __str__(self):
        return f"{self.expense} — {self.get_action_display()} por {self.performed_by}"
```

***

## 5. ETAPA 1 — FUNDACIÓN DEL PROYECTO

### 5.1 Objetivo de la etapa

Al finalizar esta etapa, existe un proyecto Django corriendo en local con:
- Login funcional con roles
- Admin configurado con los modelos principales
- Formulario básico de carga manual de un gasto (sin OCR)
- Deploy funcionando en Railway

**Duración estimada:** 2 semanas

### 5.2 Variables de entorno necesarias

Crear archivo `.env` (nunca commitearlo) con:

```
# .env
SECRET_KEY=generada-con-python-secrets
DEBUG=True
DATABASE_URL=postgresql://user:password@localhost:5432/cordoba_dev
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 5.3 Dependencias (requirements.txt)

```
Django==5.1.4
djangorestframework==3.15.2
psycopg2-binary==2.9.10
django-environ==0.11.2
django-allauth==65.3.0
Pillow==11.1.0
celery==5.4.0
redis==5.2.1
WeasyPrint==63.1
whitenoise==6.9.0
gunicorn==23.0.0
boto3==1.35.0
django-storages==1.14.4
```

Crear también `requirements-dev.txt`:

```
-r requirements.txt
django-debug-toolbar==4.4.6
factory-boy==3.3.1
coverage==7.6.10
```

### 5.4 Configuración base (settings/base.py)

```python
# config/settings/base.py

import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Terceros
    'allauth',
    'allauth.account',
    'rest_framework',
    
    # Apps del proyecto
    'apps.accounts',
    'apps.protocols',
    'apps.patients',
    'apps.expenses',
    'apps.reports',
    'apps.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'
AUTH_USER_MODEL = 'accounts.User'

DATABASES = {
    'default': env.db('DATABASE_URL')
}

SITE_ID = 1
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

### 5.5 Admin configurado

```python
# apps/expenses/admin.py

from django.contrib import admin
from .models import Expense, TicketFile, AuditLog, ExpensePeriod

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['visit', 'category', 'amount', 'currency', 'status', 'expense_date', 'created_by']
    list_filter = ['status', 'category', 'currency']
    search_fields = ['visit__patient__patient_code', 'vendor_name', 'receipt_number']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'expense_date'
    
    fieldsets = (
        ('Contexto clínico', {
            'fields': ('visit', 'period')
        }),
        ('Datos del gasto', {
            'fields': ('category', 'description', 'expense_date', 'amount', 'currency')
        }),
        ('Datos del comprobante', {
            'fields': ('vendor_name', 'vendor_cuit', 'receipt_number', 'receipt_type', 'tax_amount')
        }),
        ('Estado y workflow', {
            'fields': ('status', 'coordinator_notes')
        }),
        ('Metadatos', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['expense', 'action', 'performed_by', 'performed_at']
    readonly_fields = ['expense', 'action', 'from_status', 'to_status', 
                       'comment', 'performed_by', 'performed_at', 'ip_address']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ExpensePeriod)
class ExpensePeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'protocol', 'date_from', 'date_to', 'status']
    list_filter = ['status', 'protocol']
```

### 5.6 Template base

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Proyecto Córdoba{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        [x-cloak] { display: none !important; }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Navbar -->
    <nav class="bg-white border-b border-gray-200 px-4 py-3">
        <div class="max-w-7xl mx-auto flex items-center justify-between">
            <div class="flex items-center gap-3">
                <span class="font-semibold text-gray-900">Proyecto Córdoba</span>
                <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
                    {{ request.user.site_name }}
                </span>
            </div>
            <div class="flex items-center gap-4">
                <span class="text-sm text-gray-600">{{ request.user.get_full_name }}</span>
                <a href="{% url 'account_logout' %}" 
                   class="text-sm text-gray-500 hover:text-gray-900">
                    Salir
                </a>
            </div>
        </div>
    </nav>
    
    <!-- Sidebar + Content -->
    <div class="max-w-7xl mx-auto flex gap-0">
        <!-- Sidebar -->
        <aside class="w-56 min-h-screen bg-white border-r border-gray-200 p-4">
            <nav class="space-y-1">
                <a href="/dashboard/" 
                   class="flex items-center gap-2 px-3 py-2 rounded text-sm text-gray-700 hover:bg-gray-100">
                    Dashboard
                </a>
                <a href="/expenses/new/" 
                   class="flex items-center gap-2 px-3 py-2 rounded text-sm text-gray-700 hover:bg-gray-100">
                    Cargar Viático
                </a>
                <a href="/expenses/" 
                   class="flex items-center gap-2 px-3 py-2 rounded text-sm text-gray-700 hover:bg-gray-100">
                    Mis Gastos
                </a>
                {% if request.user.is_coordinator or request.user.is_site_admin %}
                <a href="/expenses/pending/" 
                   class="flex items-center gap-2 px-3 py-2 rounded text-sm text-gray-700 hover:bg-gray-100">
                    Pendientes
                </a>
                <a href="/reports/" 
                   class="flex items-center gap-2 px-3 py-2 rounded text-sm text-gray-700 hover:bg-gray-100">
                    Reportes PDF
                </a>
                {% endif %}
            </nav>
        </aside>
        
        <!-- Main content -->
        <main class="flex-1 p-6">
            {% if messages %}
            <div class="mb-4 space-y-2">
                {% for message in messages %}
                <div class="p-3 rounded text-sm {% if message.tags == 'error' %}bg-red-50 text-red-700{% else %}bg-green-50 text-green-700{% endif %}">
                    {{ message }}
                </div>
                {% endfor %}
            </div>
            {% endif %}
            
            {% block content %}{% endblock %}
        </main>
    </div>
    
    <script>lucide.createIcons();</script>
</body>
</html>
```

### 5.7 Resultado esperado al final de la Etapa 1

Al terminar la Etapa 1 deberías poder:
1. Ir a `http://localhost:8000/admin/` e ingresar con superusuario.
2. Crear un Protocol, un Patient, una Visit y un Expense manualmente desde el admin.
3. Ir a `http://localhost:8000/dashboard/` y ver el layout base con sidebar.
4. Tener el proyecto corriendo en Railway con base de datos PostgreSQL real.

**Checkpoint de validación — copiar al asistente:**
```
Checklist Etapa 1:
[ ] python manage.py migrate corre sin errores
[ ] python manage.py createsuperuser funciona
[ ] Admin muestra Protocol, Patient, Visit, Expense, AuditLog, ExpensePeriod
[ ] Se puede crear un Expense desde el admin vinculado a una Visit
[ ] La URL /dashboard/ carga sin error 500
[ ] El proyecto está deployado en Railway y la URL pública carga
```

***

## 6. ETAPA 2 — CAPTURA DE TICKET

### 6.1 Objetivo de la etapa

El asistente puede entrar desde el celular, seleccionar protocolo → paciente → visita y subir una foto del ticket. La imagen se guarda en Cloudinary (o S3) asociada al gasto.

**Duración estimada:** 2 semanas

### 6.2 Flujo de pantallas (UX)

```
/expenses/new/
    Paso 1: Seleccionar protocolo (dropdown)
    Paso 2: Seleccionar paciente del protocolo (carga dinámica con HTMX)
    Paso 3: Seleccionar visita del paciente (carga dinámica con HTMX)
    Paso 4: Completar datos del gasto
        - Categoría
        - Descripción (opcional)
        - Fecha del comprobante
        - Monto
    Paso 5: Subir foto del ticket
        - Cámara nativa del celular (input type="file" accept="image/*" capture="environment")
        - Preview en tiempo real antes de confirmar
    Confirmar → Gasto queda en status "ocr_pending"
```

### 6.3 Vista de carga (views.py)

```python
# apps/expenses/views.py

from django.views.generic import CreateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import Expense, TicketFile
from apps.patients.models import Patient, Visit
from apps.protocols.models import Protocol
from .tasks import process_ocr_for_ticket

class ExpenseCreateView(LoginRequiredMixin, CreateView):
    model = Expense
    template_name = 'expenses/create.html'
    fields = ['category', 'description', 'expense_date', 'amount', 'currency',
              'vendor_name', 'receipt_number']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['protocols'] = Protocol.objects.filter(is_active=True)
        return context
    
    def form_valid(self, form):
        # Obtener la visita seleccionada del POST
        visit_id = self.request.POST.get('visit_id')
        visit = get_object_or_404(Visit, pk=visit_id)
        
        expense = form.save(commit=False)
        expense.visit = visit
        expense.status = 'draft'
        expense.created_by = self.request.user
        expense.save()
        
        # Procesar archivo si se subió
        uploaded_file = self.request.FILES.get('ticket_file')
        if uploaded_file:
            ticket = TicketFile.objects.create(
                expense=expense,
                file=uploaded_file,
                file_type=uploaded_file.content_type.split('/')[-1],
                file_size=uploaded_file.size,
                uploaded_by=self.request.user,
                ocr_status='pending'
            )
            # Cambiar estado del gasto a espera de OCR
            expense.status = 'ocr_pending'
            expense.save()
            
            # Disparar task de OCR en background
            process_ocr_for_ticket.delay(ticket.id)
        
        return JsonResponse({'success': True, 'expense_id': expense.id})


# HTMX: cargar pacientes cuando se elige un protocolo
def load_patients_for_protocol(request):
    protocol_id = request.GET.get('protocol_id')
    patients = Patient.objects.filter(
        protocol_id=protocol_id, is_active=True
    ).order_by('patient_code')
    return JsonResponse({
        'patients': [
            {'id': p.id, 'code': p.patient_code, 'initials': p.initials}
            for p in patients
        ]
    })


# HTMX: cargar visitas cuando se elige un paciente
def load_visits_for_patient(request):
    patient_id = request.GET.get('patient_id')
    visits = Visit.objects.filter(
        patient_id=patient_id,
        status__in=['scheduled', 'completed']
    ).select_related('visit_type').order_by('scheduled_date')
    return JsonResponse({
        'visits': [
            {
                'id': v.id,
                'name': v.visit_type.name,
                'date': v.scheduled_date.strftime('%d/%m/%Y'),
                'status': v.get_status_display()
            }
            for v in visits
        ]
    })
```

### 6.4 Template de carga (con cámara nativa)

```html
<!-- templates/expenses/create.html -->
{% extends 'base.html' %}
{% block content %}

<div class="max-w-lg mx-auto">
    <h1 class="text-xl font-semibold text-gray-900 mb-6">Cargar Viático</h1>
    
    <form id="expense-form" method="post" enctype="multipart/form-data"
          hx-post="/expenses/new/" hx-target="#form-result">
        {% csrf_token %}
        
        <!-- Paso 1: Protocolo -->
        <div class="mb-4">
            abel class="block text-sm font-medium text-gray-700 mb-1">
                Protocolo *
            </label>
            <select name="protocol_id" id="protocol-select" required
                    class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    hx-get="/expenses/patients/"
                    hx-target="#patient-select-container"
                    hx-trigger="change"
                    hx-include="[name='protocol_id']">
                <option value="">Seleccionar protocolo...</option>
                {% for protocol in protocols %}
                <option value="{{ protocol.id }}">{{ protocol.code }} — {{ protocol.name }}</option>
                {% endfor %}
            </select>
        </div>
        
        <!-- Paso 2: Paciente (carga dinámica) -->
        <div id="patient-select-container" class="mb-4">
            abel class="block text-sm font-medium text-gray-700 mb-1">
                Paciente *
            </label>
            <select name="patient_id" id="patient-select" disabled
                    class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                    hx-get="/expenses/visits/"
                    hx-target="#visit-select-container"
                    hx-trigger="change">
                <option value="">Primero seleccione un protocolo...</option>
            </select>
        </div>
        
        <!-- Paso 3: Visita (carga dinámica) -->
        <div id="visit-select-container" class="mb-4">
            abel class="block text-sm font-medium text-gray-700 mb-1">
                Visita *
            </label>
            <select name="visit_id" id="visit-select" disabled
                    class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                <option value="">Primero seleccione un paciente...</option>
            </select>
        </div>
        
        <!-- Paso 4: Datos del gasto -->
        <div class="grid grid-cols-2 gap-3 mb-4">
            <div>
                abel class="block text-sm font-medium text-gray-700 mb-1">Categoría *</label>
                <select name="category" required
                        class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                    <option value="">Seleccionar...</option>
                    <option value="transport">Transporte</option>
                    <option value="meals">Comidas</option>
                    <option value="accommodation">Alojamiento</option>
                    <option value="pharmacy">Farmacia</option>
                    <option value="parking">Estacionamiento</option>
                    <option value="other">Otro</option>
                </select>
            </div>
            <div>
                abel class="block text-sm font-medium text-gray-700 mb-1">Fecha *</label>
                <input type="date" name="expense_date" required
                       class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
            </div>
            <div>
                abel class="block text-sm font-medium text-gray-700 mb-1">Monto *</label>
                <input type="number" name="amount" step="0.01" required
                       class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                       placeholder="0.00">
            </div>
            <div>
                abel class="block text-sm font-medium text-gray-700 mb-1">Moneda</label>
                <select name="currency"
                        class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                    <option value="ARS">ARS $</option>
                    <option value="USD">USD $</option>
                </select>
            </div>
        </div>
        
        <!-- Paso 5: Foto del ticket -->
        <div class="mb-6">
            abel class="block text-sm font-medium text-gray-700 mb-2">
                Foto del comprobante
            </label>
            
            <!-- Input de archivo con cámara nativa en móvil -->
            abel class="flex flex-col items-center justify-center w-full h-40 
                          border-2 border-dashed border-gray-300 rounded-lg 
                          cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors">
                <div id="upload-placeholder" class="flex flex-col items-center">
                    <i data-lucide="camera" class="w-8 h-8 text-gray-400 mb-2"></i>
                    <p class="text-sm text-gray-500">Toca para sacar foto o subir imagen</p>
                    <p class="text-xs text-gray-400 mt-1">JPG, PNG, PDF</p>
                </div>
                <img id="ticket-preview" class="hidden max-h-36 rounded object-contain" alt="Preview">
                <input type="file" name="ticket_file" id="ticket-input"
                       accept="image/*,application/pdf"
                       capture="environment"
                       class="hidden"
                       onchange="previewTicket(this)">
            </label>
        </div>
        
        <button type="submit"
                class="w-full bg-blue-600 text-white py-3 rounded-lg font-medium text-sm
                       hover:bg-blue-700 transition-colors disabled:opacity-50">
            Enviar a revisión
        </button>
    </form>
    
    <div id="form-result"></div>
</div>

<script>
function previewTicket(input) {
    if (input.files && input.files) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('ticket-preview');
            const placeholder = document.getElementById('upload-placeholder');
            preview.src = e.target.result;
            preview.classList.remove('hidden');
            placeholder.classList.add('hidden');
        };
        reader.readAsDataURL(input.files);
    }
}
</script>
{% endblock %}
```

### 6.5 Resultado esperado al final de la Etapa 2

1. El asistente puede ir a `/expenses/new/` desde el celular.
2. Al seleccionar el protocolo, los pacientes se cargan dinámicamente.
3. Al seleccionar el paciente, las visitas se cargan dinámicamente.
4. Se puede subir una foto del ticket y ver el preview antes de enviar.
5. Al confirmar, el gasto aparece en el admin con la imagen del ticket.

**Checkpoint de validación:**
```
Checklist Etapa 2:
[ ] /expenses/new/ carga en el celular correctamente
[ ] Seleccionar protocolo actualiza el select de pacientes sin recargar la página
[ ] Seleccionar paciente actualiza el select de visitas sin recargar la página
[ ] Se puede tomar una foto con la cámara del celular
[ ] El preview de la imagen se muestra antes de enviar
[ ] Al enviar, el gasto aparece en el admin con status "ocr_pending"
[ ] La imagen del ticket está guardada en media/ (o Cloudinary)
```

***

## 7. ETAPA 3 — MOTOR OCR

### 7.1 Objetivo de la etapa

Cuando se sube un ticket, el sistema procesa la imagen automáticamente, extrae los datos del comprobante y pre-completa los campos del gasto. El usuario puede corregir si algo está mal.

**Duración estimada:** 2 semanas

### 7.2 Celery task de OCR

```python
# apps/expenses/tasks.py

from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_ocr_for_ticket(self, ticket_file_id):
    """
    Procesa OCR de un ticket.
    Se ejecuta en background después de que el usuario sube la imagen.
    """
    from .models import TicketFile, Expense, AuditLog
    
    try:
        ticket = TicketFile.objects.get(id=ticket_file_id)
        ticket.ocr_status = 'processing'
        ticket.save()
        
        # Llamar al servicio OCR
        from .services import OCRService
        ocr_service = OCRService()
        result = ocr_service.process_ticket(ticket.file.url)
        
        # Guardar resultados crudos
        ticket.ocr_raw_json = result.raw_json
        ticket.ocr_extracted_date = result.date
        ticket.ocr_extracted_amount = result.amount
        ticket.ocr_extracted_vendor = result.vendor_name
        ticket.ocr_extracted_cuit = result.vendor_cuit
        ticket.ocr_extracted_receipt_number = result.receipt_number
        ticket.ocr_extracted_receipt_type = result.receipt_type
        ticket.ocr_confidence_date = result.confidence_date
        ticket.ocr_confidence_amount = result.confidence_amount
        ticket.ocr_confidence_vendor = result.confidence_vendor
        ticket.ocr_status = 'completed'
        ticket.ocr_processed_at = timezone.now()
        ticket.save()
        
        # Pre-completar campos del Expense si tienen alta confianza
        expense = ticket.expense
        if result.amount and result.confidence_amount > 0.7:
            expense.amount = result.amount
        if result.date and result.confidence_date > 0.7:
            expense.expense_date = result.date
        if result.vendor_name and result.confidence_vendor > 0.5:
            expense.vendor_name = result.vendor_name
        if result.vendor_cuit:
            expense.vendor_cuit = result.vendor_cuit
        if result.receipt_number:
            expense.receipt_number = result.receipt_number
        if result.receipt_type:
            expense.receipt_type = result.receipt_type
        
        expense.status = 'pending_review'
        expense.save()
        
        # Registrar en AuditLog
        AuditLog.objects.create(
            expense=expense,
            action='ocr_completed',
            from_status='ocr_pending',
            to_status='pending_review',
            comment=f'OCR completado. Confianza: fecha={result.confidence_date:.0%}, '
                    f'monto={result.confidence_amount:.0%}',
        )
        
        logger.info(f"OCR completado para ticket {ticket_file_id}")
        
    except TicketFile.DoesNotExist:
        logger.error(f"TicketFile {ticket_file_id} no existe")
    except Exception as exc:
        logger.error(f"Error en OCR para ticket {ticket_file_id}: {exc}")
        try:
            ticket.ocr_status = 'failed'
            ticket.ocr_error_message = str(exc)
            ticket.save()
            ticket.expense.status = 'pending_review'
            ticket.expense.save()
        except Exception:
            pass
        raise self.retry(exc=exc)
```

### 7.3 Servicio OCR (Veryfi)

```python
# apps/expenses/services.py

import os
from dataclasses import dataclass
from typing import Optional
from datetime import date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    raw_json: dict
    date: Optional[date] = None
    amount: Optional[Decimal] = None
    vendor_name: str = ''
    vendor_cuit: str = ''
    receipt_number: str = ''
    receipt_type: str = ''
    confidence_date: float = 0.0
    confidence_amount: float = 0.0
    confidence_vendor: float = 0.0


class OCRService:
    """
    Servicio de OCR. Abstrae el motor específico para facilitar cambio futuro.
    Motor actual: Veryfi API.
    Para cambiar a Google Document AI: solo modificar este servicio.
    """
    
    def __init__(self):
        self.client_id = os.environ.get('VERYFI_CLIENT_ID')
        self.client_secret = os.environ.get('VERYFI_CLIENT_SECRET')
        self.username = os.environ.get('VERYFI_USERNAME')
        self.api_key = os.environ.get('VERYFI_API_KEY')
    
    def process_ticket(self, file_url: str) -> OCRResult:
        """
        Procesa un ticket y retorna los datos extraídos.
        """
        try:
            from veryfi import Client
            
            client = Client(
                client_id=self.client_id,
                client_secret=self.client_secret,
                username=self.username,
                api_key=self.api_key
            )
            
            response = client.process_document_url(file_url)
            return self._parse_veryfi_response(response)
            
        except ImportError:
            logger.warning("Veryfi SDK no instalado. Usando modo simulación.")
            return self._mock_result()
        except Exception as e:
            logger.error(f"Error llamando a Veryfi: {e}")
            raise
    
    def _parse_veryfi_response(self, response: dict) -> OCRResult:
        """Convierte la respuesta de Veryfi al formato interno OCRResult."""
        from datetime import datetime
        
        raw_date = response.get('date')
        parsed_date = None
        if raw_date:
            try:
                parsed_date = datetime.strptime(raw_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        total = response.get('total')
        amount = Decimal(str(total)) if total else None
        
        # Buscar CUIT en el texto del vendor (formato argentino: XX-XXXXXXXX-X)
        import re
        vendor_name = response.get('vendor', {}).get('name', '')
        vendor_raw = str(response.get('vendor', {}))
        cuit_match = re.search(r'\d{2}-\d{8}-\d', vendor_raw)
        cuit = cuit_match.group(0) if cuit_match else ''
        
        return OCRResult(
            raw_json=response,
            date=parsed_date,
            amount=amount,
            vendor_name=vendor_name,
            vendor_cuit=cuit,
            receipt_number=str(response.get('invoice_number', '')),
            receipt_type=response.get('document_type', ''),
            confidence_date=0.9 if parsed_date else 0.0,
            confidence_amount=0.95 if amount else 0.0,
            confidence_vendor=0.8 if vendor_name else 0.0,
        )
    
    def _mock_result(self) -> OCRResult:
        """Resultado simulado para desarrollo sin API key."""
        return OCRResult(
            raw_json={'mock': True},
            date=None,
            amount=None,
            vendor_name='[OCR no disponible]',
            confidence_date=0.0,
            confidence_amount=0.0,
            confidence_vendor=0.0,
        )
```

### 7.4 Vista de revisión de OCR

Después del procesamiento, el asistente ve una pantalla de revisión donde puede confirmar o corregir los campos extraídos por OCR. Los campos con alta confianza se muestran en verde; con baja confianza, en amarillo; los no reconocidos, en rojo y en blanco.

### 7.5 Resultado esperado al final de la Etapa 3

1. Al subir un ticket, aparece un spinner indicando "Procesando...".
2. Después de 5-10 segundos, el gasto pasa a "Pendiente de Revisión".
3. En la pantalla de revisión, los campos están pre-completados con lo que extrajo el OCR.
4. Los campos tienen un badge de confianza (verde / amarillo / rojo).
5. El asistente puede corregir cualquier campo antes de confirmar.

**Checkpoint de validación:**
```
Checklist Etapa 3:
[ ] CELERY_BROKER_URL=redis://localhost:6379/0 configurado
[ ] celery -A config worker --loglevel=info corre sin errores
[ ] Al subir un ticket, la task OCR se dispara (visible en logs de Celery)
[ ] El TicketFile queda con ocr_status='completed' después del procesamiento
[ ] Los campos del Expense se actualizan con los datos del OCR
[ ] La pantalla de revisión muestra los campos con sus niveles de confianza
[ ] El asistente puede editar y confirmar
```

***

## 8. ETAPA 4 — VALIDACIONES Y ESTADOS

### 8.1 Objetivo de la etapa

El coordinador tiene su propio dashboard donde ve todos los gastos pendientes de revisión, puede aprobarlos, rechazarlos u observarlos. Las validaciones automáticas (fecha fuera de ventana, tope excedido) se muestran como alertas.

**Duración estimada:** 2 semanas

### 8.2 Dashboard del coordinador

```python
# apps/dashboard/views.py

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.expenses.models import Expense

class CoordinatorDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/coordinator.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['pending_expenses'] = Expense.objects.filter(
            status='pending_review'
        ).select_related(
            'visit__patient__protocol',
            'visit__visit_type',
            'created_by'
        ).prefetch_related('ticket_files').order_by('-created_at')
        
        context['observed_expenses'] = Expense.objects.filter(
            status='observed'
        ).count()
        
        context['approved_today'] = Expense.objects.filter(
            status='approved'
        ).count()
        
        return context
```

### 8.3 Acciones del coordinador (HTMX)

```python
# apps/expenses/views.py — Acciones del coordinador

from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from .models import Expense, AuditLog

@require_POST
@login_required
def approve_expense(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id)
    
    if not request.user.is_coordinator and not request.user.is_site_admin:
        return HttpResponse('No autorizado', status=403)
    
    old_status = expense.status
    expense.status = 'approved'
    expense.save()
    
    AuditLog.objects.create(
        expense=expense,
        action='approved',
        from_status=old_status,
        to_status='approved',
        comment=request.POST.get('comment', ''),
        performed_by=request.user,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Retornar el HTML actualizado de la fila (HTMX swap)
    return HttpResponse(
        f'<tr id="expense-{expense_id}" class="bg-green-50">'
        f'<td class="px-4 py-2 text-sm text-green-700">Aprobado ✓</td>'
        f'</tr>'
    )


@require_POST
@login_required
def reject_expense(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id)
    old_status = expense.status
    expense.status = 'rejected'
    expense.coordinator_notes = request.POST.get('comment', '')
    expense.save()
    
    AuditLog.objects.create(
        expense=expense,
        action='rejected',
        from_status=old_status,
        to_status='rejected',
        comment=expense.coordinator_notes,
        performed_by=request.user,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return HttpResponse(f'<span class="text-red-600 text-sm">Rechazado</span>')


@require_POST
@login_required
def observe_expense(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id)
    old_status = expense.status
    expense.status = 'observed'
    expense.coordinator_notes = request.POST.get('comment', '')
    expense.save()
    
    AuditLog.objects.create(
        expense=expense,
        action='observed',
        from_status=old_status,
        to_status='observed',
        comment=expense.coordinator_notes,
        performed_by=request.user,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    return HttpResponse(f'<span class="text-yellow-600 text-sm">Observado — {expense.coordinator_notes}</span>')
```

### 8.4 Validaciones automáticas

```python
# apps/expenses/services.py — Añadir a la clase existente

class ExpenseValidationService:
    """Valida un gasto contra las reglas del protocolo."""
    
    def validate(self, expense: 'Expense') -> list:
        """Retorna lista de alertas. Lista vacía = sin alertas."""
        alerts = []
        
        # Validación 1: Fecha dentro de la ventana de visita
        if not expense.is_within_visit_window():
            alerts.append({
                'type': 'warning',
                'code': 'date_outside_window',
                'message': (
                    f'La fecha del ticket ({expense.expense_date}) está fuera '
                    f'de la ventana de la visita '
                    f'({expense.visit.get_ticket_window_start()} — '
                    f'{expense.visit.get_ticket_window_end()})'
                )
            })
        
        # Validación 2: Tope de categoría
        if expense.exceeds_category_limit():
            protocol = expense.protocol
            limits = {
                'meals': protocol.max_daily_meals,
                'transport': protocol.max_daily_transport,
                'accommodation': protocol.max_daily_accommodation,
            }
            limit = limits.get(expense.category)
            alerts.append({
                'type': 'error',
                'code': 'exceeds_limit',
                'message': (
                    f'El monto {expense.amount} {expense.currency} supera el '
                    f'tope configurado para {expense.get_category_display()} '
                    f'({limit} {expense.currency})'
                )
            })
        
        # Validación 3: Posible duplicado
        from .models import Expense as ExpenseModel
        duplicate = ExpenseModel.objects.filter(
            visit=expense.visit,
            category=expense.category,
            expense_date=expense.expense_date,
            amount=expense.amount,
        ).exclude(id=expense.id).exclude(status='rejected').first()
        
        if duplicate:
            alerts.append({
                'type': 'error',
                'code': 'possible_duplicate',
                'message': f'Posible duplicado del gasto #{duplicate.id} con misma fecha, categoría y monto.'
            })
        
        return alerts
```

### 8.5 Resultado esperado al final de la Etapa 4

1. El coordinador ve su dashboard con todos los gastos pendientes.
2. Para cada gasto, puede ver el ticket, los datos extraídos y las alertas de validación.
3. Puede aprobar, rechazar u observar con un clic y un comentario.
4. Las acciones son instantáneas (HTMX) sin recargar la página.
5. El historial de auditoría de cada gasto registra todos los cambios.

**Checkpoint de validación:**
```
Checklist Etapa 4:
[ ] /dashboard/ del coordinador muestra la tabla de gastos pendientes
[ ] Se puede aprobar un gasto con botón + comentario (sin recargar)
[ ] Se puede rechazar un gasto con comentario
[ ] Se puede observar un gasto con comentario
[ ] Las alertas de validación aparecen sobre el gasto (fecha fuera de ventana, tope excedido)
[ ] El AuditLog registra cada acción con usuario, IP y timestamp
```

***

## 9. ETAPA 5 — PDF POR PACIENTE

### 9.1 Objetivo de la etapa

El coordinador puede generar un PDF de rendición por paciente, listo para entregar al sponsor o archivar como documento fuente GCP/ANMAT.

**Duración estimada:** 2 semanas

### 9.2 Generador de PDF

```python
# apps/reports/generators.py

from weasyprint import HTML, CSS
from django.template.loader import render_to_string
from django.http import HttpResponse
from apps.expenses.models import Expense
from apps.patients.models import Patient
import base64


def generate_patient_pdf(patient_id, period_id=None, request=None):
    """
    Genera PDF de rendición para un paciente.
    Retorna un objeto HttpResponse con el PDF.
    """
    patient = Patient.objects.get(id=patient_id)
    
    expenses_qs = Expense.objects.filter(
        visit__patient=patient,
        status__in=['approved', 'settled', 'exported']
    ).select_related(
        'visit__visit_type',
    ).prefetch_related('ticket_files').order_by('visit__scheduled_date', 'expense_date')
    
    if period_id:
        expenses_qs = expenses_qs.filter(period_id=period_id)
    
    # Calcular totales por categoría
    from django.db.models import Sum
    totals_by_category = {}
    for expense in expenses_qs:
        cat = expense.get_category_display()
        totals_by_category[cat] = totals_by_category.get(cat, 0) + float(expense.amount)
    
    grand_total = sum(totals_by_category.values())
    
    # Convertir imágenes a base64 para el PDF
    expenses_with_images = []
    for expense in expenses_qs:
        ticket = expense.ticket_files.first()
        image_base64 = None
        if ticket and ticket.file:
            try:
                with ticket.file.open('rb') as f:
                    image_base64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                pass
        expenses_with_images.append({
            'expense': expense,
            'image_base64': image_base64,
        })
    
    # Renderizar template HTML
    html_string = render_to_string('reports/pdf_patient.html', {
        'patient': patient,
        'protocol': patient.protocol,
        'expenses_with_images': expenses_with_images,
        'totals_by_category': totals_by_category,
        'grand_total': grand_total,
        'generated_at': __import__('django.utils.timezone', fromlist=['now']).now(),
        'generated_by': request.user if request else None,
    })
    
    # Generar PDF con WeasyPrint
    html = HTML(string=html_string, base_url='/')
    pdf_bytes = html.write_pdf()
    
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f'viaticos_{patient.patient_code}_{patient.protocol.code}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response
```

### 9.3 Template del PDF por paciente

```html
<!-- templates/reports/pdf_patient.html -->
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  @page {
    size: A4;
    margin: 2cm;
    @bottom-right {
      content: "Página " counter(page) " de " counter(pages);
      font-size: 9px;
      color: #888;
    }
  }
  body { font-family: Arial, sans-serif; font-size: 11px; color: #333; }
  .header { border-bottom: 2px solid #1e40af; margin-bottom: 16px; padding-bottom: 8px; }
  .header h1 { font-size: 16px; color: #1e40af; margin: 0 0 4px 0; }
  .meta-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
  .meta-box { background: #f8f9fa; padding: 8px; border-radius: 4px; }
  .meta-box label { font-size: 9px; color: #666; text-transform: uppercase; display: block; }
  .meta-box span { font-size: 11px; font-weight: bold; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 10px; }
  th { background: #1e40af; color: white; padding: 6px 8px; text-align: left; }
  td { padding: 5px 8px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
  tr:nth-child(even) td { background: #f9fafb; }
  .ticket-thumb { max-width: 60px; max-height: 45px; border: 1px solid #ddd; }
  .totals-table { width: 40%; margin-left: auto; }
  .totals-table td { border: none; }
  .grand-total td { font-weight: bold; font-size: 12px; border-top: 2px solid #333; }
  .footer { margin-top: 24px; border-top: 1px solid #e5e7eb; padding-top: 8px; 
            font-size: 9px; color: #888; display: flex; justify-content: space-between; }
  .confidential { background: #fef3c7; border: 1px solid #f59e0b; padding: 4px 8px; 
                  border-radius: 4px; font-size: 9px; margin-bottom: 12px; }
</style>
</head>
<body>

<div class="header">
  <h1>Rendición de Viáticos</h1>
  <p style="margin:0;color:#666;">{{ protocol.name }}</p>
</div>

<div class="confidential">
  ⚠️ Documento confidencial — Archivo fuente GCP. 
  Identificación de paciente por código únicamente.
</div>

<div class="meta-grid">
  <div class="meta-box">
    abel>Protocolo</label>
    <span>{{ protocol.code }}</span>
  </div>
  <div class="meta-box">
    abel>Paciente (código)</label>
    <span>{{ patient.patient_code }}</span>
  </div>
  <div class="meta-box">
    abel>Sponsor</label>
    <span>{{ protocol.sponsor|default:"—" }}</span>
  </div>
  <div class="meta-box">
    abel>Fase</label>
    <span>{{ protocol.phase|default:"—" }}</span>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Fecha</th>
      <th>Visita</th>
      <th>Categoría</th>
      <th>Proveedor</th>
      <th>Nro. Comprobante</th>
      <th>Tipo</th>
      <th>IVA</th>
      <th style="text-align:right">Monto</th>
      <th>Comprobante</th>
    </tr>
  </thead>
  <tbody>
    {% for item in expenses_with_images %}
    <tr>
      <td>{{ item.expense.expense_date|date:"d/m/Y" }}</td>
      <td>{{ item.expense.visit.visit_type.name }}</td>
      <td>{{ item.expense.get_category_display }}</td>
      <td>{{ item.expense.vendor_name|default:"—" }}</td>
      <td>{{ item.expense.receipt_number|default:"—" }}</td>
      <td>{{ item.expense.receipt_type|default:"—" }}</td>
      <td style="text-align:right">
        {% if item.expense.tax_amount %}
        {{ item.expense.currency }} {{ item.expense.tax_amount }}
        {% else %}—{% endif %}
      </td>
      <td style="text-align:right">
        {{ item.expense.currency }} {{ item.expense.amount }}
      </td>
      <td>
        {% if item.image_base64 %}
        <img class="ticket-thumb" 
             src="data:image/jpeg;base64,{{ item.image_base64 }}" 
             alt="Comprobante">
        {% else %}
        <span style="color:#aaa;font-size:9px;">Sin imagen</span>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<!-- Totales por categoría -->
<table class="totals-table">
  <tbody>
    {% for category, total in totals_by_category.items %}
    <tr>
      <td>{{ category }}</td>
      <td style="text-align:right">{{ protocol.currency }} {{ total|floatformat:2 }}</td>
    </tr>
    {% endfor %}
    <tr class="grand-total">
      <td>TOTAL GENERAL</td>
      <td style="text-align:right">{{ protocol.currency }} {{ grand_total|floatformat:2 }}</td>
    </tr>
  </tbody>
</table>

<div class="footer">
  <span>Generado: {{ generated_at|date:"d/m/Y H:i" }}</span>
  <span>Por: {{ generated_by|default:"Sistema" }}</span>
  <span>v1.0 — Proyecto Córdoba</span>
</div>

</body>
</html>
```

### 9.4 Resultado esperado al final de la Etapa 5

1. En el panel de reportes, el coordinador selecciona un paciente y un período.
2. El sistema genera y descarga un PDF con el formato correcto.
3. El PDF incluye: datos del protocolo, código de paciente, tabla de gastos con imágenes en miniatura, totales y metadata de generación.
4. El PDF está listo para entregarse al sponsor o para archivo GCP.

**Checkpoint de validación:**
```
Checklist Etapa 5:
[ ] /reports/ muestra selector de paciente y período
[ ] Al generar, el navegador descarga un archivo PDF
[ ] El PDF tiene el header con protocolo y código de paciente
[ ] La tabla de gastos muestra fecha, visita, categoría, monto y miniatura del ticket
[ ] Los totales por categoría están correctos
[ ] El footer tiene fecha de generación, usuario y versión
[ ] El PDF tiene el aviso de confidencialidad
```

***

## 10. ETAPA 6 — PDF CONSOLIDADO DEL SITE

### 10.1 Objetivo de la etapa

El site puede generar un único PDF con todos los viáticos de un período, agrupados por paciente y visita, con totales globales.

**Duración estimada:** 2 semanas

La lógica es idéntica al PDF por paciente pero iterando sobre todos los pacientes del protocolo en el período. El template `pdf_site.html` agrega una primera página de resumen ejecutivo con totales por paciente y categoría, seguida de los detalles de cada paciente.

### 10.2 Resultado esperado al final de la Etapa 6

1. El coordinador puede seleccionar protocolo + período y generar el PDF consolidado.
2. El PDF tiene una primera página de resumen (totales por paciente y categoría).
3. A continuación van los detalles de cada paciente.
4. Se puede exportar también a Excel (openpyxl) como alternativa.

**Checkpoint de validación:**
```
Checklist Etapa 6:
[ ] /reports/site/ permite seleccionar protocolo y período
[ ] El PDF consolidado se genera y descarga correctamente
[ ] La primera página es un resumen ejecutivo con todos los totales
[ ] Cada paciente tiene su sección con sus gastos detallados
[ ] La exportación a Excel (.xlsx) también funciona
```

***

## 11. ETAPA 7 — CIERRE DE PERÍODO Y AUDITORÍA

### 11.1 Objetivo de la etapa

El coordinador puede cerrar un período, lo que bloquea todos los gastos del período para edición. El sistema genera automáticamente el PDF final al cierre. El historial de auditoría es completo y visible.

**Duración estimada:** 2 semanas

### 11.2 Lógica de cierre de período

```python
# apps/expenses/services.py — Añadir

from django.db import transaction
from django.utils import timezone

def close_period(period_id, user):
    """
    Cierra un período de rendición.
    - Valida que no haya gastos pendientes de revisión
    - Cambia todos los aprobados a 'settled'
    - Bloquea el período para edición
    - Genera PDF automáticamente
    """
    from .models import ExpensePeriod, Expense, AuditLog
    
    period = ExpensePeriod.objects.get(id=period_id)
    
    if not period.is_editable:
        raise ValueError("El período ya está cerrado.")
    
    # Verificar que no haya gastos pendientes
    pending = Expense.objects.filter(
        period=period, status='pending_review'
    ).count()
    
    if pending > 0:
        raise ValueError(
            f"No se puede cerrar el período. Hay {pending} gasto(s) pendiente(s) de revisión."
        )
    
    with transaction.atomic():
        # Cambiar gastos aprobados a liquidados
        approved_expenses = Expense.objects.filter(
            period=period, status='approved'
        )
        for expense in approved_expenses:
            old_status = expense.status
            expense.status = 'settled'
            expense.save()
            AuditLog.objects.create(
                expense=expense,
                action='settled',
                from_status=old_status,
                to_status='settled',
                comment=f'Liquidado al cerrar período: {period.name}',
                performed_by=user,
            )
        
        # Cerrar el período
        period.status = 'closed'
        period.closed_by = user
        period.closed_at = timezone.now()
        period.save()
    
    return period
```

### 11.3 Vista de auditoría de un gasto

```python
# apps/expenses/views.py

class ExpenseDetailView(LoginRequiredMixin, DetailView):
    model = Expense
    template_name = 'expenses/detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['audit_logs'] = self.object.audit_logs.all().order_by('performed_at')
        context['ticket_files'] = self.object.ticket_files.all()
        
        from .services import ExpenseValidationService
        context['validation_alerts'] = ExpenseValidationService().validate(self.object)
        
        return context
```

### 11.4 Resultado esperado al final de la Etapa 7

1. El coordinador puede cerrar un período desde la pantalla de gestión de períodos.
2. Si hay gastos pendientes de revisión, el sistema bloquea el cierre con un mensaje claro.
3. Al cerrar, todos los gastos aprobados pasan a "Liquidado".
4. El período cerrado muestra un ícono de candado y no permite editar nada.
5. Cada gasto tiene un historial completo e inmutable de todos sus cambios.

**Checkpoint de validación:**
```
Checklist Etapa 7:
[ ] /periods/ muestra la lista de períodos con su estado
[ ] No se puede cerrar un período con gastos pendientes
[ ] Al cerrar, los gastos aprobados pasan a "liquidado"
[ ] El período cerrado no permite editar gastos
[ ] El detalle de cada gasto muestra el historial de auditoría completo
[ ] El AuditLog registra el cierre del período en cada gasto afectado
```

***

## 12. ETAPA 8 — PULIDO Y HARDENING

### 12.1 Objetivo de la etapa

El sistema está listo para uso real. Tests básicos, documentación mínima, revisión de seguridad y preparación para segundo cliente (multisite).

**Duración estimada:** 2 semanas

### 12.2 Checklist de seguridad

```
Seguridad — verificar antes de ir a producción:
[ ] HTTPS activo (Railway lo provee automáticamente)
[ ] SECRET_KEY diferente en producción y no en el repo
[ ] DEBUG=False en producción
[ ] ALLOWED_HOSTS configurado correctamente
[ ] Archivos de media servidos desde S3 (no desde el servidor)
[ ] Permisos verificados: asistente NO puede aprobar, coordinador NO puede borrar AuditLog
[ ] CSRF activo en todos los formularios
[ ] Rate limiting en el endpoint de login (django-ratelimit)
[ ] Logs de errores configurados (Sentry o similar)
[ ] Backup automático de la base de datos (Railway lo hace cada 24h)
```

### 12.3 Tests críticos a implementar

```python
# apps/expenses/tests.py

from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()

class ExpenseWorkflowTest(TestCase):
    """Tests del flujo principal de un gasto."""
    
    def test_expense_status_transitions(self):
        """Un gasto debe pasar por los estados correctos."""
        # Crear contexto
        # draft → ocr_pending → pending_review → approved → settled
        pass
    
    def test_coordinator_cannot_be_bypassed(self):
        """Un asistente no puede aprobar gastos."""
        pass
    
    def test_audit_log_is_created_on_state_change(self):
        """Cada cambio de estado debe generar un AuditLog."""
        pass
    
    def test_closed_period_blocks_edits(self):
        """Un período cerrado no permite editar sus gastos."""
        pass
    
    def test_date_validation_outside_window(self):
        """Un ticket con fecha fuera de ventana debe generar alerta."""
        pass
```

### 12.4 Preparación para multisite

Para cuando llegue el segundo cliente (otro site de investigación), los modelos ya tienen las bases. Solo añadir:

```python
# apps/protocols/models.py — añadir al Protocol

class Site(models.Model):
    """
    Site de investigación. Cuando haya múltiples sites,
    cada Protocol pertenece a un Site.
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
```

Y agregar `site = models.ForeignKey(Site, ...)` en `Protocol`. Los usuarios del Site A no verán los datos del Site B. Django Groups + custom QuerySet managers manejan esto.

***

## 13. GUÍA DE VERIFICACIÓN POR ETAPA

Esta tabla es tu checklist maestro. Después de cada etapa, verificar todos los puntos antes de mostrar al cliente.

| Etapa | Entregable al cliente | Criterio de éxito |
|---|---|---|
| 1 — Fundación | Login + Admin + Deploy | El cliente puede ver el admin y navegar a /dashboard/ |
| 2 — Captura | Carga de ticket desde celular | El asistente puede subir una foto y el gasto aparece en el sistema |
| 3 — OCR | Extracción automática de datos | Los campos se pre-completan con los datos del ticket |
| 4 — Validaciones | Dashboard del coordinador + aprobaciones | El coordinador puede aprobar/rechazar con un clic |
| 5 — PDF Paciente | PDF descargable por paciente | El PDF tiene el formato correcto y las imágenes |
| 6 — PDF Site | PDF consolidado del site | Un PDF con todos los pacientes del período |
| 7 — Cierre | Cierre de período + auditoría | El coordinador cierra y el PDF final se genera automáticamente |
| 8 — Hardening | Sistema listo para producción | Tests pasando, seguridad verificada, segundo site posible |

***

## 14. PROMPTS LISTOS PARA CLAUDECODE / CODEX

### Prompt Etapa 1 — Crear proyecto Django

```
Creá un proyecto Django 5.1 llamado "proyecto_cordoba" con la siguiente estructura:
- Configuración en config/settings/ (base.py, development.py, production.py)
- 6 apps en apps/: accounts, protocols, patients, expenses, reports, dashboard
- AUTH_USER_MODEL = 'accounts.User' con campos: site_name, phone, external_id, created_at
- Configuración para PostgreSQL con django-environ
- Django allauth instalado para autenticación
- Whitenoise para archivos estáticos
- LANGUAGE_CODE = 'es-ar', TIME_ZONE = 'America/Argentina/Buenos_Aires'
- manage.py en la raíz del proyecto

Los modelos que necesito son exactamente estos: [PEGAR MODELOS DE LA SECCIÓN 4]

Configurá el admin de Django para mostrar todos los modelos con los fieldsets documentados.
Generá también los urls.py base y el requirements.txt completo.
```

### Prompt Etapa 2 — Captura de ticket con HTMX

```
Tengo un proyecto Django con los modelos Expense, TicketFile, Visit, Patient y Protocol ya creados.

Necesito crear la vista de carga de gastos en apps/expenses/views.py y templates/expenses/create.html con las siguientes características:
- Formulario de 5 pasos en una sola página usando HTMX
- Paso 1: selector de protocolo (carga los activos)
- Paso 2: selector de paciente (carga dinámicamente al elegir protocolo, via HTMX GET a /expenses/patients/?protocol_id=X)
- Paso 3: selector de visita (carga dinámicamente al elegir paciente, via HTMX GET a /expenses/visits/?patient_id=X)
- Paso 4: campos del gasto (categoría, fecha, monto, moneda)
- Paso 5: upload de foto con preview nativo (input file, accept="image/*", capture="environment")
- Al confirmar: crear Expense + TicketFile, disparar task Celery process_ocr_for_ticket.delay(ticket.id)
- La página debe verse bien en móvil (375px) y desktop
- Usar Tailwind CSS via CDN y HTMX 2.x
```

### Prompt Etapa 3 — Celery + OCR

```
Necesito integrar OCR al proyecto Proyecto Córdoba.

Creá los siguientes archivos:
1. config/celery.py — Configuración de Celery con Redis como broker
2. apps/expenses/tasks.py — Task process_ocr_for_ticket(ticket_file_id) que:
   - Obtiene el TicketFile por id
   - Llama a OCRService().process_ticket(file_url)
   - Guarda los resultados en los campos ocr_extracted_* del TicketFile
   - Pre-completa los campos del Expense si la confianza es > 0.7
   - Actualiza el status del Expense a 'pending_review'
   - Crea un AuditLog con action='ocr_completed'
   - Maneja errores con retry (max 3 intentos)
3. apps/expenses/services.py — Clase OCRService con:
   - Integración con Veryfi API (CLIENT_ID, CLIENT_SECRET, USERNAME, API_KEY desde env)
   - Método _parse_veryfi_response() que extrae: fecha, monto, vendedor, CUIT (regex \d{2}-\d{8}-\d), número de comprobante, tipo
   - Método _mock_result() para desarrollo sin API key
   - Dataclass OCRResult con todos los campos y sus confidence scores

La task debe ser idempotente: si ya fue procesada, no volver a procesar.
```

### Prompt Etapa 4 — Dashboard del coordinador

```
Necesito el dashboard del coordinador en Proyecto Córdoba.

Creá:
1. apps/dashboard/views.py — CoordinatorDashboardView con:
   - Lista de gastos con status='pending_review'
   - Contadores: observados, aprobados hoy, rechazados hoy
   - Cada gasto pre-carga: visita, paciente, protocolo, ticket_files, alertas de validación

2. apps/expenses/views.py — 3 endpoints HTMX:
   - POST /expenses/<id>/approve/ → cambia status a 'approved', crea AuditLog, retorna HTML actualizado de la fila
   - POST /expenses/<id>/reject/ → idem con 'rejected'
   - POST /expenses/<id>/observe/ → idem con 'observed'
   Todos requieren que el usuario sea coordinator o site_admin.

3. apps/expenses/services.py — Clase ExpenseValidationService con validaciones:
   - Fecha fuera de ventana de visita
   - Monto excede tope del protocolo
   - Posible duplicado (mismo paciente, visita, categoría, fecha, monto)

4. templates/dashboard/coordinator.html — Tabla de gastos pendientes con:
   - Por cada gasto: código paciente, visita, categoría, fecha, monto, badge de alertas, preview del ticket, botones Aprobar/Rechazar/Observar
   - Los botones usan HTMX: hx-post, hx-swap="outerHTML", hx-confirm para rechazar/observar
   - Modal HTMX para el coordinador agregue comentario al aprobar/rechazar/observar
```

### Prompt Etapa 5 — PDF por paciente

```
Necesito el generador de PDF por paciente en Proyecto Córdoba usando WeasyPrint.

Creá:
1. apps/reports/generators.py — Función generate_patient_pdf(patient_id, period_id, request):
   - Filtra Expenses del paciente con status in ['approved', 'settled', 'exported']
   - Convierte imágenes de TicketFile a base64 para embeber en el PDF
   - Calcula totales por categoría y total general
   - Renderiza templates/reports/pdf_patient.html con todos los datos
   - Retorna HttpResponse con content_type='application/pdf'

2. templates/reports/pdf_patient.html — Template HTML para WeasyPrint:
   - Header: logo del site (si existe), nombre del protocolo, código del paciente
   - Aviso de confidencialidad
   - Tabla de metadatos: protocolo, código paciente, sponsor, fase, período
   - Tabla de gastos: fecha, visita, categoría, proveedor, CUIT, nro. comprobante, tipo, IVA, monto, imagen miniatura del ticket (base64)
   - Tabla de totales por categoría + TOTAL GENERAL
   - Footer: fecha y hora de generación, usuario, versión, número de página

3. apps/reports/views.py — Vista que recibe patient_id y period_id y llama al generador

El PDF debe verse profesional, en A4, con paginación automática.
El nombre del archivo descargado debe ser: viaticos_{patient_code}_{protocol_code}.pdf
```

### Prompt Etapa 7 — Cierre de período

```
Necesito la funcionalidad de cierre de período en Proyecto Córdoba.

Creá:
1. apps/expenses/services.py — Función close_period(period_id, user):
   - Verifica que no haya gastos con status='pending_review' en el período
   - Si los hay, lanza ValueError con mensaje claro indicando cuántos hay
   - Usa transaction.atomic() para:
     a) Cambiar todos los gastos con status='approved' a 'settled'
     b) Crear AuditLog para cada gasto con action='settled'
     c) Cambiar period.status a 'closed', guardar closed_by y closed_at
   - Retorna el período cerrado

2. apps/expenses/views.py — Vista POST /periods/<id>/close/:
   - Llama a close_period(period_id, request.user)
   - Si hay error (ValueError), muestra mensaje de error con HTMX
   - Si éxito, redirige a la lista de períodos con mensaje de éxito
   - Solo accesible para coordinator y site_admin

3. templates/expenses/periods.html — Lista de períodos con:
   - Estado visual: candado cerrado para 'closed', badge verde para 'open'
   - Botón "Cerrar período" con confirmación HTMX
   - Contador de gastos pendientes de revisión por período (advertencia si > 0)
   - Enlace para generar PDF del período

4. La vista de detalle de un Expense debe mostrar el AuditLog completo con:
   - Cada entrada: acción, estado anterior, estado nuevo, comentario, usuario, fecha/hora
   - Diseño tipo timeline vertical
   - El AuditLog debe ser inmutable (sin botones de edición/borrado)
```

***

## APÉNDICE A — Variables de entorno completas

```
# .env.example — Copiar como .env y completar

# Django
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de datos
DATABASE_URL=postgresql://user:password@localhost:5432/cordoba_dev

# Redis (para Celery)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Almacenamiento de archivos (desarrollo: local, producción: S3 o Cloudinary)
USE_S3=False
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=us-east-1

# OCR — Veryfi
VERYFI_CLIENT_ID=
VERYFI_CLIENT_SECRET=
VERYFI_USERNAME=
VERYFI_API_KEY=

# Email (para notificaciones de cambio de estado)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend  # dev
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=

# Site
SITE_NAME=CINME
```

***

## APÉNDICE B — Comandos frecuentes

```bash
# Desarrollo local
python manage.py runserver                        # Levantar servidor
python manage.py makemigrations                   # Crear migraciones
python manage.py migrate                          # Aplicar migraciones
python manage.py createsuperuser                  # Crear admin
celery -A config worker --loglevel=info           # Levantar worker OCR
celery -A config flower                           # Monitor de tareas (opcional)

# Deploy en Railway
railway login                                     # Login
railway link                                      # Linkear proyecto
railway up                                        # Deploy
railway run python manage.py migrate              # Migrar en producción
railway run python manage.py createsuperuser      # Admin en producción

# Utilidades
python manage.py shell                            # Shell Django
python manage.py test apps/expenses/              # Tests de la app expenses
python manage.py collectstatic                    # Recopilar estáticos
```

***

## APÉNDICE C — Diagrama de estados del gasto

```
                        ┌─────────────┐
                        │   BORRADOR  │
                        └──────┬──────┘
                               │ asistente confirma
                               ▼
                      ┌────────────────┐
                      │  OCR PENDING   │ ← Celery procesando
                      └───────┬────────┘
                               │ OCR completa
                               ▼
                     ┌──────────────────┐
                     │ PENDIENTE        │ ← Coordinador debe revisar
                     │ DE REVISIÓN      │
                     └────┬──────┬──────┘
                          │      │      │
              coordinador │      │      │ coordinador
              aprueba      │      │      │ rechaza
                          ▼      │      ▼
                    ┌──────────┐ │ ┌──────────┐
                    │ APROBADO │ │ │ RECHAZADO│
                    └────┬─────┘ │ └──────────┘
                         │       │ coordinador
                 cierre   │       │ observa
                período   │       ▼
                          │  ┌──────────┐
                          │  │ OBSERVADO│ → asistente corrige → PENDIENTE REVISIÓN
                          │  └──────────┘
                          ▼
                    ┌──────────┐
                    │ LIQUIDADO│ ← período cerrado
                    └────┬─────┘
                         │ PDF exportado
                         ▼
                    ┌──────────┐
                    │ EXPORTADO│ ← registro final
                    └──────────┘
```

***

## APÉNDICE D — Integración futura con Alpha CR

Cuando llegue el momento de integrar con Alpha CR, los puntos de contacto ya están preparados en el modelo de datos:

| Entidad | Campo en Proyecto Córdoba | Fuente en Alpha CR |
|---|---|---|
| Usuario | `external_id` | ID de usuario en Alpha CR |
| Protocolo | `external_protocol_id` | ID del protocolo en Alpha CR |
| Paciente | `external_patient_id` | ID del paciente en Alpha CR |
| Visita | `external_visit_id` | ID de la visita en Alpha CR |

La integración puede ser:
1. **V1 (manual):** Export CSV de Alpha CR → import en Proyecto Córdoba con comando de management `python manage.py import_visits_from_csv visits.csv`
2. **V2 (automática):** Webhook desde Alpha CR → endpoint POST en Proyecto Córdoba que crea/actualiza visitas automáticamente
3. **V3 (nativa):** SDK de Alpha CR integrado como fuente de datos en tiempo real