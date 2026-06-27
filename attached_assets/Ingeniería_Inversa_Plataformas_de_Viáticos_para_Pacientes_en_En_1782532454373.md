# Ingeniería Inversa: Plataformas de Viáticos para Pacientes en Ensayos Clínicos

## Executive Summary

El mercado global de gestión de pagos y viáticos para pacientes de ensayos clínicos es un segmento especializado pero consolidado, dominado por cuatro o cinco actores principales: Greenphire (ClinCard), nmible, Scout Clinical, Medidata Patient Payments y PatientGO (Illingworth). Todos resuelven el mismo problema central: automatizar el reembolso de gastos del paciente, vincularlo a visitas del protocolo y reducir la carga administrativa del site. Ninguno ofrece, sin embargo, una solución económica, autónoma y accesible para sites independientes pequeños en Latinoamérica, con integración a HCE propia, captura OCR de tickets locales y generación de documentación PDF para rendición. Esa brecha es exactamente el espacio de oportunidad para el bot de viáticos de CINME / Innova Trials.

***

## 1. Panorama del Mercado

### 1.1 Actores principales

Existe un ecosistema bien establecido de plataformas de patient payments para investigación clínica, principalmente de origen anglosajón (EE.UU., Reino Unido). Los actores más relevantes son:[^1][^2]

| Plataforma | Origen | Modelo | Foco principal |
|---|---|---|---|
| **Greenphire / ClinCard** | EE.UU. | SaaS + tarjeta prepaga | Sponsors, CROs grandes, pagos globales |
| **nmible** | Reino Unido | App + API + motor de pagos | Sites pequeños a grandes CROs |
| **Scout Clinical** | EE.UU. | Portal + concierge | Sites, sponsors, pacientes |
| **Medidata Patient Payments** | EE.UU. | SaaS integrado (Dassault) | Sponsors grandes, integrado a EDC Rave |
| **PatientGO (Illingworth)** | Reino Unido | App móvil + concierge | Agencias de investigación clínica |
| **PayClinical / ClinPay** | Europa | Web + API | Sites pequeños y CROs europeos |

***

## 2. Ingeniería Inversa por Producto

### 2.1 Greenphire / ClinCard

ClinCard es el sistema de pagos a pacientes más adoptado globalmente, con más de 15 millones de pagos ejecutados en todo el mundo. Funciona como una plataforma web con tarjeta prepaga recargable que reemplaza cheques y efectivo.[^3][^4]

**Cómo funciona el flujo:**

- El coordinador del site accede al portal web y emite el pago con un clic.[^5]
- El paciente recibe los fondos instantáneamente en su ClinCard (puede retirar en banco sin cuenta bancaria).[^6]
- El sistema configura cronogramas de pago por tipo de visita y protocolo.[^6]
- Integra con fuentes de datos clínicos: EDC, CTMS, IVRS.[^3]
- Genera reportes automáticos: Year-End 1099, Pagos por Estudio, Pagos por Sujeto.[^5]
- Incluye mensajería automatizada al paciente (SMS/email) en su idioma nativo.[^5]
- Módulo de viajes (Travel Module): cubre traslados sin costo out-of-pocket para el paciente, pre-configurado según protocolo.[^6]
- Captura de recibos (receipt capture) disponible para rembolsos.[^7]

**Fortalezas:** Máxima escala global, compliance IRS y HIPAA, integración con cualquier EDC/CTMS. Reduce 90% del trabajo administrativo en pagos.[^3][^5][^6]

**Debilidades para sites pequeños LATAM:** Orientado a sponsors y grandes CROs. No transparenta pricing público para sites individuales. Requiere contrato con sponsor para habilitarse. No adaptado a flujos contables locales (comprobantes fiscales argentinos, rendiciones PDF internas).

***

### 2.2 nmible

nmible es el sistema más alineado con sites pequeños. Lanzado en 2022 en Reino Unido, su propuesta es ser accesible para el site más pequeño y escalable al más grande.[^8]

**Cómo funciona el flujo:**

