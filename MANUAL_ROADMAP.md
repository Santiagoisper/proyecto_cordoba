# Proyecto Córdoba — Manual y Roadmap Maestro

**Plataforma de gestión de viáticos para pacientes de investigación clínica**
Cliente: CINME / Innova Trials · Responsable técnico: Santiago Isbert
Documento generado: 2026-07-09 · Estado del código: 89 tests en verde, `check --deploy` limpio

---

## 1. Qué es este sistema y por qué existe

Córdoba resuelve un problema concreto y caro: en un ensayo clínico el laboratorio reintegra los viáticos del paciente (taxi, comida, alojamiento para llegar al site), y ese reintegro tiene que quedar documentado con el comprobante original, imputado al protocolo y a la visita correcta, aprobado por un coordinador, y auditable ante ANMAT o el sponsor. Hoy eso se hace con planillas de Excel, fotos sueltas en teléfonos y carpetas físicas. Se pierde plata, se pierde tiempo y no sobrevive una inspección.

El sistema toma la foto del ticket, le lee los datos con OCR, deja que el asistente lo impute a un paciente y una visita, el coordinador lo aprueba o lo observa, y al cerrar el período genera el PDF y el Excel que el laboratorio necesita, con la foto del comprobante incrustada y un registro de auditoría que nadie puede alterar. La privacidad del paciente está en el núcleo del diseño: la base nunca guarda el nombre real, solo el código y las iniciales.

Lo importante para tu decisión de negocio: el núcleo funcional está terminado y probado. Lo que sigue no es "construir el producto", es "llevarlo a producción, blindarlo y sumarle lo que lo vuelve difícil de copiar". Este documento es el mapa de eso.

---

## 2. Lo que se calibró en esta sesión

Se hicieron siete pasadas sobre todo el código. No quedó línea librada al azar. Antes de esta sesión el sistema tenía un test end-to-end que fallaba y varias trampas silenciosas que no explotaban todavía pero iban a explotar en producción. Ahora corren 89 tests y el chequeo de despliegue de Django pasa limpio.

Estos son los hallazgos reales y sus correcciones, ordenados por gravedad.

| Severidad | Qué estaba mal | Qué se hizo |
|---|---|---|
| Crítico | El PDF y el Excel **sumaban pesos y dólares en un mismo total**, dando un número sin sentido si un paciente tenía tickets en dos monedas. Rompía el test end-to-end. | Los totales ahora se calculan y se muestran **separados por moneda**, en PDF y en Excel. Nunca se mezclan. |
| Crítico | `patients/views.py` no tenía **ningún control de acceso por site**: cualquier usuario logueado podía ver o editar cualquier paciente cambiando el número en la URL (IDOR). | Se agregó scoping por site en las cinco vistas de pacientes y visitas, con la misma regla fail-closed del resto del sistema. |
| Alto | El PDF tiraba `LayoutError` en la página 2 cuando el pie de página no entraba. | Se corrigió la altura del marco del pie. El PDF de varias páginas ahora se genera siempre. |
| Alto | El `AuditLog`, que es el corazón del cumplimiento Part 11, era inmutable **solo en el admin**. Cualquier código podía hacer `.save()` o `.delete()` sobre un registro. | Se hizo inmutable a nivel del modelo: `save()` sobre un registro existente y `delete()` levantan excepción. La inmutabilidad ya no depende de que nadie se equivoque. |
| Alto | El campo `ocr_confidence` estaba en la base pero **nunca se llenaba**. La confianza global del OCR se perdía. | La tarea de OCR ahora calcula y guarda la confianza global promediando los campos efectivamente extraídos. |
| Medio | Dos vistas HTMX (`htmx_load_patients`, `htmx_load_visits`) **creaban visitas en la base como efecto secundario de un simple GET**, y estaban duplicadas con las vistas buenas. | Se eliminaron junto con sus URLs. Un GET nunca debe mutar datos. |
| Medio | Toda la UI dependía del **CDN de Tailwind** (`cdn.tailwindcss.com`), que el propio Tailwind marca como no apto para producción, más `unpkg` y `jsdelivr`. Sin internet o con el CDN caído, la app se veía rota. | Se reemplazó por un build local compilado de Tailwind (`theme/`), y se bajaron Chart.js y Lucide al servidor. Cero dependencias de CDN externos. |
| Medio | El tema noche tenía una regla (`html.dark .rounded-lg { background: ... !important }`) que **pintaba de azul todos los elementos redondeados**, incluidos botones que no debían cambiar. | Se reescribió el tema noche como CSS compilado, tocando solo superficies estructurales y respetando los colores semánticos. |
| Medio | Los gráficos del dashboard del coordinador mostraban **datos ficticios hardcodeados** ("Protocolo A: 30%"). | Ahora consultan datos reales del site: comprobantes por protocolo y carga diaria de los últimos 14 días. |
| Medio | El OCR solo intentaba leer monto, fecha, proveedor, CUIT y número. No extraía **moneda ni IVA**. | El parser de Veryfi ahora también extrae moneda (ISO 4217), IVA y tipo de comprobante. |
| Bajo | No había **validación server-side** de los archivos subidos. El `accept` del HTML es solo una sugerencia del navegador. | Se agregó un validador que rechaza archivos de más de 15 MB y todo lo que no sea imagen o PDF, con tests. |
| Bajo | `ALLOWED_HOSTS` por defecto era `['*']` (acepta cualquier host). | Se restringió a localhost por defecto; en producción se define explícito por variable de entorno. |
| Bajo | Faltaban índices de base en los campos por los que más se filtra (`status`, `expense_date`). | Se agregaron índices en `Expense` y `AuditLog`. Las listas y dashboards escalan sin degradarse. |
| Bajo | La creación de un gasto con su ticket no era atómica: si fallaba a mitad, quedaban registros huérfanos. | Se envolvió en una transacción. O se crea todo, o no se crea nada. |

