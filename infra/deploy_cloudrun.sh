#!/usr/bin/env bash
set -euo pipefail

# Deploy the FastAPI dashboard to Cloud Run
# Usage: ./infra/deploy_cloudrun.sh

export PROJECT_ID="${PROJECT_ID:-job-agent-yourname}"
export REGION="${REGION:-us-central1}"
export BUCKET_NAME="${BUCKET_NAME:-job-agent-files-${PROJECT_ID}}"
export VM_INTERNAL_IP="${VM_INTERNAL_IP:-10.128.0.2}"

gcloud config set project "$PROJECT_ID"

cd "$(dirname "$0")/../dashboard"

gcloud run deploy job-agent-dashboard \
  --source . \
  --region "$REGION" \
  --platform managed \
  --no-allow-unauthenticated \
  --set-env-vars "ENV=production" \
  --set-env-vars "DATABASE_URL=postgresql://jobagent:jobagent@${VM_INTERNAL_IP}/jobagent" \
  --set-env-vars "BUCKET_NAME=${BUCKET_NAME}" \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID}"

CLOUD_RUN_URL=$(gcloud run services describe job-agent-dashboard \
  --region "$REGION" --format='value(status.url)')

echo "Dashboard deployed at: $CLOUD_RUN_URL"
echo ""
echo "Setting up Cloud Scheduler..."

gcloud scheduler jobs create http scraper-morning \
  --location="$REGION" \
  --schedule="0 8 * * *" \
  --uri="${CLOUD_RUN_URL}/trigger/scraper" \
  --http-method=POST \
  --time-zone="America/Chicago" || echo "Scheduler job may already exist"

gcloud scheduler jobs create http scraper-evening \
  --location="$REGION" \
  --schedule="0 18 * * *" \
  --uri="${CLOUD_RUN_URL}/trigger/scraper" \
  --http-method=POST \
  --time-zone="America/Chicago" || echo "Scheduler job may already exist"

gcloud scheduler jobs create http tracker-daily \
  --location="$REGION" \
  --schedule="0 12 * * *" \
  --uri="${CLOUD_RUN_URL}/trigger/tracker" \
  --http-method=POST \
  --time-zone="America/Chicago" || echo "Scheduler job may already exist"

echo ""
echo "Enabling Cloud IAP..."
gcloud iap web enable \
  --resource-type=cloud-run \
  --service=job-agent-dashboard \
  --region="$REGION" || echo "IAP may already be enabled"

echo ""
echo "Grant yourself access with:"
echo "  gcloud iap web add-iam-policy-binding \\"
echo "    --resource-type=cloud-run \\"
echo "    --service=job-agent-dashboard \\"
echo "    --region=$REGION \\"
echo "    --member='user:YOUR_GOOGLE_EMAIL' \\"
echo "    --role='roles/iap.httpsResourceAccessor'"