- El participante abre la app, ve sus visitas próximas con fecha, estudio y médico.[^9]
- Desde la app, saca foto del recibo o ingresa kilometraje y lo vincula a la visita.[^9]
- El gasto se enruta automáticamente al aprobador correspondiente.[^9]
- Una vez aprobado, el pago puede llegar el mismo día vía transferencia bancaria, tarjeta virtual o cheque imprimible.[^9]
- El site no gestiona ni emite pagos: nmible actúa como motor financiero.[^10]
- Disponible también por email (foto del recibo enviada por correo, procesada igual).[^11]
- Notificaciones push al paciente cuando el reclamo es aprobado o rechazado, y cuando se envía el pago.[^12]
- El cuidador puede reclamar en nombre del paciente.[^12]

**Motor de tres capas:**
1. App de participante (gastos y visitas).
2. Portal del site (revisión y aprobación).
3. Motor de pagos (routing, compliance, tokenización).[^13]

**Fortalezas:** Mobile-first, captura del recibo en el momento, pago same-day, sin carga para el site. Escalable a CROs grandes vía API white-label.[^13][^8]

**Debilidades para sites LATAM:** Foco en transferencias bancarias europeas. No genera rendición PDF con formato de site. No maneja comprobantes fiscales locales. Pricing orientado a contratos por estudio con sponsor. Sin módulo propio de backoffice para coordinadores.

***

### 2.3 Scout Clinical / Scout Portal

Scout Clinical ofrece una plataforma de portal centrada en la experiencia del site y del paciente.[^14][^15]

**Cómo funciona el flujo:**

- Site agrega al participante con nombre, ID de estudio y contacto.[^16]
- Participante puede subir recibos, solicitar viajes y ver visitas directamente desde el portal, sin pasar por el coordinador.[^17]
- Site staff solo revisa y aprueba; no retipea ni gestiona pagos.[^18]
- Scout maneja los pagos directamente al paciente (ScoutPass, PayPal, transferencia bancaria, cheque) en la moneda local.[^18][^17]
- Dashboard unificado para sponsors y CROs: estado de solicitudes, gastos vs. presupuesto, velocidad de reembolsos.[^19]
- Soporte de 200+ idiomas y conversión de moneda automática.[^19][^18]
- Compliance HIPAA, GDPR y MR-001 con audit trail en cada acción.[^17][^19]
- Portal funciona en cualquier dispositivo: desktop, tablet, móvil.[^16]

**Fortalezas:** Mejor UX para sites y pacientes simultáneamente. Mínima carga de entrenamiento. Alta autonomía del paciente para gestionar sus propios viáticos.[^18][^17]

**Debilidades para LATAM:** Igual que los anteriores: sin adaptación a rendición local, sin PDF de cierre por protocolo, requiere contrato sponsor, no disponible como herramienta independiente del site.

***

### 2.4 Medidata Patient Payments

Lanzado en septiembre 2024, Medidata Patient Payments es la apuesta de Dassault Systèmes para integrar reembolsos directamente en su ecosistema Rave.[^20][^21]

**Cómo funciona el flujo:**

- Los pagos (stipends) se disparan automáticamente por actividades del estudio: completar un diario, terminar una visita, hacer una evaluación.[^22][^20]
- El participante puede ver y reclamar gastos desde myMedidata o iMedidata.[^21]
- Cubre: viajes, comidas, alojamiento, pérdida de ingresos, guardería, kilometraje.[^20][^22]
- Integración nativa con Rave EDC y eCOA.[^23]
- Los participantes eligen el método de pago preferido.[^24]

**Fortalezas:** Integración máxima para usuarios de Medidata. El trigger de pago es automático y auditado desde la actividad clínica.[^20]

**Debilidades:** Solo útil para organizaciones ya en el ecosistema Medidata. Sin valor para sites independientes. Muy reciente, limitaciones aún en cobertura global.

***

### 2.5 PatientGO (Illingworth)

PatientGO es la app de concierge de Illingworth Research Group, orientada a facilitar viajes, alojamiento y reembolsos de gastos para pacientes.[^25]

**Cómo funciona el flujo:**