Además se endureció la configuración de producción (cookies `HttpOnly` y `SameSite`, header de proxy TLS, expiración de sesión, límite de intentos de login, conexiones de base persistentes), se agregó configuración de logging y de email, y se sacó Django REST Framework de la instalación porque no se usaba en ninguna parte.

---

## 3. Arquitectura técnica (congelada, y por qué)

El stack está elegido y no conviene moverlo. La razón es regulatoria antes que técnica: un sistema que va a auditoría tiene que ser simple de explicar y de inspeccionar. Django monolítico con plantillas del servidor y HTMX para la interactividad no tiene un front-end de JavaScript que auditar por separado, no tiene una API que versionar, y todo el flujo de una acción se sigue leyendo un solo archivo de vistas.

| Capa | Tecnología | Por qué |
|---|---|---|
| Backend | Django 5.1 | Maduro, batteries-included, admin de auditoría gratis |
| Interactividad | HTMX 2.x | Reactividad sin framework JS, sin build de front, auditable |
| Estilos | Tailwind (build local compilado) | Consistencia visual sin CDN, un solo CSS versionado |
| Base de datos | PostgreSQL (Neon) | Estándar, transaccional, backups gestionados |
| OCR | Veryfi API (con modo mock) | Lectura de tickets sin montar infra de visión propia |
| Tareas async | Celery + Redis | OCR y descarga de media fuera del request |
| PDF / Excel | xhtml2pdf + openpyxl | Puro Python, sin dependencias del sistema operativo |
| Estáticos | WhiteNoise | Sirve el CSS y JS sin un CDN aparte |
| Auth | django-allauth + Django Groups | Roles por grupo, login con rate limit |
| Canal de ingesta | WhatsApp Cloud API (Meta) | Nuevo. El asistente manda la foto por WhatsApp |
| Deploy | Railway | Código y base juntos, HTTPS gestionado |

Las cuatro apps del dominio son `protocols` (protocolos, sites, tipos de visita), `patients` (pacientes y visitas, sin datos identificatorios), `expenses` (gastos, tickets, períodos, presupuesto, auditoría) y `reports` (PDF y Excel). Se sumó `intake` para el canal de WhatsApp. Todo lo demás es andamiaje.

