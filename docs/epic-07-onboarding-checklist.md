# EPIC-07 Checklist de Prerequisitos por Rol

## Uso

Esta checklist se ejecuta antes de iniciar onboarding de un nuevo equipo LATAM.
Todas las casillas criticas deben estar completas para habilitar despliegue en dev.

## Plataforma

- [ ] Proyectos `dev/intg/prod` creados y accesibles.
- [ ] `cosmos-cicd-sa` presente en cada proyecto.
- [ ] Bucket de estado Terraform asignado y accesible.
- [ ] APIs requeridas habilitadas (Cloud Run, Spanner, Monitoring, Secret Manager, Scheduler).
- [ ] Artifact Registry creado en cada proyecto.
- [ ] Variables CI/CD base cargadas:
  - [ ] `GCP_PROJECT_ID_DEV`
  - [ ] `GCP_PROJECT_ID_INTG`
  - [ ] `GCP_PROJECT_ID_PROD`
  - [ ] `GCP_REGION`
  - [ ] `TF_STATE_BUCKET`

## Seguridad

- [ ] Modelo de autenticacion definido (`internal` o `external`).
- [ ] Secretos requeridos disponibles y con acceso minimo necesario.
- [ ] IAM validado para despliegue e invocacion segura.
- [ ] Politica de auditoria y retencion confirmada.
- [ ] Canal de incidentes de seguridad definido.

## Data Owner

- [ ] Caso de uso inicial seleccionado y documentado.
- [ ] Datos de prueba autorizados para dev/intg.
- [ ] Criterios de aceptacion funcional definidos.
- [ ] Responsable de validacion funcional nombrado.

## AMG Core

- [ ] Version objetivo de despliegue acordada.
- [ ] Runbooks de operacion e incidente compartidos.
- [ ] Dashboard de testing y SLO disponible para el equipo.
- [ ] Sesion de handoff tecnico calendarizada.

## Cierre de checklist

- [ ] Checklist validada por Plataforma.
- [ ] Checklist validada por Seguridad.
- [ ] Checklist validada por Data Owner.
- [ ] Checklist validada por AMG Core.
- [ ] Fecha de inicio de onboarding aprobada.
