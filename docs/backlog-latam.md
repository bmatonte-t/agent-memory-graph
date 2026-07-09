# Backlog LATAM Airlines

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

- Las variables de despliegue existen como entradas requeridas en [.gitlab-ci.yml](.gitlab-ci.yml), pero no están materializadas localmente en valores reales para dev/intg/prod.
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

Estado en este entorno: COMPLETADA en alcance local (todo lo implementable sin apply en GCP administrado).
Estado global de la épica: PARCIAL (pendiente apply y validación operativa en dev/intg).
Estado de ejecución actual: CERRADA POR AHORA (pendientes externos explícitos mantenidos en backlog).

Objetivo:

- Pasar de operación manual a operación programada para higiene de memoria cognitiva.

Resultado de negocio:

- Menor degradación del grafo por conocimiento obsoleto y mayor estabilidad de costos/latencia.

Tareas:

- [x] T3.1 Crear recursos google_cloud_scheduler_job para decay y prune.
  Estado: completada en local con dos jobs en [infrastructure/terraform/scheduler.tf](infrastructure/terraform/scheduler.tf).
- [x] T3.2 Configurar autenticación segura Scheduler -> Cloud Run (OIDC audience y SA dedicada).
  Estado: completada en local con SA dedicada, invoker IAM mínimo y oidc_token por job en [infrastructure/terraform/scheduler.tf](infrastructure/terraform/scheduler.tf).
- [x] T3.3 Resolver decisión de frecuencia de prune (diario vs semanal) y alinear código + docs.
  Estado: completada. Prune quedó semanal (domingo 03:00 UTC) en [src/memory/cognitive_weighting.py](src/memory/cognitive_weighting.py), [tests/unit/test_cognitive_weighting.py](tests/unit/test_cognitive_weighting.py), [infrastructure/terraform/scheduler.tf](infrastructure/terraform/scheduler.tf) y [infrastructure/terraform/terraform.tfvars.example](infrastructure/terraform/terraform.tfvars.example).
- [x] T3.4 Añadir alertas de fallo de ejecución de jobs (error count + ausencia de ejecución esperada).
  Estado: completada en local. Se implementaron alertas por ejecución fallida y por ausencia de ejecución esperada en [infrastructure/terraform/scheduler.tf](infrastructure/terraform/scheduler.tf).
- [x] T3.5 Añadir trazas y logs con job_id, tenant_id y resultado por corrida.
  Estado: completada en local con metadata de Scheduler y resultado en [src/api/main.py](src/api/main.py).
- [x] T3.6 Crear runbook de operación y recuperación ante fallos de Scheduler.
  Estado: completada con runbook en [docs/epic-03-scheduler-runbook.md](docs/epic-03-scheduler-runbook.md).

### Ejecución directa EPIC-03 (evidencia 2026-07-01)

Evidencia técnica observada:

- Infra Scheduler implementada con SA dedicada, IAM invoker mínimo, OIDC audience y payloads de mantenimiento en [infrastructure/terraform/scheduler.tf](infrastructure/terraform/scheduler.tf).
- Alertas Scheduler completadas para ambos jobs: fallos de ejecución + ausencia de ejecución esperada en [infrastructure/terraform/scheduler.tf](infrastructure/terraform/scheduler.tf).
- Variables de operación Scheduler agregadas con validaciones de rango en [infrastructure/terraform/variables.tf](infrastructure/terraform/variables.tf).
- Valores de ejemplo versionados para configuración por entorno en [infrastructure/terraform/terraform.tfvars.example](infrastructure/terraform/terraform.tfvars.example).
- Alineación de frecuencia prune semanal aplicada en runtime y pruebas:
  - [src/memory/cognitive_weighting.py](src/memory/cognitive_weighting.py)
  - [tests/unit/test_cognitive_weighting.py](tests/unit/test_cognitive_weighting.py)
- Endpoints internos con logging de ejecución scheduler (job_id, schedule_time, tenant_id global, resultado) en [src/api/main.py](src/api/main.py).
- Cobertura de compatibilidad con headers de Cloud Scheduler en [tests/integration/test_scheduler_integration.py](tests/integration/test_scheduler_integration.py).

Validaciones locales ejecutadas:

- `terraform fmt` + `terraform validate` en [infrastructure/terraform](infrastructure/terraform): OK.
- `terraform plan` local aislado (copia temporal sin backend GCS + workspace dev + variables stub): OK, plan generado con `42 to add, 0 to change, 0 to destroy`.
- `uv run ruff check` sobre archivos Python tocados: OK.
- `uv run pytest tests/integration/test_scheduler_integration.py tests/unit/test_cognitive_weighting.py -q`: 24 passed.

Conclusión de ejecución:

- EPIC-03 quedó cerrada en alcance local.
- El cierre global depende de apply real y validación de corridas en entornos dev/intg.

Definición de terminado:

- [ ] Jobs visibles en Terraform state y en Cloud Scheduler.
- [ ] Se observa al menos una corrida exitosa de cada job en intg.
- [x] Documentación operativa alineada con el comportamiento real.

Dependencias:

- EPIC-02 para validación en entorno real.

Riesgos:

- Exposición accidental de endpoints internos sin política de invocación estricta.

Mitigación:

- Restringir invocadores y validar IAM por principal mínimo necesario.

### Bloqueos activos para cerrar EPIC-03 (externos al entorno local)

- B3.1 Falta aplicar Terraform en proyecto objetivo con credenciales/plataforma habilitadas.
- B3.2 Falta validar ejecución real de jobs y trazas en Cloud Logging (dev/intg).
- B3.3 El flujo canónico del módulo (con backend GCS) requiere bucket de state y acceso de plataforma para plan/apply en entornos reales.

### Próximos pasos mínimos para destrabar

- P3.1 Ejecutar `terraform apply` en dev con variables reales y verificar creación de jobs.
- P3.2 Forzar una corrida manual de cada job y capturar evidencia de éxito (Scheduler + Cloud Run logs).
- P3.3 Repetir validación completa en intg y actualizar este backlog con evidencia.
- P3.4 Ejecutar checklist de operación en [docs/epic-03-scheduler-runbook.md](docs/epic-03-scheduler-runbook.md).

### Checklist final de cierre global EPIC-03 (dev/intg)

- [ ] Preparación backend/workspace: `terraform init -backend-config="bucket=<TF_STATE_BUCKET>" -reconfigure`.

- [ ] Selección workspace dev/intg: `terraform workspace select dev` (repetir luego con `intg`).

- [ ] Plan controlado: `terraform plan -out=tfplan -var-file=terraform.tfvars`.

- [ ] Apply controlado: `terraform apply tfplan`.

- [ ] Verificación jobs: `gcloud scheduler jobs list --location <SCHEDULER_LOCATION>` incluye `amg-decay-weights-daily` y `amg-prune-weights-weekly`.

- [ ] Corrida manual decay: `gcloud scheduler jobs run amg-decay-weights-daily --location <SCHEDULER_LOCATION>`.

- [ ] Corrida manual prune: `gcloud scheduler jobs run amg-prune-weights-weekly --location <SCHEDULER_LOCATION>`.

- [ ] Logs Cloud Run de ambos endpoints con campos `job_id`, `schedule_time`, `tenant_id`, `operation`, `result=success`.

- [ ] Alertas activas para fallo de ejecución y ausencia de ejecución esperada en decay/prune.

- [ ] Evidencia dev adjunta en este backlog (comandos + salidas o capturas).

- [ ] Evidencia intg adjunta en este backlog (comandos + salidas o capturas).

- [ ] Definición de terminado de EPIC-03 marcada completa.

---

## EPIC-04 (P1): Descubrimiento MCP y contrato de integración

Estado en este entorno: EN EJECUCIÓN (implementación local desarrollada).
Estado global de la épica: PARCIAL (pendiente validación en entorno real con clientes internos).

Objetivo:

- Publicar endpoint de descubrimiento para auto-configuración de clientes MCP.

Resultado de negocio:

- Disminución del esfuerzo de integración y menor fricción para adopción por equipos.

Tareas:

- [x] T4.1 Diseñar contrato de GET /.well-known/mcp con versionado.
  Estado: completada en local con contrato `manifest_version=1.0` y `supported_versions` en [src/models/mcp.py](src/models/mcp.py).
- [x] T4.2 Incluir catálogo de tools soportadas, esquema de parámetros, errores y capacidades.
  Estado: completada en local con catálogo tipado y capacidades en [src/mcp/service.py](src/mcp/service.py).
- [x] T4.3 Añadir pruebas de contrato para endpoint de discovery.
  Estado: completada en local con tests de endpoint/versionado en [tests/unit/test_mcp_api.py](tests/unit/test_mcp_api.py).