---

## 4. Lectura perfecta del comprobante: cómo se logra

Este es el corazón del pedido, así que va en detalle. "Que lo lea perfectamente" no es un botón, es una cadena de decisiones donde cada eslabón sube la probabilidad de acertar.

**Primero, la captura.** El formulario de carga usa `capture="environment"` para abrir la cámara trasera del teléfono directamente, y acepta imagen o PDF. El validador server-side rechaza lo que no sirve antes de gastar una llamada de OCR. La recomendación operativa para el asistente, que va en la guía de usuario, es sacar la foto con buena luz, el ticket plano y los cuatro bordes dentro del cuadro. El 80% de los errores de OCR se resuelven en la captura, no en el algoritmo.

**Segundo, el motor.** Veryfi está entrenado específicamente para tickets y facturas, incluidos los formatos latinoamericanos, y devuelve los campos ya estructurados. El sistema le manda el archivo, y Veryfi devuelve monto, fecha, proveedor, moneda, IVA y número de comprobante. Si no hay credenciales configuradas, el sistema entra en modo mock y no rompe: deja los campos vacíos para carga manual.

**Tercero, la normalización.** Acá estaba una de las trampas finas. Un ticket argentino escribe "40.200,50" (punto de miles, coma decimal) y uno americano "40,200.50" al revés. El sistema detecta cuál es cuál contando los dígitos después del último separador, y convierte a un número correcto. Sin esto, un taxi de cuarenta mil pesos se cargaba como cuarenta.

**Cuarto, la confianza.** Cada campo extraído trae un nivel de confianza. En la pantalla de revisión, el asistente ve un badge verde, amarillo o rojo por campo. Verde arriba de 70%, amarillo entre 40 y 70, rojo abajo. Los campos de alta confianza se pre-completan solos; los de baja confianza obligan a mirar. La confianza global ahora se guarda en la base, así que con el tiempo se puede medir qué proveedores o qué sites tienen peor lectura y actuar sobre eso.

**Quinto, la corrección humana con red.** El OCR nunca aprueba solo. El asistente confirma o corrige, el coordinador aprueba. El dato malo tiene dos filtros humanos antes de llegar al PDF. Para un sistema que va a auditoría, esto no es una limitación, es un requisito: siempre hay una persona responsable de cada número.

**Camino de mejora para lectura aún mejor** (documentado como opción, no todavía construido): correr un segundo modelo en paralelo sobre los tickets de baja confianza y comparar resultados, o mandar a Veryfi una imagen pre-procesada (enderezada y con contraste ajustado con Pillow, que ya está instalado) antes del OCR. Ambos suben la tasa de acierto en tickets térmicos borrosos, que son los peores.

---

## 5. El canal de WhatsApp (construido en esta sesión)

Se pidió poder mandar el comprobante por WhatsApp y que lo lea. Está construido y probado. Así funciona.

El asistente le saca la foto al ticket y se la manda al número de WhatsApp Business del site. Meta reenvía ese mensaje a un webhook del sistema (`/intake/whatsapp/webhook/`). El sistema valida que la petición venga realmente de Meta con la firma criptográfica `X-Hub-Signature-256`, verifica que el número que manda esté en la lista de contactos autorizados del site, baja la imagen, y la deja en la bandeja de recepción exactamente igual que si la hubieran subido desde la web. Desde ahí sigue el flujo normal: el asistente la imputa a un paciente y una visita, el OCR corre, el coordinador aprueba.

Tres decisiones de diseño que importan para la seguridad y el cumplimiento:

La primera, solo el **personal autorizado** puede mandar tickets, nunca el paciente. Los números se cargan uno por uno en el admin y se asocian a un site. Un número desconocido recibe un mensaje de rechazo y el ticket no entra. Esto evita que el canal se llene de ruido o que entren comprobantes sin trazabilidad.

La segunda, **idempotencia**. Meta a veces reenvía el mismo mensaje. Cada mensaje entrante se guarda con su ID único, y si llega dos veces, se procesa una sola. Nunca se duplica un ticket.

