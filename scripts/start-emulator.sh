#!/bin/bash
# Start the Google Cloud Spanner Emulator for local development

set -e

PROJECT_ID="test-project"
INSTANCE_ID="test-instance"
DATABASE_ID="test-database"

echo "Starting Google Cloud Spanner Emulator..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI not found. Please install Google Cloud SDK."
    exit 1
fi

# Check if emulator is already running
if lsof -Pi :9010 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Spanner Emulator is already running on port 9010"
else
    # Start the emulator
    gcloud emulators spanner start --host-port=0.0.0.0:9010 &
    EMULATOR_PID=$!
    echo "Spanner Emulator started with PID $EMULATOR_PID"
    
    # Wait for emulator to be ready
    sleep 3
fi

# Initialize gcloud to use the emulator
export SPANNER_EMULATOR_HOST=localhost:9010

# Create instance if it doesn't exist
echo "Setting up Spanner instance and database..."
gcloud config set project $PROJECT_ID

if ! gcloud spanner instances list --project=$PROJECT_ID | grep -q $INSTANCE_ID; then
    echo "Creating Spanner instance: $INSTANCE_ID"
    gcloud spanner instances create $INSTANCE_ID \
        --config=emulator-config \
        --description="Test instance for Agent Memory Graph" \
        --project=$PROJECT_ID
else
    echo "Instance $INSTANCE_ID already exists"
fi

# Create database if it doesn't exist
if ! gcloud spanner databases list --instance=$INSTANCE_ID --project=$PROJECT_ID | grep -q $DATABASE_ID; then
    echo "Creating Spanner database: $DATABASE_ID"
    gcloud spanner databases create $DATABASE_ID \
        --instance=$INSTANCE_ID \
        --project=$PROJECT_ID
else
    echo "Database $DATABASE_ID already exists"
fi

echo "Spanner Emulator is ready!"
echo "Environment variables set:"
echo "  SPANNER_EMULATOR_HOST=$SPANNER_EMULATOR_HOST"
echo "  GCP_PROJECT_ID=$PROJECT_ID"
echo "  SPANNER_INSTANCE_ID=$INSTANCE_ID"
echo "  SPANNER_DATABASE_ID=$DATABASE_ID"

# Keep the emulator running
wait
