# EPIC-03 Scheduler Runbook

## Objetivo

Operar y recuperar los jobs de Cloud Scheduler que ejecutan mantenimiento cognitivo:

- Decay diario de pesos.
- Prune semanal de nodos por umbral cognitivo.

## Alcance

Este runbook cubre:

- Verificacion de despliegue de Scheduler via Terraform.
- Verificacion de ejecuciones y logs en Cloud Run.
- Diagnostico rapido de fallos.
- Acciones de recuperacion y rollback operativo.

## Componentes

- Terraform jobs e IAM: [infrastructure/terraform/scheduler.tf](infrastructure/terraform/scheduler.tf)
- Variables scheduler: [infrastructure/terraform/variables.tf](infrastructure/terraform/variables.tf)
- Endpoints internos con logs: [src/api/main.py](src/api/main.py)
- Runtime de scheduler config: [src/memory/cognitive_weighting.py](src/memory/cognitive_weighting.py)
- Pruebas de contrato scheduler: [tests/integration/test_scheduler_integration.py](tests/integration/test_scheduler_integration.py)

## Configuracion esperada

- Decay schedule: `0 2 * * *` (UTC)
- Prune schedule: `0 3 * * 0` (UTC, domingo)
- Decay payload: `{ "decay_rate": 0.05 }`
- Prune payload: `{ "threshold": 0.30 }`
- Autenticacion: OIDC desde SA dedicada de Scheduler.

## Checklist pre-deploy

- [ ] Variables reales de entorno cargadas (project, region, notification channels).
- [ ] Cloud Scheduler API habilitada en proyecto objetivo.
- [ ] Cloud Run service desplegado y accesible.
- [ ] IAM invoker minimo necesario aplicado para SA de Scheduler.
- [ ] Plan Terraform sin cambios inesperados.

## Deploy y verificacion

1. Inicializar y validar Terraform:

```bash
cd infrastructure/terraform
terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

1. Aplicar en entorno objetivo:

```bash
terraform apply tfplan
```

### Dry-plan local sin backend remoto (solo evidencia tecnica)

Cuando no hay acceso al bucket de state ni permisos de plataforma, se puede validar
el plan de forma local en una copia temporal del modulo:

```bash
cd /path/to/repo
rm -rf /tmp/amg-tf-epic03-plan
mkdir -p /tmp/amg-tf-epic03-plan
rsync -a infrastructure/terraform/ /tmp/amg-tf-epic03-plan/

# Quitar temporalmente el bloque backend "gcs" de la copia (no del repo)
awk '
BEGIN{skip=0; depth=0}
{
  if (skip==0 && $0 ~ /^  backend "gcs" \{/) { skip=1; depth=1; next }
  if (skip==1) {
    if ($0 ~ /\{/) depth++
    if ($0 ~ /\}/) depth--
    if (depth==0) { skip=0; next }
    next
  }
  print
}
' /tmp/amg-tf-epic03-plan/config.tf > /tmp/amg-tf-epic03-plan/config.tf.nobackend
mv /tmp/amg-tf-epic03-plan/config.tf.nobackend /tmp/amg-tf-epic03-plan/config.tf

cd /tmp/amg-tf-epic03-plan
terraform init -reconfigure
terraform workspace select dev || terraform workspace new dev
terraform plan -refresh=false -input=false -lock=false -var-file=/tmp/amg_epic03_local.tfvars
```

Nota:

- Este flujo no reemplaza el plan/apply canonico con backend GCS.
- Sirve para validar cambios Terraform en entorno local y generar evidencia previa.

1. Verificar jobs creados:

```bash
gcloud scheduler jobs list --location <scheduler_location>
```

1. Forzar corrida de prueba decay:

```bash
gcloud scheduler jobs run amg-decay-weights-daily --location <scheduler_location>
```

1. Forzar corrida de prueba prune:

```bash
gcloud scheduler jobs run amg-prune-weights-weekly --location <scheduler_location>
```

1. Verificar logs de Cloud Run para cada corrida:

- Confirmar presencia de campos: `job_id`, `schedule_time`, `tenant_id`, `operation`, `result`.
- Confirmar resultado `success` para ambas operaciones.

## Diagnostico rapido

Si un job falla:

1. Revisar ejecucion en Cloud Scheduler:

```bash
gcloud scheduler jobs describe <job_name> --location <scheduler_location>
```

1. Revisar logs de Cloud Run endpoint interno:

- `/internal/decay-weights`
- `/internal/prune-weights`

1. Verificar permisos IAM del invocador:

- SA de scheduler debe tener `roles/run.invoker` sobre servicio Cloud Run.

1. Verificar OIDC audience:

- Debe coincidir con URI base del servicio Cloud Run.

## Acciones de recuperacion

- Error de payload:
  - Ajustar `scheduler_decay_rate` o `scheduler_prune_threshold` en variables Terraform.
  - Reaplicar y rerun del job.

- Error de autenticacion:
  - Validar SA de scheduler, binding `roles/run.invoker`, y audience.
  - Reaplicar Terraform.

- Error runtime (500):
  - Revisar conectividad y estado de Spanner.
  - Revisar errores del endpoint interno y dependencia de base de datos.

## Rollback operativo

- Pausar temporalmente jobs (sin destruir infraestructura) para cortar impacto:

```bash
gcloud scheduler jobs pause amg-decay-weights-daily --location <scheduler_location>
gcloud scheduler jobs pause amg-prune-weights-weekly --location <scheduler_location>
```

- Reanudar cuando se resuelva incidente:

```bash
gcloud scheduler jobs resume amg-decay-weights-daily --location <scheduler_location>
gcloud scheduler jobs resume amg-prune-weights-weekly --location <scheduler_location>
```

## Evidencia requerida para cierre de EPIC-03

- Captura de `terraform apply` exitoso con recursos scheduler creados.
- Captura de `gcloud scheduler jobs list` con ambos jobs activos.
- Evidencia de al menos una corrida exitosa por job en dev e intg.
- Enlace o extracto de logs con metadata de corrida y resultado.
- Confirmacion de alertas activas y notificando en canales esperados.

## Bloqueos conocidos

- Requiere permisos de plataforma y APIs habilitadas fuera del entorno local actual.