La tercera, el webhook responde a Meta en milisegundos y hace el trabajo pesado (bajar la imagen, crearla) en segundo plano con Celery. WhatsApp corta la conexión si el webhook tarda, así que esto no es opcional.

**Para activarlo** hace falta una cuenta de WhatsApp Business API (por Meta o por un proveedor como Twilio o 360dialog), y cargar cuatro variables de entorno: el token de verificación, el secreto de la app, el token de acceso y el ID del número. Sin esas credenciales el webhook existe pero no procesa, así que se puede desplegar el código ahora y activar el canal después, sin tocar nada.

---

## 6. Roadmap a producción

El sistema está en el punto donde el núcleo funciona y falta el trabajo de "llevarlo a la calle". Estos son los sprints, con lo que ya quedó hecho en esta sesión marcado.

**Sprint A — Fundaciones de producción.** Hecho en esta sesión: hardening de configuración, CSS sin CDN, PWA instalable, canal de WhatsApp, control de acceso cerrado, auditoría inmutable, tests. Lo que queda del lado tuyo: rotar las credenciales de Veryfi que hoy están en el `.env` local (nunca fueron a git, pero conviene rotarlas antes del go-live), generar un `SECRET_KEY` nuevo para producción, y contratar el proyecto en Railway con su base y su Redis.

**Sprint B — Notificaciones por email.** El backend de email ya está configurado. Falta escribir los avisos concretos: el asistente recibe un mail cuando su gasto se aprueba, se rechaza o se observa. Es medio día de trabajo una vez que haya una cuenta de SendGrid o similar.

**Sprint C — Integración con Alpha CR.** Este es el que depende de un tercero (Ichtys). Cuando tengan la documentación de la API de Alpha CR, se sincronizan protocolos, pacientes y visitas automáticamente en vez de cargarlos a mano. El modelo ya tiene los campos `external_id` preparados para esto en todas las tablas. Si la API tarda, el plan B es importar un CSV o Excel estable, y esa estructura se puede definir sin bloquear nada.

**Sprint D — UAT con usuarios reales.** Dos o más asistentes del site hacen el flujo completo sin ayuda técnica: cargar cinco a diez tickets reales, imputarlos, que el coordinador los apruebe, generar el PDF. El criterio de rechazo es duro: cualquier error 500 en un flujo principal frena el go-live. Los bugs que aparezcan se corrigen en el mismo sprint.

**Sprint E — Documentación y capacitación.** Tres guías cortas (asistente, coordinador, admin), la matriz de roles y permisos, el procedimiento de backup y restore, y una capacitación grabada de una hora. Este es el material que también sirve para la auditoría.

**Sprint F — Go-live y hypercare.** Despliegue final con todo verificado, y una primera semana de acompañamiento cercano: revisar logs a diario, responder consultas en menos de cuatro horas, corregir bloqueantes el mismo día. Se declara estable después de cinco días corridos sin incidentes.

Estimación realista de punta a punta, contando que Alpha CR es la incógnita: entre seis y ocho semanas hasta un go-live sólido. Si Alpha CR se demora, se puede ir a producción sin esa integración y sumarla después, porque el sistema funciona con carga manual perfectamente.

---

## 7. Ideas nuevas de alto valor

Estas son funciones que no estaban pedidas pero que suben el valor del producto y, varias de ellas, lo hacen más difícil de copiar. Ordenadas por relación valor/esfuerzo.

**Detección de fraude y anomalías.** El sistema ya detecta duplicados y montos fuera de tope. El siguiente paso es un score de riesgo por ticket que combine señales: mismo comercio repetido sospechosamente, montos redondos poco naturales, fechas fuera de la ventana de visita, o el mismo comprobante fotografiado dos veces desde ángulos distintos (comparando un hash perceptual de la imagen). Para un laboratorio que paga los viáticos, esto es oro, y es exactamente el tipo de lógica de dominio que un competidor no copia mirando la pantalla.

