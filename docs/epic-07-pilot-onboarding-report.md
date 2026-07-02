# EPIC-07 Reporte de Piloto de Onboarding

## Estado

Piloto ejecutado en alcance local (simulacion controlada de onboarding),
sin despliegue real en proyectos productivos gestionados por plataforma.

## Equipo piloto (simulado)

- Equipo: Revenue Analytics LATAM (simulado para ejecucion local).
- Objetivo inicial: validar onboarding end-to-end en entorno de desarrollo.

## Actividades ejecutadas

- Se definio playbook de onboarding estandar.
- Se publico checklist de prerequisitos por rol.
- Se formalizo modelo de soporte operativo y escalamiento.
- Se actualizo metadata de catalogo para ownership y enlaces de operacion.
- Se registro evidencia y bloqueos en backlog.

## Resultados

- El flujo de onboarding quedo documentado y versionado.
- Los criterios de entrada/salida quedaron definidos.
- El modelo operativo reduce ambiguedad para nuevos equipos.

## Lecciones aprendidas

- La principal fuente de bloqueo no es tecnica local, sino de plataforma:
  - permisos IAM efectivos,
  - variables CI/CD reales,
  - activacion de APIs/recursos en proyectos objetivo.
- La adopcion mejora cuando owner tecnico y data owner se nombran desde intake.
- El registro temprano en catalogo evita perdida de contexto operativo.

## Bloqueos externos para piloto real

- Falta ejecutar onboarding contra proyectos reales dev/intg/prod.
- Falta evidencia de pipeline real y smoke en Cloud Run desplegado.
- Falta validacion en canales operativos corporativos reales.

## Siguientes pasos para cerrar piloto real

1. Ejecutar onboarding con un equipo LATAM real usando este playbook.
2. Adjuntar evidencia de despliegue y smoke checks en backlog.
3. Validar SLA/escalamiento durante una ventana de 2-4 semanas.
4. Ajustar playbook/checklist segun hallazgos del piloto real.