- Paciente o cuidador solicita viaje/alojamiento desde la app, web o dispositivo móvil.[^25]
- También puede reclamar gastos out-of-pocket directamente desde la app.[^26]
- Equipo de Illingworth gestiona el proceso centralmente, bajo política de viajes predefinida por protocolo.[^25]
- Multi-idioma disponible en iOS y Android.[^25]
- Comunicación del site/paciente vía email, teléfono o SMS.[^26]

**Fortalezas:** Servicio de concierge humano detrás de la app. Ideal para pacientes complejos (oncología, neurologías, pacientes con movilidad reducida).[^27]

**Debilidades:** No es una plataforma autónoma del site. Depende del equipo operativo de Illingworth. No disponible para sites independientes como herramienta propia.

***

## 3. Comparativa de Características

| Característica | Greenphire | nmible | Scout | Medidata | PatientGO |
|---|---|---|---|---|---|
| Captura OCR de ticket | ✅ (receipt capture) | ✅ (foto en app) | ✅ (upload desde portal) | Parcial | ❌ |
| Vinculación a visita clínica | ✅ | ✅ | ✅ | ✅ (automático) | Parcial |
| App móvil paciente | ✅ | ✅ | ✅ | ✅ | ✅ |
| Portal del site (coordinador) | ✅ | ✅ | ✅ | ✅ | ❌ |
| Flujo de aprobación | ✅ | ✅ | ✅ | Automático | Manual |
| PDF de rendición por paciente | ❌ (reportes por sujeto) | ❌ | ❌ | ❌ | ❌ |
| PDF consolidado por site | ❌ | ❌ | ❌ | ❌ | ❌ |
| Integración EDC/CTMS | ✅ (amplia) | Parcial | Parcial | ✅ (Rave nativa) | ❌ |
| Multi-protocolo / multi-site | ✅ | ✅ | ✅ | ✅ | ✅ |
| Uso sin sponsor contratado | ❌ | Parcial | ❌ | ❌ | ❌ |
| Adaptado a LATAM/Argentina | ❌ | ❌ | ❌ | ❌ | ❌ |
| Precio accesible sites pequeños | ❌ | Parcial | ❌ | ❌ | ❌ |
| Backoffice clínico propio | ❌ | ❌ | Parcial | ❌ | ❌ |
| Rendición fiscal local (AFIP/RG) | ❌ | ❌ | ❌ | ❌ | ❌ |

***

## 4. Qué hace cada uno muy bien (para copiar)

### 4.1 De nmible: captura en el momento y pago rápido

nmible resuelve perfectamente la fricción de "tener que esperar para cargar el gasto": el participante saca la foto del recibo en el instante, lo vincula a la visita abierta y lo envía. El pago puede llegar ese mismo día. Ese flujo de **captura inmediata + vinculación contextual + feedback de estado en tiempo real** es el mejor patrón de UX del mercado para el paciente o asistente del site.[^12][^9]

### 4.2 De Scout: autoservicio del paciente y visibilidad del site

El Scout Portal libera al coordinador de ser intermediario en la carga. El participante gestiona sus propias solicitudes; el site solo aprueba. Además, el dashboard unificado da visibilidad en tiempo real de qué gastos están pendientes, aprobados o liquidados a nivel de todo el estudio. Ese modelo de **autoservicio del participante + revisión centralizada del site** reduce horas de administración por semana.[^19][^17][^18]

### 4.3 De Greenphire: configuración por protocolo y reportes automáticos

ClinCard permite configurar cronogramas de pago y topes por tipo de visita y protocolo desde el inicio. Los reportes (pagos por estudio, por sujeto, reconciliación financiera) se generan automáticamente. Ese modelo de **configuración previa del protocolo + reporte automático al cierre** es exactamente el flujo que necesita el bot de CINME para generar el PDF de rendición.[^7][^5][^6]

### 4.4 De Medidata: triggers automáticos por actividad clínica

La lógica de Medidata de disparar pagos automáticamente cuando se registra una visita en el EDC es poderosa para escenarios de alta automatización. A futuro, cuando el bot se integre con Alpha CR, ese mismo patrón puede aplicarse: visita registrada en la HCE → sugerencia automática de apertura de período de carga de viáticos.[^21][^20]

***

## 5. Gaps del Mercado: La Oportunidad Real