**Panel de sponsor.** Una vista de solo lectura que el laboratorio puede mirar para ver el estado de los reintegros de su protocolo en tiempo real, sin llamar por teléfono. Convierte al sistema de una herramienta interna en algo que el sponsor valora y por lo que paga.

**Conciliación bancaria.** Cerrar el círculo: cruzar los gastos aprobados contra la transferencia efectiva que hizo el laboratorio, y marcar qué se pagó y qué falta. Hoy eso se hace de memoria.

**Reintegro al paciente por el mismo canal.** Si el paciente cobra por transferencia, generar la orden de pago desde el gasto aprobado y notificarle por WhatsApp que su reintegro está en camino. Cierra la experiencia.

**Lectura mejorada con pre-procesamiento de imagen.** Enderezar y realzar el contraste del ticket con Pillow antes de mandarlo al OCR. Sube la tasa de acierto en tickets térmicos, que son los que peor se leen.

**Modo offline real con cola de subida.** La PWA ya cachea la app y muestra una pantalla de "sin conexión". El siguiente paso es guardar el ticket en el teléfono cuando no hay señal y subirlo solo cuando vuelve. Para un asistente que se mueve entre consultorios, esto es la diferencia entre usar la app o no.

---

## 8. Cómo hacerlo difícil de copiar

Esto es lo que pediste marcar, y conviene ser franco sobre qué protege de verdad y qué no.

Lo primero que hay que entender: **la interfaz no se protege**. Cualquiera que vea las pantallas puede rehacerlas en un mes. La UI bonita no es el foso. El foso está en otro lado, y son cinco capas.

**Capa uno, el conocimiento de dominio embebido.** Lo que hace valioso a Córdoba no es que suba fotos, es que sabe qué es una ventana de visita, cómo se imputa un gasto a un protocolo, qué exige la Part 11, cómo se separa por moneda, qué hace sospechoso a un ticket. Esa lógica está en el código de servicios y validaciones, no en la pantalla. Un competidor que copie la interfaz se queda sin el motor. Mientras más reglas de negocio reales acumule el sistema (detección de fraude, conciliación, casos de borde de ANMAT), más caro es alcanzarlo. Esta es la protección más fuerte y la más barata: seguir metiendo dominio.

**Capa dos, el secreto comercial bien guardado.** El código es privado. Que siga privado: repositorio cerrado, acceso solo para quien trabaja en él, y sin la carpeta `Fable5/` (que es un clon anidado de todo el proyecto y ya quedó en `.gitignore` para que no se filtre por accidente). Los secretos (claves de Veryfi, base, WhatsApp) van en variables de entorno, nunca en el código. Rotá las claves de Veryfi que estuvieron en el `.env` de desarrollo antes del go-live.

**Capa tres, la marca y el contrato.** El nombre, el logo y "Proyecto Córdoba" como identidad se registran como marca. Con cada cliente (empezando por el propio laboratorio) va un contrato de licencia que prohíbe explícitamente la ingeniería inversa, la redistribución y el uso fuera del alcance pactado. Esto no impide que alguien copie la idea, pero te da con qué ir a la Justicia si un cliente o un empleado se lleva el sistema. Para un producto B2B en un mercado chico y regulado como el de los CRO en Latinoamérica, el contrato pesa más que la tecnología.

**Capa cuatro, el dato y la integración como cerrojo.** El día que Córdoba esté integrado con Alpha CR y tenga el histórico de reintegros de un laboratorio adentro, cambiarse a un competidor cuesta muchísimo. El costo de cambio es un foso que se construye con el tiempo y con las integraciones, no con líneas de código. Cada integración con un sistema del cliente (Alpha CR, el banco, el ERP del sponsor) es un ladrillo más en ese muro.

**Capa cinco, el cumplimiento como barrera de entrada.** Un competidor no solo tiene que copiar el software, tiene que probar que cumple Part 11, Annex 11 y las exigencias de ANMAT, y ganarse la confianza de un laboratorio para manejar datos de un ensayo. El audit trail inmutable, la privacidad del paciente por diseño y la trazabilidad completa son, además de lo correcto, una barrera: llevan tiempo de construir y de validar, y un recién llegado empieza de cero.

