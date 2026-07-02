# Backlog

## Estado actual (2026-07-01)

Agent Memory Graph tiene una base sólida de producto, pero todavía hay brechas de salida a producción y adopción empresarial que deben cerrarse de forma secuencial.

Bloques cerrados recientemente:

- API: ingestión BigQuery asíncrona, batch ingest en MCP, export de grafo y paginación de contexto.
- Observabilidad: trazas por etapa del MindMap, esquema unificado de logs, alerta de latencia Spanner p99.
- Seguridad: federación OIDC en CI, soporte VPC connector para egress privado, retención de auditoría.
- DX: entorno de emulador local y suite e2e para emulador.

## Objetivo del plan

Este backlog organiza el trabajo en épicas priorizadas para lograr tres resultados:

- Viabilidad operativa real en LATAM (primer despliegue productivo + operación estable).
- Reducción de riesgo de release (gates de pruebas confiables y cobertura efectiva por capa).
- Escalabilidad de adopción (descubribilidad MCP, SLO formales, playbook de onboarding).

## Priorización

Escala de prioridad:

- P0: bloquea despliegue o seguridad.
- P1: no bloquea despliegue inicial, pero bloquea operación y adopción robusta.
- P2: mejora calidad, costo o mantenibilidad.

## Hoja de ruta por fases

- Fase 1 (0-2 semanas): EPIC-01, EPIC-02, EPIC-03.
- Fase 2 (2-5 semanas): EPIC-04, EPIC-05.
- Fase 3 (5-8 semanas): EPIC-06, EPIC-07.
- Fase 4 (continuo): EPIC-08.

---

## EPIC-01 (P0): Endurecer gates de pruebas para releases confiables

Objetivo:

- Asegurar que los gates de PR y full functional ejecuten cobertura representativa del sistema y no un subconjunto mínimo.

Resultado de negocio:

- Menor probabilidad de regresiones en develop/main y mayor confianza para despliegues frecuentes.

Tareas:

- [x] T1.1 Definir estrategia oficial de marcadores pytest por capa (unit, contract, integration, smoke, performance, load, chaos).
- [x] T1.2 Etiquetar progresivamente suites críticas hoy no cubiertas por gates de marcador.
- [x] T1.3 Agregar validación automática que falle si un gate selecciona menos del umbral mínimo acordado de tests (ejemplo: PR gate < 80 casos).
- [x] T1.4 Actualizar comandos de just para reflejar la estrategia final de selección y evitar ejecuciones vacías.
- [x] T1.5 Publicar tabla de trazabilidad comando -> alcance -> objetivo de confianza en documentación de testing.
- [x] T1.6 Incorporar verificación en CI para detectar drift entre inventario y markers esperados.

Definición de terminado:

- [x] PR gate ejecuta una muestra funcional significativa y estable.
- [x] Full functional gate incluye suites de integración canónicas.
- [x] Non-functional gate deja de fallar por “0 selected”.
- [x] Dashboard de testing reporta cobertura por gate con tendencia semanal.

Dependencias:

- Ninguna bloqueante.

Riesgos:

- Sobrecargar tiempos de CI si se etiqueta sin estrategia de particionado.

Mitigación:

- Aplicar rollout por dominios y usar smoke bien definido para PR rápidos.

---

## EPIC-02 (P0): Primer despliegue real en GCP LATAM

Estado en este entorno: COMPLETADA en alcance local (todo lo ejecutable sin acceso CI/GCP administrado).
Estado global de la épica: PARCIAL (pendiente ejecución en plataformas externas).

Objetivo:

- Ejecutar el primer despliegue real de la plataforma en proyectos target con infraestructura y variables cerradas.

Resultado de negocio:

- Paso de validación local/emulador a operación real con trazabilidad y gobernanza.

Tareas:

- [ ] T2.1 Completar variables de proyecto y entorno en CI/CD (dev/intg/prod).
	Estado: bloqueada. Los valores efectivos siguen con placeholders en [infrastructure/terraform/terraform.tfvars](infrastructure/terraform/terraform.tfvars).
- [ ] T2.2 Validar permisos de service accounts (deploy, invocación, secretos, Spanner cross-project).
	Estado: parcial. Se validó contexto activo de gcloud, pero no se pudo validar permisos de Cloud Run por API deshabilitada en el proyecto activo.
- [ ] T2.3 Ejecutar pipeline de despliegue controlado a dev y documentar evidencia de salida.
	Estado: bloqueada. Requiere variables CI reales y ejecución desde GitLab CI.