El análisis revela que **ninguna plataforma existente** cubre el caso de uso específico de CINME / Innova Trials:

1. **Sin rendición PDF estructurada**: Todos generan reportes de pagos pero ninguno genera un PDF listo para presentar al sponsor o para archivo fuente del site, con desglose por visita, paciente y protocolo. Ese es el output clave del bot.[^7][^3][^19]

2. **Sin herramienta para sites independientes**: Todas las plataformas requieren que el sponsor o CRO habilite y financie el sistema. No existe una herramienta que el site pueda contratar y usar de forma autónoma, con su propio backoffice.[^28][^1]

3. **Sin adaptación a mercados emergentes / LATAM**: Ninguna contempla comprobantes fiscales locales (facturas A/B/C argentinas, tickets con CUIT), tipos de cambio en pesos, categorías de gastos locales (remises, taxis de aplicaciones, farmacias) o normativa ANMAT.[^19][^18]

4. **Sin integración con HCE propias del site**: La integración de Medidata es con su propio EDC Rave; Greenphire integra con EDCs populares globales. Ninguna tiene un modelo de integración plug-and-play con HCEs de sites independientes como Alpha CR.[^21][^3]

5. **OCR superficial o inexistente en rendición**: Ninguna hace OCR real orientado a capturar campos fiscales del comprobante local ni lo usa para validar coherencia de fecha con la visita. La captura de recibos es básicamente un adjunto de imagen, no extracción inteligente de datos.[^29][^30]

6. **Sin workflow de aprobación clínico completo para el site**: No existe un backoffice diseñado para que el coordinador del site gestione estados, observe gastos, cierre períodos y entregue documentación lista para auditoría (GCP, ANMAT).[^31]

***

## 6. Blueprint de Funcionalidades a Construir

A partir de la ingeniería inversa, el bot de CINME / Innova Trials debería incorporar lo mejor de cada plataforma, añadiendo lo que ninguna tiene:

### De nmible (copiar)
- Captura de ticket inmediata desde móvil con foto
- Vinculación a visita abierta del paciente
- Estado del gasto visible en tiempo real (borrador → pendiente → aprobado → liquidado)
- Notificación al asistente cuando cambia el estado

### De Scout Portal (copiar)
- Portal del coordinador para revisar y aprobar (no recargar datos)
- Dashboard de gastos pendientes por protocolo/paciente/visita
- Flujo de autoservicio: el asistente carga, el coordinador aprueba
- Acceso desde cualquier dispositivo (móvil y desktop)

### De Greenphire (copiar)
- Configuración inicial de topes y categorías por protocolo
- Generación automática de reportes al cierre
- Cronograma de visitas como marco de validación temporal del ticket

### De Medidata (copiar para V2)
- Trigger automático de apertura de período de viáticos al registrar visita en Alpha CR
- Vinculación automática sugerida por fecha de ticket vs. ventana de visita

### Exclusivo del bot (lo que ninguno tiene)
- **OCR con extracción de campos fiscales argentinos** (CUIT proveedor, nro. de comprobante, tipo de factura, IVA)
- **PDF de rendición por paciente** con viáticos desglosados por visita, listo para presentar al sponsor
- **PDF consolidado del site** con todos los gastos del período por protocolo
- **Backoffice clínico completo** con estados, observaciones, cierre de período y auditoría
- **Integración con Alpha CR** como fuente de agenda de visitas (módulo V2)
- **Adaptación a normativa local** (ANMAT, GCP, Ley de Protección de Datos Argentina)
- **Multi-protocolo y multi-site** desde una sola instalación (arquitectura para producto vendible)

***

## 7. Modelo de Negocio Sugerido

Los competidores globales monetizan principalmente via sponsors o CROs (B2B2C). La oportunidad diferencial es un modelo **B2B directo con el site**, accesible sin depender del sponsor:[^1][^13][^3]

- **SaaS por site**: tarifa mensual por site activo + protocolos activos.
- **Por transacción de rendición**: cobro por PDF generado o por cierre de período.
- **Licencia por estudio**: tarifa fija al sponsor por estudio gestionado desde el bot (modelo para escalamiento cuando se productice).
- **Integración Alpha CR como módulo premium**: sites que ya usan Alpha CR pagan un add-on por la integración automática de agenda y visitas.

