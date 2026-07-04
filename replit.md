# Proyecto Córdoba — Viáticos para Investigación Clínica

Sistema web de gestión de viáticos para pacientes de ensayos clínicos. Asistentes suben tickets de gastos, el OCR extrae datos, coordinadores aprueban, y el sistema genera PDFs GCP-compliant por paciente, por visita y consolidados por site. Incluye tablero global de control de gasto (`/dashboard/tablero/`).

## Run & Operate

- `cd cordoba && python manage.py runserver 0.0.0.0:${PORT:-8000}` — servidor de desarrollo (workflow principal)
- `cd cordoba && python manage.py migrate` — aplicar migraciones
- `cd cordoba && python manage.py makemigrations` — generar nuevas migraciones
- `cd cordoba && python manage.py createsuperuser` — crear superusuario
- `cd cordoba && python manage.py shell` — shell interactivo de Django
- `powershell -ExecutionPolicy Bypass -File scripts\prepare-client-demo.ps1` — validar y migrar antes de demo
- `powershell -ExecutionPolicy Bypass -File scripts\seed-client-demo.ps1` — crear/resetear datos y usuarios de demo
- `powershell -ExecutionPolicy Bypass -File scripts\start-client-demo.ps1` — levantar demo local en `localhost:8000`
- `powershell -ExecutionPolicy Bypass -File scripts\start-client-demo-tunnel.ps1` — abrir URL pública temporal con ngrok

## Stack

- **Backend:** Django 5.1 + PostgreSQL (via django-environ)
- **Frontend:** Django Templates + HTMX 2.x + Tailwind (vendorizado en `static/js/tailwind.min.js`, sin CDN) + Lucide Icons
- **Auth:** django-allauth con 4 grupos: `site_admin`, `coordinator`, `assistant`, `auditor`
- **Estáticos:** Whitenoise
- **Async OCR (Etapa 2):** Celery + Redis (no configurado aún)
- **PDFs (Etapa 4):** WeasyPrint (no configurado aún)

## Where things live

- `cordoba/` — raíz del proyecto Django
- `cordoba/config/settings/` — configuración por entorno (base, development, production)
- `cordoba/apps/accounts/` — usuarios con roles vía Django Groups
- `cordoba/apps/protocols/` — protocolos y tipos de visita
- `cordoba/apps/patients/` — pacientes (solo códigos, NUNCA nombres reales) y visitas
- `cordoba/apps/expenses/` — gastos, tickets, períodos, auditoría
- `cordoba/apps/dashboard/` — vistas por rol
- `cordoba/templates/` — templates base y por app

## Architecture decisions

- **Privacidad del paciente:** solo `patient_code` e iniciales, NUNCA nombre completo. Los datos identificatorios viven en Alpha CR (futura integración).
- **AuditLog inmutable:** `has_add_permission`, `has_change_permission`, `has_delete_permission` retornan `False` en admin. Nunca UPDATE/DELETE en producción.
- **Roles via Django Groups:** `site_admin`, `coordinator`, `assistant`, `auditor`. Propiedades `is_coordinator`, `is_assistant`, `is_site_admin`, `is_auditor` en el modelo User.
- **Período cerrado:** un `ExpensePeriod` con `status='closed'` no puede modificarse (lógica de negocio, Etapa 5).
- **AUTH_USER_MODEL = 'accounts.User'** — cambiar después del primer migrate requiere nueva base de datos.

## Product

- Asistentes cargan fotos de tickets desde mobile (375px mobile-first)
- OCR extrae monto, fecha, comercio automáticamente
- Coordinadores aprueban/rechazan/observan desde su dashboard
- Al cerrar un período, se generan PDFs por paciente + PDF consolidado del site
- Diseñado para auditoría GCP/ANMAT

## User preferences

- Stack fijo: Django + HTMX + Tailwind CDN. NO React, NO Node.js.
- Español argentino en toda la UI y mensajes.
- Mobile-first: diseñar primero para 375px.
- Seguridad no negociable: códigos de paciente, AuditLog inmutable, períodos cerrados no modificables.

## Reportes para sponsor

- `/reports/` — tres reportes, todos POST + CSRF, todos anonimizados (solo `patient_code`):
  - **PDF por paciente** (`reports:patient_pdf`): gastos aprobados + galería de comprobantes + resumen por visita.
  - **PDF por visita** (`reports:visit_pdf`): todos los pacientes que hicieron esa visita del protocolo, con comprobantes.
  - **PDF consolidado / Excel** (`reports:site_pdf`, `reports:site_excel`): resumen ejecutivo por paciente + por visita.
- Al generar un reporte los gastos pasan a `exported` y queda AuditLog.
- xhtml2pdf: el pie de página se declara con `-pdf-frame-content: <id-del-div>` DENTRO del `@frame` (no como estilo inline del div); si no, el contenido del cuerpo fluye al frame del pie y rompe con LayoutError. Las imágenes no aceptan `width: %`.

## Diseño

- Paleta cálida farma definida en `templates/base.html` (tailwind.config): `primary` verde petróleo, `secondary` salvia, `accent` terracota; fondo crema `#f8f6f1`; tema noche verde petróleo oscuro.
- Todos los assets JS son locales (`static/js/`): tailwind, htmx, lucide, chart.umd — la app funciona sin internet.

## Gotchas

- `DJANGO_SETTINGS_MODULE=config.settings.development` debe estar en el entorno.
- `PORT=8000` debe estar seteado para que el workflow funcione.
- Las migraciones de `accounts` (0001, 0002) son MANUALES — no regenerar con makemigrations sin cuidado.
- Para agregar grupos de permisos granulares por modelo, editar la migración `0002_create_groups.py`.
- `allauth` requiere `django.contrib.sites` y `SITE_ID = 1`.
- El `staticfiles/` directory es autogenerado por `collectstatic` — no commitear.

## Pointers

- Referencia completa del proyecto: `attached_assets/Proyecto_Córdoba_—_Manual_Completo_de_Desarrollo_(1)_1782532076667.md`
- Template de env vars: `cordoba/.env.example`
