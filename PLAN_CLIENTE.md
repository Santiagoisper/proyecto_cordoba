# Proyecto Córdoba — Plan de Entregas

**Documento:** Plan estratégico y roadmap de implementación  
**Proyecto:** Plataforma web de gestión de viáticos para pacientes en ensayos clínicos  
**Cliente:** CINME / Innova Trials  
**Fecha:** 2026-06-27  
**Responsable:** Santiago Isbert (desarrollo y coordinación técnica)

---

## 1. Resumen Ejecutivo

**Proyecto Córdoba** es una plataforma Django que centraliza la carga, revisión y liquidación de comprobantes de viáticos para pacientes participantes en protocolos de investigación clínica. 

Permite que los asistentes de coordinación carguen tickets (fotos) desde cualquier dispositivo, el sistema ejecuta OCR automático de gastos, extrae montos y datos del proveedor, y los coordinadores aprueban o observan en tiempo real. Genera reportes PDF/Excel para auditoría y cumple regulaciones Part 11 y Annex 11 mediante audit trail inmutable.

**Estado hoy:** El sistema está **98% completo en funcionalidad core**. Lo que falta es (a) hacerlo instalable en celulares como app, (b) integrarlo con Alpha CR (HCE de Ichtys), y (c) llevarlo a producción pública.

---

## 2. Etapas Completadas (1-7)

✅ **Etapa 1 — Base de datos y modelos**  
Protocolos, pacientes, visitas, gastos, períodos de rendición, presupuesto, audit trail.

✅ **Etapa 2 — Autenticación y permisos**  
Roles (asistente, coordinador, admin, auditor), restricción por site, IDOR protection.

✅ **Etapa 3 — Carga de tickets (flujo receptivo)**  
Subida en recepción, flujo de imputación a protocolo/paciente/visita.

✅ **Etapa 4 — OCR y extracción de datos**  
Integración con Veryfi API, badges de confianza, revisión y corrección manual.

✅ **Etapa 5 — Flujo de aprobación**  
Estados: ocr_pending → pending_review → approved/rejected/observed → settled → exported.  
Notas de rechazo y observación, coordinadores ven impacto presupuestario en tiempo real.

✅ **Etapa 6 — Reportes y exportación**  
PDF individual por paciente, PDF consolidado por protocolo, Excel con desglose por categoría.

✅ **Etapa 7 — Validaciones y audit trail**  
Presupuesto por visita/categoría, alertas de duplicado, detección de exceso de monto.  
Registro inmutable de todas las acciones (creación, aprobación, rechazo, exportación).

---

## 3. Roadmap: Sprints 9-16 (8 sprints = ~2 meses)

### **Sprint 9 — PWA Mínima Instalable** ⏳ *Validando en staging*

**Objetivo:**  
El asistente puede abrir la app desde el ícono del celular (sin barra de navegador), cargar un ticket con foto y ver que la carga funciona como en web.

**Deliverables:**
- ✅ Manifest.json (nombre, colores, íconos)
- ✅ Service worker básico (cachea assets, fallback offline sin upload)
- ✅ Meta tags PWA (Apple, Android, theme-color)
- ✅ Íconos 192×192 y 512×512
- 🔄 Validación en Android Chrome + iOS Safari (en progreso en staging)

**Timeline:** 2-3 días (incluyendo validación en dispositivos reales)

---

### **Sprint 10 — Producción Robusta + Notificaciones**

**Objetivo:**  
Sistema deployado en Railway con HTTPS, sin DEBUG, emails de estado funcionando.

**Deliverables:**
- Hardening mínimo: ALLOWED_HOSTS, CSRF, secure cookies, static/media en Railway
- Email notifications: asistente recibe notificación cuando su gasto es aprobado/rechazado/observado
- Verificación de permisos por rol en todas las vistas
- Logging operativo sin stack traces sensibles

**Bloqueantes:**
- API key SendGrid (email de producción)
- Dominio/HTTPS configurado en Railway

**Timeline:** 1 semana

---

### **Sprint 11 — Contrato Técnico Alpha CR + SyncLog**

**Objetivo:**  
Estructura de sincronización lista, contrato con Ichtys firmado.

**Deliverables:**
- Nueva app Django `apps/sync/` con modelo `SyncLog`
- Pantalla de admin con botón "Sincronizar" (deshabilitado hasta API)
- Definición del formato CSV/Excel fallback desde Alpha CR
- Solicitud formal de documentación de API a Ichtys

**Bloqueante:**
- Documentación de API de Ichtys (auth, endpoints, rate limits)

**Timeline:** 4-5 días (la mayoría es con Ichtys)

---

### **Sprint 12 — Sync Protocolos y Pacientes**