Este modelo permite que el primer cliente (el site piloto) pague una tarifa asequible y que la plataforma escale hacia sponsors y CROs en fases posteriores, como hicieron nmible y Scout en sus inicios.[^8]

***

## 8. Conclusiones

El mercado global de patient expense management en ensayos clínicos está dominado por soluciones de alto costo, orientadas a sponsors globales y no adaptadas a la realidad operativa ni regulatoria de sites independientes en Latinoamérica. La brecha principal no está en la captura de tickets (todos lo hacen) sino en la **rendición documental estructurada, el backoffice clínico del site y la adaptación local**. El bot de CINME / Innova Trials tiene una oportunidad real de ocupar ese espacio, tomando los mejores patrones de UX del mercado (captura inmediata de nmible, portal de aprobación de Scout, configuración por protocolo de Greenphire) y añadiendo la capa que ninguno tiene: PDF de rendición lista para auditoría y adaptación al contexto regulatorio y fiscal local.

---

## References

1. [Best Clinical Trial Reimbursement Software • March 2026 | F6S](https://www.f6s.com/software/category/clinical-trial-reimbursement) - Find the best Clinical Trial Reimbursement software of 2026. Get discounts on top-rated systems and ...

2. [Clinical Trial Patient Payments solutions](https://directory.betterclinical.com/software/category/clinical-trial-patient-payments/) - Clinical Trial Patient Payment software automates how participants are compensated for their time an...

3. [IM Landing Page: CC | Greenphire](https://greenphire.com/cc-greenphire-resources/)

4. [Greenphire revolutionises subject payment in clinical trials with launch of ClinCard automated payment system](https://www.europeanpharmaceuticalreview.com/news/6386/greenphire-revolutionizes-subject-payment-in-clinical-trials-with-launch-of-clincard-automated-payment-system/) - Greenphire, announced the growing success of its ClinCard System since its launch...

5. [[PDF] Finally, a painless payment option for patients.](https://familymedicine.med.wayne.edu/pdfs-new/clincard_flyer.pdf)

6. [A Better Way to Pay Patients](https://www.finance.upenn.edu/wp-content/uploads/A-Better-Way-to-Pay-Patients.pdf)

7. [Greenphire | Greenphire Means Go | Brochure](https://greenphire.com/wp-content/uploads/2024/10/Greenphire-Means-Go-Brochure.pdf)

8. [nmible partners with Velocity Clinical Research to streamline clinical ...](https://www.einpresswire.com/article/683516340/nmible-partners-with-velocity-clinical-research-to-streamline-clinical-trials-patient-stipends) - • nmible’s solution expected to save more than 650 working days per year, administering payments U.K...

9. [nmible - App Store - Apple](https://apps.apple.com/us/app/nmible/id1547252807) - As a trial participant you can easily view your upcoming hospital visits, next visit date, study and...

10. [Nmible | Financial Infrastructure for Clinical Trial Reimbursement](https://www.nmible.com) - Run app, API, and in-clinic reimbursement from one secure operating layer with policy-driven approva...

11. [Nmible](https://get.nmible.com) - Use nmible (nim-bul) to quickly and securely request refunds for your expenses as soon as they are i...

12. [Utiliza nmible (nim-bul) para solicitar de forma rápida y segura el ...](https://get.nmible.com/es/) - Utiliza nmible (nim-bul) para solicitar de forma rápida y segura el reembolso de tus gastos en cuant...

13. [nmible Payment Engine for Clinical Trials](https://www.linkedin.com/posts/nmible_nmible-clinicaltrials-cro-activity-7439727672081133568-WcbT) - 🎗️ One payment engine. Three ways to make it work for you. Whether you want to run payments, offload...

14. [Support for clinical trial patients through Scout Clinical](https://www.scoutclinical.com/services/scout-clinical) - Explore clinical trial patient services that help sites and sponsors reduce burden and keep studies ...

15. [Scout Portal for managing clinical trial requests](https://www.scoutclinical.com/services/scout-clinical/scout-portal) - Submit and track participant travel and payment needs in one secure portal. Easy access for sites an...

16. [Getting Started with the Scout Portal: A Simple Guide for Sites](https://www.scoutclinical.com/scout-portal-getting-started-for-sites) - Learn how to access the Scout Portal, create participant profiles, and manage site requests easily. ...

17. [Patient-Accessible Portal for Clinical Trials](https://explore.scoutclinical.com/blog/patient-accessible-portal) - Let patients manage travel and payments directly. See how the Scout Portal improves retention and ea...

18. [The Scout Portal Helps Sites Hit SCRS' 25 in 25 Goal](https://explore.scoutclinical.com/blog/scout-portal-scrs-25-in-25) - Train less, launch faster. See how the Scout Portal helps sites meet SCRS’s 25 in 25 goal with minim...

19. [What the Scout Portal Does for Sites, Sponsors, and Patients](https://explore.scoutclinical.com/blog/what-the-scout-portal-does) - Discover how the Scout Portal simplifies clinical trial logistics for sites, sponsors, and patients—...

20. [Medidata Launches Patient Payments: Streamlining Clinical Trial ...](https://hitconsultant.net/2024/09/26/medidata-launches-patient-payments-streamlining-clinical-trial-reimbursements/) - Medidata, a Dassault Systèmes brand and leading provider of clinical trial solutions to the life sci...

21. [Medidata Streamlines Clinical Trial Compensation with New Patient Payments Platform](https://trial.medpath.com/news/bf32818b0c1b7bc6/medidata-streamlines-clinical-trial-compensation-with-new-patient-payments-platform) - - Medidata has launched a comprehensive Patient Payments solution to automate and simplify reimburse...

22. [Medidata Extends Its Commitment to the Patient Experience ...](https://via.ritzau.dk/pressemeddelelse/14055362/medidata-extends-its-commitment-to-the-patient-experience-with-the-launch-of-patient-payments?publisherId=90456&lang=en) - New solution accelerates payments to patients participating in a clinical trial, improving experienc...

23. [환자 지급금 솔루션 - 자동화된 보안 처리](https://www.medidata.com/kr/patient-experience/patient-payments/) - 유연하고 규정을 준수하는 솔루션으로 환자 지급금 및 환급을 간소화하여 시험기관의 부담을 줄이고 임상시험이 원활하게 진행되도록 지원합니다.

24. [Patient Payments Solution - Automated & Secure Processing](https://www.medidata.com/en/patient-experience/patient-payments/) - Medidata Patient Payments delivers transparent reimbursement for trial participants without adding a...

25. [Patient Concierge App - PatientGO - Illingworth Research Group](https://illingworthresearch.com/patientgo-patient-concierge/) - PatientGO a patient concierge app designed to deliver support with patient travel, expense reimburse...

26. [PatientGO Terms - Illingworth Research Group](https://illingworthresearch.com/patientgo-terms/) - english This EULA or Agreement (together with our Privacy Policy) and any additional terms of use in...

27. [PatientGO - Apps on Google Play](https://play.google.com/store/apps/details?id=uk.co.illingworth.patientgo&hl=en_US) - Patient concierge services

28. [[PDF] Greenphire Patient Convenience ROI White Paper - Suvoda](https://www.suvoda.com/hubfs/Greenphire%20White%20Papers%20-%20Reports/Greenphire_Patient_Convenience_ROI_White_Paper_FINAL.pdf)

29. [Expense Report Processing: Why OCR Alone Fails and What ...](https://firmadapt.com/blog/expense-report-processing-ocr-fails-what-works-better) - OCR captures receipt data but misses 80% of expense processing work. What a complete automation syst...

30. [The Hidden Cost of Manual Document Processing in Clinical Trials](https://artificio.ai/blog/the-hidden-cost-of-manual-document-processing-in-clinical-trials) - Streamline pharma workflows with AI. Move beyond manual OCR to automate CRF processing, adverse even...

31. [Improving Study Success With Optimized Patient Payments](https://myscrs.org/resources/improving-study-success-with-optimized-patient-payments/) - Exploring best practices to close collaboration gaps across clinical research ... expense verificati...

