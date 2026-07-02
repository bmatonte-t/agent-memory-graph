# EPIC-07 Modelo de Soporte Operativo

## Objetivo

Definir un modelo de soporte repetible para equipos LATAM que adopten
Agent Memory Graph, con acuerdos internos de respuesta y escalamiento.

## Canales operativos

- Canal primario: canal de operaciones del equipo (ChatOps corporativo).
- Canal secundario: issue tracker del producto para defectos y mejoras.
- Canal de crisis: bridge de incidente para eventos SEV-1/SEV-2.

## Clasificacion de tickets

- P1 (critico): servicio degradado o caido en prod.
- P2 (alto): degradacion funcional relevante sin caida total.
- P3 (medio): errores puntuales o deuda operativa.
- P4 (bajo): consultas, mejoras y tareas no urgentes.

## SLA internos

- P1:
  - Acknowledge: <= 15 min.
  - Mitigacion inicial: <= 60 min.
  - Recuperacion objetivo: <= 4 h.
- P2:
  - Acknowledge: <= 30 min.
  - Mitigacion inicial: <= 4 h.
  - Recuperacion objetivo: <= 1 dia habil.
- P3:
  - Acknowledge: <= 4 h habiles.
  - Resolucion objetivo: <= 3 dias habiles.
- P4:
  - Acknowledge: <= 1 dia habil.
  - Resolucion objetivo: priorizacion en sprint.

## Esquema de escalamiento

1. Nivel 1 (equipo adoptante)

- Ejecuta triage inicial y runbook basico.
- Escala a Nivel 2 si no hay mitigacion en ventana acordada.

1. Nivel 2 (AMG Core)

- Analiza causa tecnica de producto.
- Coordina cambios de configuracion, rollback o hotfix.
- Escala a Nivel 3 si hay dependencia de plataforma o proveedor.

1. Nivel 3 (Plataforma/Seguridad)

- Atiende fallas de infraestructura, IAM, red o cumplimiento.
- Coordina comunicacion institucional en incidentes mayores.

## Indicadores de soporte

- MTTA por severidad.
- MTTR por severidad.
- Porcentaje de tickets dentro de SLA.
- Incidentes repetidos por categoria de causa.

## Gobernanza

- Revision semanal de tickets abiertos (operaciones + AMG Core).
- Revision mensual de tendencias y deuda operativa.
- Revision trimestral de SLA y reglas de escalamiento.
