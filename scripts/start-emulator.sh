#!/bin/bash
# Start the Google Cloud Spanner Emulator for local development.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-test-project}"
INSTANCE_ID="${INSTANCE_ID:-test-instance}"
DATABASE_ID="${DATABASE_ID:-test-database}"
GCLOUD_CONFIG_NAME="${SPANNER_EMULATOR_GCLOUD_CONFIG:-spanner-emulator}"
EMULATOR_GRPC_HOSTPORT="${SPANNER_EMULATOR_HOSTPORT:-localhost:9010}"
EMULATOR_REST_ENDPOINT="${SPANNER_EMULATOR_REST_ENDPOINT:-http://localhost:9020/}"
DOCKER_IMAGE="gcr.io/cloud-spanner-emulator/emulator"
DOCKER_CONTAINER_NAME="spanner-emulator"

echo "Starting Google Cloud Spanner Emulator..."

if ! command -v gcloud >/dev/null 2>&1; then
    echo "Error: gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

run_gcloud_emulator() {
    CLOUDSDK_ACTIVE_CONFIG_NAME="$GCLOUD_CONFIG_NAME" gcloud --quiet "$@"
}

port_is_listening() {
    local port="$1"
    lsof -Pi ":${port}" -sTCP:LISTEN -t >/dev/null 2>&1
}

wait_for_port() {
    local port="$1"
    local timeout_seconds="$2"
    local waited=0

    until port_is_listening "$port"; do
        sleep 1
        waited=$((waited + 1))
        if [[ "$waited" -ge "$timeout_seconds" ]]; then
            return 1
        fi
    done
}

configure_emulator_gcloud() {
    if ! gcloud config configurations describe "$GCLOUD_CONFIG_NAME" >/dev/null 2>&1; then
        gcloud config configurations create "$GCLOUD_CONFIG_NAME" --no-activate >/dev/null
    fi

    run_gcloud_emulator config set auth/disable_credentials true >/dev/null
    run_gcloud_emulator config set project "$PROJECT_ID" >/dev/null
    run_gcloud_emulator config set api_endpoint_overrides/spanner "$EMULATOR_REST_ENDPOINT" >/dev/null
}

start_with_gcloud_component() {
    gcloud emulators spanner start --host-port=0.0.0.0:9010 &
    EMULATOR_PID=$!
    echo "Spanner Emulator started with PID $EMULATOR_PID"

    if ! wait_for_port 9010 15 || ! wait_for_port 9020 15; then
        echo "Error: Spanner emulator did not become ready on ports 9010/9020."
        kill "$EMULATOR_PID" >/dev/null 2>&1 || true
        exit 1
    fi
}

start_with_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "Error: Docker is not installed, and the gcloud emulator component is unavailable."
        echo "Install the cloud-spanner-emulator component or Docker Desktop."
        exit 1
    fi

    if docker ps --format '{{.Names}}' | grep -qx "$DOCKER_CONTAINER_NAME"; then
        echo "Spanner emulator container is already running"
    else
        docker rm -f "$DOCKER_CONTAINER_NAME" >/dev/null 2>&1 || true
        docker run -d --rm \
            --name "$DOCKER_CONTAINER_NAME" \
            -p 9010:9010 \
            -p 9020:9020 \
            "$DOCKER_IMAGE" >/dev/null
        echo "Spanner emulator started in Docker container '$DOCKER_CONTAINER_NAME'"
    fi

    if ! wait_for_port 9010 15 || ! wait_for_port 9020 15; then
        echo "Error: Dockerized Spanner emulator did not become ready on ports 9010/9020."
        exit 1
    fi
}

if port_is_listening 9010 && port_is_listening 9020; then
    echo "Spanner Emulator is already running on ports 9010 and 9020"
elif gcloud components list --filter='id=cloud-spanner-emulator' --format='value(id)' | grep -qx 'cloud-spanner-emulator'; then
    start_with_gcloud_component
else
    echo "gcloud emulator component is unavailable; falling back to Docker"
    start_with_docker
fi

export SPANNER_EMULATOR_HOST="$EMULATOR_GRPC_HOSTPORT"

configure_emulator_gcloud

echo "Setting up Spanner instance and database..."

if ! run_gcloud_emulator spanner instances list --project="$PROJECT_ID" | grep -q "$INSTANCE_ID"; then
    echo "Creating Spanner instance: $INSTANCE_ID"
    run_gcloud_emulator spanner instances create "$INSTANCE_ID" \
        --config=emulator-config \
        --description="Test instance for Agent Memory Graph" \
        --nodes=1 \
        --project="$PROJECT_ID"
else
    echo "Instance $INSTANCE_ID already exists"
fi

if ! run_gcloud_emulator spanner databases list --instance="$INSTANCE_ID" --project="$PROJECT_ID" | grep -q "$DATABASE_ID"; then
    echo "Creating Spanner database: $DATABASE_ID"
    run_gcloud_emulator spanner databases create "$DATABASE_ID" \
        --instance="$INSTANCE_ID" \
        --project="$PROJECT_ID"
else
    echo "Database $DATABASE_ID already exists"
fi

echo "Spanner Emulator is ready!"
echo "Environment variables set:"
echo "  SPANNER_EMULATOR_HOST=$SPANNER_EMULATOR_HOST"
echo "  GCP_PROJECT_ID=$PROJECT_ID"
echo "  SPANNER_INSTANCE_ID=$INSTANCE_ID"
echo "  SPANNER_DATABASE_ID=$DATABASE_ID"
echo "  GCLOUD_CONFIG_NAME=$GCLOUD_CONFIG_NAME"

if [[ -n "${EMULATOR_PID:-}" ]]; then
    wait "$EMULATOR_PID"
else
    echo "Docker mode is running in the background. Stop it with: docker rm -f $DOCKER_CONTAINER_NAME"
fi