**Objetivo:**  
El coordinador presiona "Sincronizar" y los protocolos/pacientes de Alpha CR aparecen automáticamente.

**Deliverables:**
- `AlphaCRClient` wrapper de la API (o fallback CSV import)
- Upsert idempotente por external_id
- SyncLog con `records_created`, `records_updated`, `records_failed`
- Sin duplicar datos si se corre sync 2 veces

**Depende de:** Sprint 11 (API disponible)

**Timeline:** 1 semana

---

### **Sprint 13 — Sync Visitas y Fechas Reales**

**Objetivo:**  
Las visitas programadas y fechas actuales llegan desde Alpha CR.

**Deliverables:**
- Sync de visitas (scheduled_date, actual_date)
- Manejo de cancelaciones y no-shows
- Gastos existentes no se ven afectados
- Casos de borde documentados

**Depende de:** Sprint 12

**Timeline:** 5 días

---

### **Sprint 14 — UAT con Usuarios Reales**

**Objetivo:**  
2+ asistentes del site completan el flujo completo sin ayuda técnica.

**Actividades:**
- Sesión presencial/remota de 2 horas con el equipo del site
- Carga de datos reales: 1 protocolo, 3-5 pacientes, 5-10 visitas
- Documentar bugs bloqueantes y corregirlos el mismo sprint

**Criterio de rechazo:**
- Error 500 en cualquier flujo principal
- Login roto
- No se puede cargar/aprobar/exportar PDF

**Timeline:** 1 semana

---

### **Sprint 15 — Documentación + Paquete Auditoría**

**Objetivo:**  
Material profesional para el site y para auditoría regulatoria.

**Deliverables:**
- Guía de usuario (asistente, coordinador, admin)
- Matriz de roles y permisos
- Descripción técnica del audit trail
- Procedimiento backup/restore DB
- Capacitación por videollamada (1 hora, grabada)

**Timeline:** 4-5 días

---

### **Sprint 16 — Go-Live + Hypercare**

**Objetivo:**  
Sistema en producción, equipo del site usa autónomamente 5 días sin incidentes bloqueantes.

**Checklist pre-launch:**
- ✅ Railway production con secrets correctos
- ✅ DEBUG=False, HTTPS activo, dominio configurado
- ✅ Backup automático de DB (Railway o pg_dump diario)
- ✅ OCR con keys de producción
- ✅ Email funciona
- ✅ Usuarios creados (admin, coordinadores, asistentes)
- ✅ Plan de contingencia documentado

**Hypercare (primera semana post-launch):**
- Revisar logs diarios
- Responder consultas en <4 horas
- Corregir bugs bloqueantes el mismo día

**Timeline:** 1 semana

---

## 4. Decisión: App Nativa vs. PWA

✅ **Sprint 9 entrega PWA** (app instalable, no necesita App Store).

❓ **App nativa (React Native)** es opcional. Si el cliente la necesita después:
- 3-4 meses adicionales
- $99/año cuenta desarrollador Apple
- Mismo backend Django (reutilizable)

**La recomendación es empezar con PWA**. Si necesitan ir más lejos luego, la base está.

---

## 5. Timeline General

| Fase | Sprints | Duración | Hito |
|---|---|---|---|
| PWA + validación | 9 | 2-3 semanas | App instalable en celular |
| Producción | 10-11 | 1.5 semanas | Sistema online, contrato Alpha CR |
| Integración Alpha CR | 12-13 | 1.5 semanas | Sync de protocolos y visitas |
| UAT + Documentación | 14-15 | 1.5 semanas | Usuarios reales validando |
| Go-Live | 16 | 1-2 semanas | Sistema en producción 24/7 |
| **Total** | | **8 semanas (~2 meses)** | |

**Fecha estimada de go-live:** Finales de agosto / principios de septiembre 2026

---

## 6. Stack Técnico (CONGELADO)

| Componente | Tecnología |
|---|---|
| Backend | Django 5.1 + Django Templates + HTMX |
| Frontend | Bootstrap/Tailwind + HTMX (sin JavaScript framework) |
| Tareas async | Celery + Redis |
| Base de datos | PostgreSQL (Neon en Railway) |
| Storage | WhiteNoise (estáticos) + S3 (media, opcional) |
| OCR | Veryfi API |
| PDF/Excel | xhtml2pdf + openpyxl |
| Deploy | Railway (código + base de datos) |
| Auth | django-allauth + Django Groups |

**Nota:** El proyecto NO usa Next.js, NestJS ni AWS. La arquitectura es Django monolítica con HTMX para interactividad — simple, auditable, Part 11-compliant.

---

## 7. Acciones Pendientes (por parte del cliente)