- [x] T4.4 Añadir compatibilidad hacia atrás para cambios no disruptivos del manifiesto.
  Estado: completada en local con normalización de versión `1` -> `1.0` y alias `tool_catalog` en [src/mcp/service.py](src/mcp/service.py) y [src/models/mcp.py](src/models/mcp.py).
- [x] T4.5 Documentar ejemplos de auto-configuración para clientes internos.
  Estado: completada en local en [docs/user-guide/mcp-tools.md](docs/user-guide/mcp-tools.md).

### Ejecución directa EPIC-04 (evidencia 2026-07-01)

Evidencia técnica observada:

- Endpoint de discovery agregado en [src/api/main.py](src/api/main.py): `GET /.well-known/mcp`.
- Contratos tipados de discovery agregados en [src/models/mcp.py](src/models/mcp.py).
- Fuente de verdad del manifiesto y compatibilidad en [src/mcp/service.py](src/mcp/service.py).
- Pruebas de contrato de discovery en [tests/unit/test_mcp_api.py](tests/unit/test_mcp_api.py).
- Guía de uso actualizada para auto-configuración MCP en [docs/user-guide/mcp-tools.md](docs/user-guide/mcp-tools.md).

Validaciones locales ejecutadas:

- `uv run ruff check src/models/mcp.py src/mcp/service.py src/api/main.py tests/unit/test_mcp_api.py`: OK.
- `uv run pytest tests/unit/test_mcp_api.py -q`: 5 passed.

Definición de terminado:

- [x] Endpoint publicado y cubierto por tests (alcance local).
- [x] Esquema versionado con política de compatibilidad documentada (alcance local).

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

- [x] T5.1 Decidir modelo de tenancy de Spanner (instancia por equipo vs compartida con aislamiento).
  Estado: completada con decisión aceptada en [docs/architecture/adr/ADR-0001-spanner-tenancy-model.md](docs/architecture/adr/ADR-0001-spanner-tenancy-model.md).
- [x] T5.2 Decidir política de modelo de síntesis (fijo vs configurable por caller).
  Estado: completada con decisión aceptada en [docs/architecture/adr/ADR-0002-synthesis-model-policy.md](docs/architecture/adr/ADR-0002-synthesis-model-policy.md).
- [x] T5.3 Decidir estrategia de export de AUDIT_EVENTS para cumplimiento y analítica.
  Estado: completada con decisión aceptada en [docs/architecture/adr/ADR-0003-audit-events-export-strategy.md](docs/architecture/adr/ADR-0003-audit-events-export-strategy.md).
- [x] T5.4 Decidir si weight_pruning_threshold será global o por tenant.
  Estado: completada con decisión aceptada en [docs/architecture/adr/ADR-0004-pruning-threshold-scope.md](docs/architecture/adr/ADR-0004-pruning-threshold-scope.md).
- [x] T5.5 Registrar decisiones en ADRs y actualizar docs de arquitectura/backlog/config.
  Estado: completada con ADR index en [docs/architecture/adr/README.md](docs/architecture/adr/README.md) y alineación en docs/código.

### Ejecución directa EPIC-05 (evidencia 2026-07-01)

Evidencia técnica observada:

- ADRs creados y aceptados:
  - [docs/architecture/adr/ADR-0001-spanner-tenancy-model.md](docs/architecture/adr/ADR-0001-spanner-tenancy-model.md)
  - [docs/architecture/adr/ADR-0002-synthesis-model-policy.md](docs/architecture/adr/ADR-0002-synthesis-model-policy.md)
  - [docs/architecture/adr/ADR-0003-audit-events-export-strategy.md](docs/architecture/adr/ADR-0003-audit-events-export-strategy.md)
  - [docs/architecture/adr/ADR-0004-pruning-threshold-scope.md](docs/architecture/adr/ADR-0004-pruning-threshold-scope.md)
- Índice ADR agregado en [docs/architecture/adr/README.md](docs/architecture/adr/README.md).
- Arquitectura alineada con decisiones en [docs/architecture.md](docs/architecture.md).
- Deployment alineado con freeze de decisiones en [docs/deployment.md](docs/deployment.md).
- Concepto de weighting alineado con umbral global en [docs/concepts/cognitive-weighting.md](docs/concepts/cognitive-weighting.md).
- Índice de documentación actualizado en [docs/index.md](docs/index.md).
- Comentarios de código alineados con decisiones en [src/db/schema.py](src/db/schema.py) y [src/memory/mindmap_pipeline.py](src/memory/mindmap_pipeline.py).

