#!/usr/bin/env bash
# Deploys the backend to Cloud Run:
#   build image -> push to Artifact Registry -> run database migrations -> deploy -> health check
#   (rolls back to the previous revision automatically if the health check fails).
#
# Usage:  ./scripts/deploy.sh staging|production [image-tag]
# Needs:  gcloud (logged in), docker. Used by the GitHub Actions deploy workflow too.
set -euo pipefail

ENVIRONMENT="${1:-}"
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
  echo "Usage: $0 staging|production [image-tag]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DEPLOY_FILE="config/${ENVIRONMENT}.deploy.env"
ENV_FILE="config/${ENVIRONMENT}.env.yaml"

set -a
# shellcheck disable=SC1090
source "$DEPLOY_FILE"
set +a

if [[ -z "${ALEMBIC_TARGET:-}" ]]; then
  echo "ERROR: $DEPLOY_FILE must set ALEMBIC_TARGET to an explicit Alembic revision or branch head." >&2
  exit 1
fi

if grep -q "REPLACE_ME" "$ENV_FILE"; then
  echo "ERROR: $ENV_FILE still contains REPLACE_ME values. Fill them in first (docs/03-configuration.md)." >&2
  exit 1
fi

TAG="${2:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPOSITORY}/${IMAGE_NAME}:${TAG}"
GCLOUD=(gcloud --project "$PROJECT_ID" --quiet)

echo "==> [1/5] Building and pushing $IMAGE"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build --platform linux/amd64 -t "$IMAGE" .
docker push "$IMAGE"

echo "==> [2/5] Running Alembic target $ALEMBIC_TARGET (Cloud Run job $MIGRATE_JOB_NAME)"
"${GCLOUD[@]}" run jobs deploy "$MIGRATE_JOB_NAME" --region "$REGION" --image "$IMAGE" \
  --service-account "$RUNTIME_SERVICE_ACCOUNT" \
  --set-cloudsql-instances "$CLOUD_SQL_INSTANCE" \
  --env-vars-file "$ENV_FILE" --set-secrets "$SECRETS" \
  --command alembic --args upgrade,"$ALEMBIC_TARGET" \
  --max-retries 0 --task-timeout 600
"${GCLOUD[@]}" run jobs execute "$MIGRATE_JOB_NAME" --region "$REGION" --wait

PREVIOUS_REVISION="$("${GCLOUD[@]}" run services describe "$SERVICE_NAME" --region "$REGION" \
  --format='value(status.latestReadyRevisionName)' 2>/dev/null || true)"

echo "==> [3/5] Deploying Cloud Run service $SERVICE_NAME"
"${GCLOUD[@]}" run deploy "$SERVICE_NAME" --region "$REGION" --image "$IMAGE" \
  --service-account "$RUNTIME_SERVICE_ACCOUNT" \
  --add-cloudsql-instances "$CLOUD_SQL_INSTANCE" \
  --env-vars-file "$ENV_FILE" --set-secrets "$SECRETS" \
  --allow-unauthenticated --port 8080 \
  --cpu "$CPU" --memory "$MEMORY" --concurrency "$CONCURRENCY" \
  --min-instances "$MIN_INSTANCES" --max-instances "$MAX_INSTANCES" \
  --timeout "$REQUEST_TIMEOUT"

URL="$("${GCLOUD[@]}" run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)')"

echo "==> [4/5] Health check $URL/api/v1/readyz"
for attempt in 1 2 3 4 5 6; do
  if curl -fsS "$URL/api/v1/readyz"; then
    echo
    echo "==> [5/5] Deployed $TAG to $ENVIRONMENT: $URL"
    exit 0
  fi
  echo "   not ready yet (attempt $attempt), waiting..."
  sleep 10
done

echo "ERROR: health check failed." >&2
if [[ -n "$PREVIOUS_REVISION" ]]; then
  echo "Rolling back traffic to $PREVIOUS_REVISION" >&2
  "${GCLOUD[@]}" run services update-traffic "$SERVICE_NAME" --region "$REGION" \
    --to-revisions "${PREVIOUS_REVISION}=100"
fi
exit 1