En resumen, y esto es lo importante: no gastes energía en ofuscar la pantalla. Gastala en acumular dominio, cerrar el código, firmar buenos contratos, integrarte hondo con el cliente y ser impecable con el cumplimiento. Ese conjunto es lo que hace que copiarte no valga la pena.

---

## 9. Checklist de entrega al cliente

Lo que tiene que estar tildado antes de decir "entregado".

Técnico: `DEBUG=False` en producción, HTTPS activo y forzado, `SECRET_KEY` nuevo y largo, `ALLOWED_HOSTS` con el dominio real, base con backup automático diario, Redis corriendo para Celery, credenciales de Veryfi de producción (rotadas), estáticos compilados y servidos, y `check --deploy` sin warnings fuera del esperado.

Funcional: los cuatro roles creados (admin, coordinador, asistente, auditor) cada uno con su site, al menos un protocolo con sus tipos de visita y sus topes cargados, el flujo completo probado de punta a punta con datos reales, y el PDF y el Excel generándose bien con la foto incrustada.

Operativo: las tres guías de usuario escritas, la capacitación dada y grabada, el procedimiento de backup y restore documentado y probado (un backup que no se probó restaurar no es un backup), y un canal de soporte con tiempos de respuesta acordados.

Legal: contrato de licencia firmado, marca en trámite de registro, y política de privacidad y tratamiento de datos del paciente acorde a la normativa.

---

## 10. Operación y mantenimiento

Para correr en desarrollo: desde `cordoba/`, `python manage.py runserver`. Para compilar el CSS después de tocar plantillas o el tema: desde `cordoba/theme/`, `npm run build` (o `npm run watch` mientras trabajás). Para correr los tests: `python manage.py test --settings=config.settings.test`, que usa SQLite en memoria y no necesita Postgres.

El sistema tiene 89 tests automáticos que cubren el cierre de períodos, la auditoría, el control de acceso por site, el parser de OCR, la validación de archivos, el canal de WhatsApp y las vistas del dashboard. Corrélos antes de cada despliegue. Un test que se rompe es el sistema avisándote de algo antes de que lo vea el cliente.

El audit trail es la caja negra. Ante cualquier duda de "quién hizo qué y cuándo", está en `/admin/expenses/auditlog/`, y no se puede alterar ni desde el admin ni desde el código.

---

## 11. Aprendizajes de esta sesión

Se pidió aprender de lo hecho, así que acá va lo que dejó cada pasada, más allá de los bugs puntuales.

El patrón más repetido de error no fue lógica equivocada, fue **cumplimiento a medias**: cosas que estaban "casi" bien. El audit trail inmutable solo en el admin. La confianza del OCR calculada pero no guardada. El control de acceso presente en expenses pero ausente en patients. La lección operativa es que en un sistema regulado, "casi cumple" es "no cumple", y esos huecos no explotan en la demo, explotan en la inspección. Conviene una pasada específica de "¿esto cumple de verdad o solo parece?" antes de cada entrega.

El segundo aprendizaje es sobre **monedas**. En un país bimonetario, cualquier sistema que maneje plata tiene que tratar la moneda como parte inseparable del monto desde el día uno. Sumar sin mirar la moneda es el bug más fácil de cometer y el más caro de detectar, porque el número se ve válido. Quedó resuelto en todo el sistema, pero es la clase de cosa que hay que vigilar en cada función nueva que toque importes.

El tercero es que la **verificación de punta a punta encuentra lo que los tests unitarios no**. El chequeo adversarial del final, levantando el servidor de verdad y golpeando las rutas, y escribiendo tests para las vistas que había reescrito, encontró una sutileza en el scoping de auditores que ningún test previo cubría. Vale la pena, siempre, esa última pasada mirándolo con ojos de quien lo quiere romper.

---

*Fin del manual. El código está en verde y listo para el Sprint A. El próximo paso concreto es tuyo: decidir Railway y arrancar producción, y contactar a Ichtys por la API de Alpha CR para no bloquear el Sprint C.*