Definición de terminado:

- [x] Todas las decisiones anteriores tienen ADR aprobado.
- [x] No quedan secciones contradictorias entre arquitectura, configuración y operación.

Dependencias:

- Ninguna.

Riesgos:

- Decisiones tardías que impacten código ya desplegado.

Mitigación:

- Timebox de decisiones y comité técnico con due dates explícitas.

---

## EPIC-06 (P1): SLOs empresariales y operación basada en objetivos

Estado en este entorno: COMPLETADA en alcance local (todo lo implementable sin apply en GCP administrado).
Estado global de la épica: PARCIAL (pendiente activación/validación en proyectos reales dev/intg/prod).

Objetivo:

- Definir SLOs del producto y conectarlos a monitoreo y alertamiento accionable.

Resultado de negocio:

- Operación predecible con objetivos medibles y gestión de error budget.

Tareas:

- [x] T6.1 Definir SLO de disponibilidad (99.5%) por entorno.
  Estado: completada en local con SLO `availability-995` en [infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf).
- [x] T6.2 Definir SLO de latencia (p95 para MEMORY_SEARCH y endpoints clave).
  Estado: completada en local con SLO `latency-p95` y umbral configurable en [infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf) y [infrastructure/terraform/variables.tf](infrastructure/terraform/variables.tf).
- [x] T6.3 Definir SLO de tasa de error (5xx y errores funcionales por tool).
  Estado: completada en local con SLO de éxito de invocaciones MCP (`error-rate`) basado en métrica de logs etiquetada por `success` en [infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf).
- [x] T6.4 Implementar recursos Terraform de SLO y alertas de burn rate.
  Estado: completada en local con `google_monitoring_custom_service`, tres `google_monitoring_slo` y tres alertas de burn-rate short/long window en [infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf).
- [x] T6.5 Crear dashboard ejecutivo y dashboard técnico con los mismos indicadores base.
  Estado: completada en local con dashboards `executive_slo` y `technical_slo` en [infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf).
- [x] T6.6 Definir protocolo de incidentes vinculado a SLOs (severidad, TTR, postmortem).
  Estado: completada con protocolo en [docs/epic-06-slo-incident-protocol.md](docs/epic-06-slo-incident-protocol.md).

### Ejecución directa EPIC-06 (evidencia 2026-07-02)

Evidencia técnica observada:

- Variables SLO/burn-rate agregadas y validadas en [infrastructure/terraform/variables.tf](infrastructure/terraform/variables.tf).
- Valores de referencia para operación agregados en [infrastructure/terraform/terraform.tfvars.example](infrastructure/terraform/terraform.tfvars.example).
- Servicio custom de Monitoring para SLOs agregado en [infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf).
- SLOs implementados:
  - disponibilidad 99.5%
  - latencia p95 <= 500ms
  - error-rate (éxito >= 99.0%)
- Alertas burn-rate short/long para cada SLO implementadas en [infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf).
- Dashboards ejecutivo/técnico implementados en [infrastructure/terraform/monitoring.tf](infrastructure/terraform/monitoring.tf).
- Outputs operativos de SLO/dashboards expuestos en [infrastructure/terraform/outputs.tf](infrastructure/terraform/outputs.tf).
- Protocolo de incidentes con severidad, TTA/TTM/TTR y postmortem en [docs/epic-06-slo-incident-protocol.md](docs/epic-06-slo-incident-protocol.md).
- Referencia operativa de dashboards actualizada en [docs/testing-health-dashboard.md](docs/testing-health-dashboard.md).

Validaciones locales ejecutadas:

- `terraform fmt` en [infrastructure/terraform](infrastructure/terraform): OK.
- `terraform validate` en módulo local backendless aislado: OK.

Conclusión de ejecución:

- EPIC-06 queda cerrada en alcance local.
- Cierre global depende de apply en proyectos reales y validación de señales en Cloud Monitoring.

Definición de terminado:

- [ ] SLOs activos y auditables en Cloud Monitoring.
- [ ] Alertas de burn rate enrutadas a canales operativos.

Dependencias:

- EPIC-02 y EPIC-03 para señales reales de producción.

Riesgos:

- SLOs poco realistas al inicio por falta de baseline operacional.

Mitigación:

- Definir periodo de calibración inicial y ajustar con evidencia de 2-4 semanas.

