#!/usr/bin/env bash
# Runs an operator command (python -m app.cli ...) inside Google Cloud as a one-off Cloud Run job,
# using the same image, database and secrets as the live service.
#
# Usage examples:
#   ./scripts/run-cli.sh production grant-existing-admin --email admin@college.com --name "College Admin"
#   ./scripts/run-cli.sh production list-admins
set -euo pipefail

ENVIRONMENT="${1:-}"
shift || true
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" || $# -eq 0 ]]; then
  echo "Usage: $0 staging|production <command> [options]  (see: python -m app.cli --help)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a
# shellcheck disable=SC1090
source "$ROOT/config/${ENVIRONMENT}.deploy.env"
set +a
GCLOUD=(gcloud --project "$PROJECT_ID" --quiet)

IMAGE="$("${GCLOUD[@]}" run services describe "$SERVICE_NAME" --region "$REGION" \
  --format='value(spec.template.spec.containers[0].image)')"
ARGS="-m,app.cli$(printf ' %s' "$@")"

"${GCLOUD[@]}" run jobs deploy college-cli --region "$REGION" --image "$IMAGE" \
  --service-account "$RUNTIME_SERVICE_ACCOUNT" \
  --set-cloudsql-instances "$CLOUD_SQL_INSTANCE" \
  --env-vars-file "$ROOT/config/${ENVIRONMENT}.env.yaml" --set-secrets "$SECRETS" \
  --command python --args "$ARGS" --max-retries 0 --task-timeout 600
"${GCLOUD[@]}" run jobs execute college-cli --region "$REGION" --wait
echo "Done. Output: Cloud Console -> Cloud Run -> Jobs -> college-cli -> Logs"