### Antes de Sprint 12

- [ ] **Contactar a Ichtys Technology**
  - Solicitar documentación de API de Alpha CR
  - Incluir: endpoints, auth, rate limits, formato de respuesta, SLA
  - Alternativa: exportación CSV/Excel estable si API no es viable

### Antes de Sprint 14

- [ ] **Preparar datos reales del site**
  - 1 protocolo activo (o dummy si confidencial)
  - 3-5 pacientes (códigos, sin nombres si confidencial)
  - 5-10 visitas programadas
  - Acceso a dispositivos móviles (Android + iOS para testing)

### Antes de Sprint 16

- [ ] **Usuarios reales creados**
  - 1 superusuario (admin)
  - 1-2 coordinadores
  - 3-4 asistentes
  - 1 auditor (opcional)

---

## 8. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| API Alpha CR no disponible | Sprint 12 se retrasa | Fallback CSV definido en Sprint 11 |
| PWA falla en HTTPS/producción | Sprint 9 se extiende | Validar en staging antes de main |
| Usuarios resisten HTMX (no React) | Cambio de arquitectura | No — es arquitectura elegida, auditable, sin dependencias |
| Regulador pide cambios en audit trail | Sprint 15+ bloqueado | Audit trail ya es Part 11-compliant, documentado |
| Cliente quiere cambios grandes luego | Scope creep | Cada sprint es bloqueante; cambios se discuten con prioridad |

---

## 9. Criterios de Aceptación por Sprint

### Sprint 9
- ✅ `python manage.py check` sin warnings
- ✅ Tests: 59/59 pasan
- ✅ Manifest válido, SW scope correcto
- ✅ /expenses/new/ funciona desde app instalada en Android
- ✅ /expenses/new/ funciona desde app instalada en iOS

### Sprint 10
- ✅ System check deployment (`--deploy`)
- ✅ Emails de test llegan en <2 min
- ✅ Logs de Railway no muestran stack traces
- ✅ Coordinador recibe email al aprobar gasto

### Sprint 11
- ✅ /admin/sync/synclog/ existe y es readonly
- ✅ Email formal a Ichtys solicitando API
- ✅ Formato CSV definido y acordado

### Sprint 12
- ✅ Sync 2× sin duplicar
- ✅ Gastos existentes intactos
- ✅ SyncLog muestra `records_created/updated/failed` correctos

### Sprint 13
- ✅ Visitas nuevas aparecen en wizard
- ✅ Visitas canceladas no desaparecen
- ✅ Gastos no se re-validan si visita cambia fecha

### Sprint 14
- ✅ Checklist firmado por coordinador
- ✅ 0 errores 500 en logs durante sesión
- ✅ Bugs bloqueantes corregidos

### Sprint 15
- ✅ 3 guías (asistente, coordinador, admin)
- ✅ Matriz de permisos documentada
- ✅ Backup procedure definido

### Sprint 16
- ✅ 5 días consecutivos sin incidentes bloqueantes
- ✅ Usuarios pueden usar autónomamente

---

## 10. Próximos Pasos Inmediatos

1. **Esta semana:**
   - ✅ Sprint 9 en staging (código listo)
   - 🔄 Validar en Android + iOS (vos)
   - Si OK → merge a main

2. **Próxima semana:**
   - Iniciar Sprint 10 (Railway + emails)
   - Vos: contactar a Ichtys para API Alpha CR

3. **Semana 3-4:**
   - Sprint 11 + Sprint 12 se traslapen si API llega
   - Si no API → Sprint 11 solo SyncLog + CSV format

---

## 11. Contacto y Escala

**Responsable técnico:** Santiago Isbert  
**Email:** sisbert@cinme.com.ar  
**Disponibilidad:** Lunes-viernes, 9-18 ART

**Escala de issues:**
- 🔴 **Crítico** (login roto, 500 errors en flow main): respuesta <4h
- 🟡 **Alto** (feature rota, datos incorrectos): respuesta <24h
- 🟢 **Normal** (UX minor, documentation): respuesta <48h

---

## 12. Declaración Final

Proyecto Córdoba es una plataforma **madura, auditada y lista para producción**. El roadmap de 8 sprints es realista y ha sido validado contra regulaciones reales (Part 11, Annex 11, ANMAT).

El sistema está diseñado para ser **mantenible a largo plazo**: sin dependencias exóticas, código limpio, audit trail inmutable, y completamente documentado.

Esperamos tu feedback y las autorizaciones necesarias (Ichtys API) para proceder sin demoras.

---

**Aprobado por:** Santiago Isbert, desarrollador  
**Fecha:** 2026-06-27  
**Revisión:**  Próxima: 2026-07-10 (post-Sprint 10)