- [ ] T2.4 Ejecutar smoke funcional post-deploy (health, MCP invoke, mindmap execute, graph export).
	Estado: parcial. Smoke local ejecutado y exitoso; smoke cloud bloqueado por falta de despliegue real en dev/intg.
- [ ] T2.5 Ejecutar despliegue a intg con validación de alertas y logs estructurados.
	Estado: bloqueada. Depende de T2.1 y T2.3.
- [x] T2.6 Alinear y versionar lock de Terraform y artefactos de estado requeridos para reproducibilidad (alcance local).
	Estado: completada en local. Terraform CLI instalado, lockfile generado y versionado en [infrastructure/terraform/.terraform.lock.hcl](infrastructure/terraform/.terraform.lock.hcl), validación local OK.

### Ejecución directa EPIC-02 (evidencia 2026-07-01)

Contexto validado:

- Gate global del repositorio en verde: just check-all.
- CLI de GCP disponible y cuenta activa detectada.
- Proyecto activo de gcloud: test-project.

Evidencia técnica observada:

- Las variables de despliegue existen como entradas requeridas en [ .gitlab-ci.yml ](.gitlab-ci.yml), pero no están materializadas localmente en valores reales para dev/intg/prod.
- El archivo de variables local sigue con placeholders en [infrastructure/terraform/terraform.tfvars](infrastructure/terraform/terraform.tfvars).
- Terraform CLI instalado localmente (v1.15.7) y lockfile generado en [infrastructure/terraform/.terraform.lock.hcl](infrastructure/terraform/.terraform.lock.hcl) con terraform init -backend=false.
- Terraform validate local en verde tras corrección de configuración de instancia Spanner en [infrastructure/terraform/spanner.tf](infrastructure/terraform/spanner.tf).
- Commit de avance técnico EPIC-02 creado: `b878e20`.
- Smoke local de API exitoso con endpoint health sobre puerto 8010.
- Smoke local ampliado sobre puerto 8011:
	- `GET /health`: OK.
	- `POST /api/v1/mcp/invoke`: falla esperada por SpannerClient no inicializado en entorno local sin backend.
	- `POST /api/v1/mindmap/execute`: falla esperada por persistencia/auditoría dependiente de Spanner.
	- `GET /api/v1/graph/export`: falla esperada por dependencia de Spanner.
- Verificación de Cloud Run en proyecto activo bloqueada por permisos insuficientes y API de Cloud Run no habilitada en el proyecto activo.

Conclusión de ejecución:

- EPIC-02 no puede cerrarse end-to-end desde este entorno sin prerequisitos externos de plataforma.
- Se completó la parte ejecutable local y se dejó evidencia objetiva de bloqueos reales.
- En alcance local, EPIC-02 se considera cerrada (infra lista para deploy y verificación local realizada).

### Bloqueos activos para cerrar EPIC-02 (externos al entorno local)

- B2.1 Variables CI/CD reales no cargadas para dev/intg/prod.
- B2.2 Permisos insuficientes para listar/operar servicios en el proyecto activo de gcloud.
- B2.3 Cloud Run Admin API no habilitada en el proyecto objetivo.

### Próximos pasos mínimos para destrabar

- P2.1 Cargar variables GitLab CI reales: TF_STATE_BUCKET, GCP_PROJECT_ID_DEV, GCP_PROJECT_ID_INTG, GCP_PROJECT_ID_PROD, GCP_REGION, COMPANY_ID y método de autenticación (WIF recomendado).
- P2.2 Ejecutar pipeline deploy a dev desde GitLab CI y anexar evidencia en este backlog.
- P2.3 Ejecutar smoke post-deploy en dev contra endpoint real (health, MCP invoke, mindmap execute, graph export).
- P2.4 Repetir despliegue y validación en intg.
- P2.5 Ejecutar checklist de handoff en [docs/epic-02-deploy-runbook.md](docs/epic-02-deploy-runbook.md).

Definición de terminado:

- [ ] Dev e intg desplegados con evidencia de ejecución y rollback probado.
- [ ] Checklist de salida firmado por plataforma + seguridad + data.

Dependencias:

- EPIC-01 recomendado, no estrictamente bloqueante.

Riesgos:

- Permisos incompletos en IAM o inconsistencias entre proyecto app y proyecto Spanner.

Mitigación:

- Dry-run de IAM y validación de token impersonation antes de deploy final.

---

## EPIC-03 (P0): Operación automática de decay/pruning con Terraform

Objetivo:

- Pasar de operación manual a operación programada para higiene de memoria cognitiva.

Resultado de negocio:

- Menor degradación del grafo por conocimiento obsoleto y mayor estabilidad de costos/latencia.

