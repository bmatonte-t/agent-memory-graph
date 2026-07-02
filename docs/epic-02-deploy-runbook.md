# EPIC-02 Deployment Runbook

## Objetivo

Cerrar EPIC-02 fuera del entorno local: despliegue real en dev/intg con evidencia verificable.

## Alcance

Este runbook cubre solamente lo que requiere acceso a plataformas externas (GitLab CI + GCP).

## Nota sobre smoke local

En entorno local sin Spanner inicializado:

- `GET /health` puede responder OK.
- Endpoints funcionales que requieren lectura/escritura de memoria (MCP, MindMap, graph export)
  pueden fallar con errores de inicialización de Spanner.

Estas fallas locales no invalidan EPIC-02; solo indican que el cierre final depende
de despliegue real en dev/intg.

## Prerrequisitos

- Acceso de maintainer a variables del proyecto en GitLab.
- Permisos GCP para operar Cloud Run, Artifact Registry, Spanner, Secret Manager y Service Usage.
- API run.googleapis.com habilitada en proyectos objetivo.
- Estado local ya preparado:
  - [infrastructure/terraform/.terraform.lock.hcl](infrastructure/terraform/.terraform.lock.hcl) versionado.
  - Validación local Terraform OK.

## Checklist operativo

### 1) Variables CI obligatorias

Configurar en GitLab CI/CD variables:

- TF_STATE_BUCKET
- GCP_PROJECT_ID_DEV
- GCP_PROJECT_ID_INTG
- GCP_PROJECT_ID_PROD
- GCP_REGION
- COMPANY_ID
- WORKLOAD_IDENTITY_PROVIDER (preferido)
- WORKLOAD_IDENTITY_SERVICE_ACCOUNT (preferido)

Evidencia requerida:

- Captura o export del panel de variables (sin exponer secretos).
- Fecha y responsable de la carga.

### 2) Verificación de APIs por proyecto

Para cada proyecto objetivo (dev/intg/prod):

- run.googleapis.com
- artifactregistry.googleapis.com
- spanner.googleapis.com
- secretmanager.googleapis.com
- iamcredentials.googleapis.com
- serviceusage.googleapis.com

Evidencia requerida:

- Salida de gcloud services list --enabled por proyecto.

### 3) Deploy dev

- Ejecutar pipeline en rama develop.
- Confirmar build-image exitoso.
- Confirmar write-tfvars exitoso.
- Confirmar plan/apply dev exitoso.

Evidencia requerida:

- URL de pipeline.
- Job IDs de build, plan y apply.
- Hash de imagen desplegada.

### 4) Smoke post-deploy dev

Ejecutar contra URL real del servicio dev:

- GET /health
- POST /api/v1/mcp/invoke (tool de lectura)
- POST /api/v1/mindmap/execute
- GET /api/v1/graph/export?tenant_id=<tenant>

Evidencia requerida:

- Request/response resumido por endpoint.
- Latencia observada.
- Resultado (OK/FAIL).

### 5) Deploy intg

- Ejecutar pipeline en rama intg.
- Confirmar plan/apply intg exitoso.
- Confirmar notificaciones/alertas habilitadas en intg.

Evidencia requerida:

- URL de pipeline intg.
- Job IDs de plan/apply.
- Confirmación de alertas activas.

### 6) Smoke post-deploy intg

Repetir smoke de dev sobre endpoint intg.

Evidencia requerida:

- Resultados por endpoint.
- Diferencias relevantes respecto de dev.

## Criterios de cierre de EPIC-02

- Dev e intg desplegados con evidencia de ejecución y rollback probado.
- Smoke funcional completo en dev e intg.
- Checklist de salida firmado por plataforma + seguridad + data.

## Plantilla de evidencia (copiar/pegar)

### EPIC-02 Evidence Log

- Fecha:
- Responsable:
- Pipeline dev URL:
- Pipeline intg URL:
- Imagen desplegada dev:
- Imagen desplegada intg:
- Smoke dev: PASS/FAIL
- Smoke intg: PASS/FAIL
- Alertas intg verificadas: SI/NO
- Rollback probado: SI/NO
- Firma Plataforma:
- Firma Seguridad:
- Firma Data:
