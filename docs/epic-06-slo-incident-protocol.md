# EPIC-06 Incident Protocol (SLO-driven Operations)

## Objetivo

Definir respuesta operativa unificada para incidentes gatillados por burn-rate de SLOs de Agent Memory Graph.

SLOs objetivo en esta fase:

- Disponibilidad: 99.5% (rolling 30d).
- Latencia: 95% de solicitudes por debajo de 500 ms.
- Tasa de error: 99.0% de invocaciones exitosas (<= 1.0% error funcional/5xx).

## Clasificacion de severidad

- SEV-1:
  - Burn rate corto y largo superan umbral en prod para disponibilidad.
  - Impacto de cliente visible en procesos criticos.
  - Respuesta esperada: mitigacion inicial <= 15 minutos.
- SEV-2:
  - Burn rate corto supera umbral en latencia o error-rate, sin caida total.
  - Degradacion funcional significativa para equipos internos.
  - Respuesta esperada: mitigacion inicial <= 30 minutos.
- SEV-3:
  - Desviaciones persistentes en intg/dev o alertas intermitentes en prod.
  - Sin impacto de negocio inmediato.
  - Respuesta esperada: mitigacion inicial <= 4 horas.

## TTR y objetivos de gestion

- TTA (time to acknowledge):
  - SEV-1: <= 5 minutos.
  - SEV-2: <= 10 minutos.
  - SEV-3: <= 30 minutos.
- TTM (time to mitigate):
  - SEV-1: <= 60 minutos.
  - SEV-2: <= 120 minutos.
  - SEV-3: <= 1 dia habil.
- TTR (time to recovery):
  - SEV-1: <= 4 horas.
  - SEV-2: <= 8 horas.
  - SEV-3: <= 3 dias habiles.

## Protocolo operativo

1. Deteccion y triage

- Confirmar alerta en Cloud Monitoring (burn-rate short/long).
- Identificar SLO afectado y entorno.
- Clasificar severidad con tabla anterior.

1. Contencion

- Aplicar mitigacion rapida (rollback, escalado de Cloud Run, rate limiting).
- Verificar si la dependencia principal es Spanner, Cloud Run, IAM, o red.

1. Diagnostico

- Revisar dashboards tecnico/ejecutivo de SLO.
- Correlacionar con:
  - logs estructurados `mcp_tool_invoke_finish`
  - metricas de latencia/error por tool
  - cambios recientes de despliegue.

1. Comunicacion

- Notificar estado en canal operativo definido por plataforma.
- Actualizar cada 15 minutos en SEV-1 y cada 30 minutos en SEV-2.

1. Recuperacion

- Confirmar normalizacion de burn rate.
- Validar salud de endpoints clave:
  - /health
  - /api/v1/mcp/invoke
  - /api/v1/mindmap/execute

1. Cierre

- Documentar linea de tiempo del incidente.
- Registrar causa raiz y acciones correctivas.

## Postmortem obligatorio

Requerido para SEV-1 y SEV-2. Recomendado para SEV-3 repetidos.

Plantilla minima:

- Resumen ejecutivo
- Impacto de negocio
- Timeline UTC
- SLO y error budget consumido
- Causa raiz tecnica
- Factores contribuyentes
- Acciones inmediatas y acciones preventivas
- Owner y fecha compromiso por accion

## Evidencia minima para auditoria

- Captura o enlace de alerta original.
- Query/logs usados para diagnostico.
- Confirmacion de recuperacion de SLO.
- Documento de postmortem (cuando aplique).