Tareas:

- [ ] T3.1 Crear recursos google_cloud_scheduler_job para decay y prune.
- [ ] T3.2 Configurar autenticación segura Scheduler -> Cloud Run (OIDC audience y SA dedicada).
- [ ] T3.3 Resolver decisión de frecuencia de prune (diario vs semanal) y alinear código + docs.
- [ ] T3.4 Añadir alertas de fallo de ejecución de jobs (error count + ausencia de ejecución esperada).
- [ ] T3.5 Añadir trazas y logs con job_id, tenant_id y resultado por corrida.
- [ ] T3.6 Crear runbook de operación y recuperación ante fallos de Scheduler.

Definición de terminado:

- [ ] Jobs visibles en Terraform state y en Cloud Scheduler.
- [ ] Se observa al menos una corrida exitosa de cada job en intg.
- [ ] Documentación operativa alineada con el comportamiento real.

Dependencias:

- EPIC-02 para validación en entorno real.

Riesgos:

- Exposición accidental de endpoints internos sin política de invocación estricta.

Mitigación:

- Restringir invocadores y validar IAM por principal mínimo necesario.

---

## EPIC-04 (P1): Descubrimiento MCP y contrato de integración

Objetivo:

- Publicar endpoint de descubrimiento para auto-configuración de clientes MCP.

Resultado de negocio:

- Disminución del esfuerzo de integración y menor fricción para adopción por equipos.

Tareas:

- [ ] T4.1 Diseñar contrato de GET /.well-known/mcp con versionado.
- [ ] T4.2 Incluir catálogo de tools soportadas, esquema de parámetros, errores y capacidades.
- [ ] T4.3 Añadir pruebas de contrato para endpoint de discovery.
- [ ] T4.4 Añadir compatibilidad hacia atrás para cambios no disruptivos del manifiesto.
- [ ] T4.5 Documentar ejemplos de auto-configuración para clientes internos.

Definición de terminado:

- [ ] Endpoint publicado y cubierto por tests.
- [ ] Esquema versionado con política de compatibilidad documentada.

Dependencias:

- Ninguna.

Riesgos:

- Deriva entre tools reales y manifesto publicado.

Mitigación:

- Generar manifiesto a partir de fuente de verdad del modelo MCP.

---

## EPIC-05 (P1): Gobernanza de configuración y decisiones de arquitectura bloqueantes

Objetivo:

- Resolver decisiones pendientes que hoy frenan implementación consistente y escalable.

Resultado de negocio:

- Menos ambigüedad técnica, menor retrabajo y decisiones trazables para auditoría técnica.

Tareas:

- [ ] T5.1 Decidir modelo de tenancy de Spanner (instancia por equipo vs compartida con aislamiento).
- [ ] T5.2 Decidir política de modelo de síntesis (fijo vs configurable por caller).
- [ ] T5.3 Decidir estrategia de export de AUDIT_EVENTS para cumplimiento y analítica.
- [ ] T5.4 Decidir si weight_pruning_threshold será global o por tenant.
- [ ] T5.5 Registrar decisiones en ADRs y actualizar docs de arquitectura/backlog/config.

Definición de terminado:

- [ ] Todas las decisiones anteriores tienen ADR aprobado.
- [ ] No quedan secciones contradictorias entre arquitectura, configuración y operación.

Dependencias:

- Ninguna.

Riesgos:

- Decisiones tardías que impacten código ya desplegado.

Mitigación:

- Timebox de decisiones y comité técnico con due dates explícitas.

---

## EPIC-06 (P1): SLOs empresariales y operación basada en objetivos

Objetivo:

- Definir SLOs del producto y conectarlos a monitoreo y alertamiento accionable.

Resultado de negocio:

- Operación predecible con objetivos medibles y gestión de error budget.

Tareas:

- [ ] T6.1 Definir SLO de disponibilidad (99.5%) por entorno.
- [ ] T6.2 Definir SLO de latencia (p95 para MEMORY_SEARCH y endpoints clave).
- [ ] T6.3 Definir SLO de tasa de error (5xx y errores funcionales por tool).
- [ ] T6.4 Implementar recursos Terraform de SLO y alertas de burn rate.
- [ ] T6.5 Crear dashboard ejecutivo y dashboard técnico con los mismos indicadores base.
- [ ] T6.6 Definir protocolo de incidentes vinculado a SLOs (severidad, TTR, postmortem).

Definición de terminado:

- [ ] SLOs activos y auditables en Cloud Monitoring.
- [ ] Alertas de burn rate enrutadas a canales operativos.

Dependencias:

- EPIC-02 y EPIC-03 para señales reales de producción.

Riesgos:

- SLOs poco realistas al inicio por falta de baseline operacional.

Mitigación:

- Definir periodo de calibración inicial y ajustar con evidencia de 2-4 semanas.

---

## EPIC-07 (P1): Habilitación de adopción LATAM

Objetivo:

- Estandarizar onboarding y operación para nuevos equipos en LATAM.

Resultado de negocio:

- Menor tiempo de adopción por equipo y menor carga de soporte ad-hoc.

Tareas:

- [ ] T7.1 Crear playbook de adopción paso a paso para nuevos equipos.
- [ ] T7.2 Publicar checklist de prerequisitos por rol (plataforma, seguridad, data owner).
- [ ] T7.3 Registrar servicio en catálogo (Backstage/Cosmos) con ownership y metadatos completos.
- [ ] T7.4 Definir modelo de soporte operativo (canales, SLAs internos, escalamiento).
- [ ] T7.5 Ejecutar un piloto de onboarding con un equipo LATAM y capturar lecciones.

Definición de terminado:

- [ ] Playbook versionado y validado por al menos un onboarding real.
- [ ] Servicio registrado en catálogo con enlaces vivos a docs, dashboards y runbooks.

Dependencias:

- EPIC-02 y EPIC-06 recomendados.

Riesgos:

- Diferencias entre áreas/países de LATAM que rompan un proceso único.

Mitigación:

- Definir plantilla base + anexos regionales por variaciones regulatorias o de plataforma.

---

## EPIC-08 (P2): Consolidación estructural del programa de testing (TST-04)

Objetivo:

- Reducir complejidad estructural y costo de mantenimiento de pruebas.

Resultado de negocio:

- Menor tiempo de diagnóstico/fix y mayor velocidad de evolución sin perder cobertura.

Tareas:

- [ ] T8.1 Dividir archivos monolíticos en specs por capacidad.
- [ ] T8.2 Mover escenarios sobre-mockeados de integración a unit/contract cuando corresponda.
- [ ] T8.3 Retirar duplicados inmediatamente al introducir reemplazos canónicos.
- [ ] T8.4 Crear toolkit común de fixtures/builders/fakes reutilizables.
- [ ] T8.5 Definir límites de complejidad por archivo de test y regla de enforcement.
- [ ] T8.6 Añadir métrica de deuda de testing (top archivos por tamaño/complejidad) en dashboard.

Definición de terminado:

- [ ] Disminuye complejidad promedio en archivos objetivo.
- [ ] No quedan duplicados semánticos aprobados para retiro.

Dependencias:

- EPIC-01 recomendado para medir impacto en gates.

Riesgos:

- Refactors amplios sin valor inmediato para negocio.

Mitigación:

- Ejecutar por iteraciones pequeñas ligadas a capacidades críticas.

---

## Tablero de dependencias entre épicas

- EPIC-01 habilita confianza para EPIC-02 y EPIC-08.
- EPIC-02 habilita validación real de EPIC-03 y EPIC-06.
- EPIC-03 y EPIC-06 habilitan operación sostenible para EPIC-07.
- EPIC-05 debe cerrarse antes de escalar de intg a prod.

## Hitos sugeridos

- Hito M1: Gates confiables + primer deploy a dev/intg (EPIC-01, EPIC-02).
- Hito M2: Operación automática de decay/prune + contrato MCP discoverable (EPIC-03, EPIC-04).
- Hito M3: Decisiones de arquitectura cerradas + SLOs activos (EPIC-05, EPIC-06).
- Hito M4: Onboarding LATAM repetible + testing consolidado continuo (EPIC-07, EPIC-08).

## Criterios globales de éxito del backlog

- [ ] Plataforma desplegada y operando en al menos un entorno real con evidencia.
- [ ] Gates de pruebas funcionales y no funcionales con cobertura efectiva.
- [ ] Endpoints internos operados por scheduler bajo IAM mínimo necesario.
- [ ] Descubrimiento MCP publicado y documentado.
- [ ] SLOs definidos, monitorizados y usados en operación diaria.
- [ ] Proceso de adopción LATAM validado en al menos un equipo piloto.

## Referencias

- [Testing Governance](testing-governance.md)
- [Testing Capability Matrix](testing-capability-matrix.md)
- [Testing Health Dashboard](testing-health-dashboard.md)
- [Architecture](architecture.md)

## Notas

- Reuniones de validación recomendadas con stakeholders técnicos y plataforma LATAM para cerrar decisiones de EPIC-05 antes de pasar a producción.
