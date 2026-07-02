# EPIC-07 Playbook de Adopcion LATAM

## Objetivo

Estandarizar la adopcion de Agent Memory Graph (AMG) por nuevos equipos LATAM,
reduciendo tiempo de onboarding y carga operativa ad-hoc.

## Alcance

Este playbook cubre:

- Actividades previas al onboarding (prerequisitos y ownership).
- Ejecucion de onboarding tecnico por entorno (dev/intg/prod).
- Validaciones de operacion minima (health, MCP, observabilidad, auditoria).
- Criterios de salida y handoff a operacion continua.

## Roles involucrados

- Plataforma: provision de proyectos, IAM, CI/CD y Terraform backend.
- Seguridad: validacion de permisos minimos y secretos.
- Data Owner: validacion funcional de casos de uso del equipo.
- AMG Core: soporte tecnico de producto, patrones MCP, runbooks.

## Flujo de onboarding estandar

1. Intake y alcance

- Confirmar equipo objetivo, owner tecnico y owner de negocio.
- Registrar alcance inicial (herramientas MCP y datasets candidatos).
- Definir fecha objetivo de go-live en dev.

1. Prerequisitos de plataforma

- Confirmar triada de proyectos: `dev`, `intg`, `prod`.
- Confirmar SA CI/CD y bucket de estado Terraform.
- Confirmar API y cuotas necesarias habilitadas.

1. Setup de configuracion

- Completar variables CI/CD por entorno.
- Validar `company_id`, region y canales de notificacion.
- Revisar metadata de catalogo y ownership.

1. Despliegue dev

- Ejecutar pipeline de despliegue en `develop`.
- Verificar recursos base provisionados (Cloud Run, Spanner, Monitoring).
- Ejecutar smoke tecnico y smoke funcional minimo.

1. Validacion intg

- Promover cambios a `intg`.
- Repetir smoke y validaciones operativas.
- Confirmar alertas y dashboards funcionales.

1. Preparacion prod

- Revisar riesgos abiertos y plan de rollback.
- Validar runbooks de incidente y soporte operativo.
- Ejecutar gate de aprobacion de negocio/plataforma.

1. Handoff a operacion

- Entregar evidencia de onboarding en backlog/reportes.
- Confirmar canal de soporte y esquema de escalamiento.
- Agendar revision de estabilizacion (2-4 semanas).

## Evidencia minima por onboarding

- Pipeline de deploy dev/intg/prod con estado exitoso.
- Resultado de smoke checks:
  - `GET /health`
  - `POST /api/v1/mcp/invoke`
  - endpoint de ejecucion MindMap
- Confirmacion de alertas y dashboards activos.
- Registro de ownership y enlaces en catalogo.
- Registro de riesgos y decisiones en backlog.

## Criterios de salida

Un onboarding se considera completo cuando:

- El equipo opera AMG en dev e intg con evidencia verificable.
- El servicio aparece en catalogo con owner y runbooks.
- Existe modelo de soporte activo con SLA interno y escalamiento.
- El Data Owner confirma valor funcional en al menos un caso de uso.

## Riesgos frecuentes y mitigaciones

- Variables incompletas en CI/CD:
  - Mitigacion: checklist por rol obligatorio antes de deploy.
- Permisos IAM insuficientes:
  - Mitigacion: validacion temprana de SA y APIs con plataforma.
- Baseline SLO insuficiente para prod:
  - Mitigacion: periodo de calibracion con seguimiento semanal.