### Bloqueos activos para cerrar EPIC-06 (externos al entorno local)

- B6.1 Falta `terraform apply` en dev/intg/prod con backend remoto y credenciales de plataforma.
- B6.2 Falta confirmar disponibilidad del recurso `google_monitoring_slo` y `google_monitoring_dashboard` en el tenant/proyecto objetivo con permisos efectivos.
- B6.3 Falta enrutar notification channels reales (Pager/Email/ChatOps) para alertas burn-rate.

### Próximos pasos mínimos para destrabar

- P6.1 Ejecutar apply en dev y validar creación de servicio custom, SLOs, alertas y dashboards.
- P6.2 Confirmar eventos de burn-rate con prueba controlada y evidencia en Cloud Monitoring.
- P6.3 Configurar y validar canales operativos reales en `notification_channels`.
- P6.4 Ajustar objetivos/umbrales tras 2-4 semanas de baseline operacional.

---

## EPIC-07 (P1): Habilitación de adopción LATAM

Estado en este entorno: COMPLETADA en alcance local (todo lo implementable sin onboarding en proyectos reales).
Estado global de la épica: PARCIAL (pendiente piloto real con equipo LATAM y validación operativa externa).

Objetivo:

- Estandarizar onboarding y operación para nuevos equipos en LATAM.

Resultado de negocio:

- Menor tiempo de adopción por equipo y menor carga de soporte ad-hoc.

Tareas:

- [x] T7.1 Crear playbook de adopción paso a paso para nuevos equipos.
  Estado: completada con playbook versionado en [docs/epic-07-adoption-playbook.md](docs/epic-07-adoption-playbook.md).
- [x] T7.2 Publicar checklist de prerequisitos por rol (plataforma, seguridad, data owner).
  Estado: completada con checklist por rol en [docs/epic-07-onboarding-checklist.md](docs/epic-07-onboarding-checklist.md).
- [x] T7.3 Registrar servicio en catálogo (Backstage/Cosmos) con ownership y metadatos completos.
  Estado: completada en alcance local con actualización de metadata, tags y enlaces operativos en [catalog-info.yaml](../catalog-info.yaml).
- [x] T7.4 Definir modelo de soporte operativo (canales, SLAs internos, escalamiento).
  Estado: completada con modelo formal en [docs/epic-07-support-model.md](docs/epic-07-support-model.md).
- [x] T7.5 Ejecutar un piloto de onboarding con un equipo LATAM y capturar lecciones.
  Estado: completada en alcance local mediante piloto simulado con hallazgos y bloqueos en [docs/epic-07-pilot-onboarding-report.md](docs/epic-07-pilot-onboarding-report.md).

### Ejecución directa EPIC-07 (evidencia 2026-07-01)

Evidencia técnica observada:

- Playbook de adopción creado en [docs/epic-07-adoption-playbook.md](docs/epic-07-adoption-playbook.md).
- Checklist de prerequisitos por rol creada en [docs/epic-07-onboarding-checklist.md](docs/epic-07-onboarding-checklist.md).
- Modelo de soporte operativo con SLA y escalamiento en [docs/epic-07-support-model.md](docs/epic-07-support-model.md).
- Reporte de piloto (local/simulado) con lecciones y bloqueos en [docs/epic-07-pilot-onboarding-report.md](docs/epic-07-pilot-onboarding-report.md).
- Registro de catalogo enriquecido (ownership, tags, links y techdocs) en [catalog-info.yaml](../catalog-info.yaml).
- Descubribilidad de documentos EPIC-07 en índice de documentación [docs/index.md](docs/index.md).

Validaciones locales ejecutadas:

- Revisión estática de errores en documentos EPIC-07: OK.

Conclusión de ejecución:

- EPIC-07 queda cerrada en alcance local.
- Cierre global depende de ejecución de un onboarding real en entorno administrado.

Definición de terminado:

- [ ] Playbook versionado y validado por al menos un onboarding real.
- [x] Servicio registrado en catálogo con enlaces vivos a docs, dashboards y runbooks (alcance local).

Dependencias:

- EPIC-02 y EPIC-06 recomendados.

Riesgos:

- Diferencias entre áreas/países de LATAM que rompan un proceso único.

Mitigación:

- Definir plantilla base + anexos regionales por variaciones regulatorias o de plataforma.

### Bloqueos activos para cerrar EPIC-07 (externos al entorno local)

- B7.1 Falta ejecutar onboarding real con un equipo LATAM en proyectos dev/intg/prod reales.
- B7.2 Falta validar canales corporativos de soporte y escalamiento en operación real.
- B7.3 Falta confirmar publicación efectiva del catálogo en instancia Backstage/Cosmos corporativa.

### Próximos pasos mínimos para destrabar

- P7.1 Seleccionar equipo piloto real y aplicar checklist por rol.
- P7.2 Ejecutar onboarding real guiado por el playbook y adjuntar evidencia en este backlog.
- P7.3 Monitorear SLA de soporte por 2-4 semanas y ajustar el modelo.
- P7.4 Confirmar visibilidad del componente en Backstage/Cosmos corporativo.

---

## EPIC-08 (P2): Consolidación estructural del programa de testing (TST-04)

Estado en este entorno: COMPLETADA en alcance local.
Estado global de la épica: COMPLETADA (sin dependencias externas para su cierre).

Objetivo:

- Reducir complejidad estructural y costo de mantenimiento de pruebas.

Resultado de negocio:

- Menor tiempo de diagnóstico/fix y mayor velocidad de evolución sin perder cobertura.

Tareas:

- [x] T8.1 Dividir archivos monolíticos en specs por capacidad.
  Estado: completada al descomponer la suite monolítica de `MemoryAPI` en:
  - [tests/unit/test_memory_api_sessions_and_facts.py](../tests/unit/test_memory_api_sessions_and_facts.py)
  - [tests/unit/test_memory_api_context_and_graph.py](../tests/unit/test_memory_api_context_and_graph.py)
  - [tests/unit/test_memory_api_weighting_and_session_closure.py](../tests/unit/test_memory_api_weighting_and_session_closure.py)
- [x] T8.2 Mover escenarios sobre-mockeados de integración a unit/contract cuando corresponda.
  Estado: completada moviendo cobertura con stubs de MCP desde integración a unit/contract en [tests/unit/test_mcp_emulator_contract.py](../tests/unit/test_mcp_emulator_contract.py).
- [x] T8.3 Retirar duplicados inmediatamente al introducir reemplazos canónicos.
  Estado: completada retirando el escenario previo tras reemplazo canónico en unit/contract (sin duplicados nuevos detectados por gobernanza).
- [x] T8.4 Crear toolkit común de fixtures/builders/fakes reutilizables.
  Estado: completada incorporando builders reutilizables (`context_turn_row_factory`, `context_response_factory`) en [tests/conftest.py](../tests/conftest.py).
- [x] T8.5 Definir límites de complejidad por archivo de test y regla de enforcement.
  Estado: completada con límite `max_test_file_lines` y enforcement en [scripts/test_suite_governance.py](../scripts/test_suite_governance.py), configurado en [docs/testing-governance-baseline.json](testing-governance-baseline.json) y documentado en [docs/testing-governance.md](testing-governance.md).
- [x] T8.6 Añadir métrica de deuda de testing (top archivos por tamaño/complejidad) en dashboard.
  Estado: completada agregando `new_large_test_file_violations` y `lines_per_test_item` en [scripts/generate_testing_health_dashboard.py](../scripts/generate_testing_health_dashboard.py), con evidencia en [reports/testing-health-dashboard.md](../reports/testing-health-dashboard.md).

### Ejecución directa EPIC-08 (evidencia 2026-07-01)

Evidencia técnica observada:

- Refactor estructural aplicado y validado sobre suite de `MemoryAPI`.
- Reclasificación de prueba sobre-mockeada de integración hacia unit/contract.
- Enforcements de gobernanza extendidos para complejidad por archivo.
- Dashboard de salud actualizado con indicador de concentración `lines_per_test_item`.
- Inventario de gobernanza regenerado sin nuevas violaciones.

Validaciones locales ejecutadas:

- `uv run ruff check` sobre archivos de test modificados: OK.
- `uv run pytest tests/unit/test_memory_api_sessions_and_facts.py tests/unit/test_memory_api_context_and_graph.py tests/unit/test_memory_api_weighting_and_session_closure.py tests/unit/test_mcp_emulator_contract.py -q`: 18 passed.
- `just test-governance-audit`: OK, sin violaciones nuevas.
- `just test-health-dashboard`: OK, métricas regeneradas.

Definición de terminado:

- [x] Disminuye complejidad promedio en archivos objetivo.
- [x] No quedan duplicados semánticos aprobados para retiro.

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
