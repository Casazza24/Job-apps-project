#!/usr/bin/env bash
set -euo pipefail

# One-time GCP project setup
# Usage: ./infra/setup_gcp.sh

export PROJECT_ID="${PROJECT_ID:-job-agent-yourname}"
export REGION="${REGION:-us-central1}"

echo "Setting up GCP project: $PROJECT_ID"

gcloud projects create "$PROJECT_ID" || echo "Project may already exist, continuing..."
gcloud config set project "$PROJECT_ID"

gcloud services enable \
  run.googleapis.com \
  compute.googleapis.com \
  storage.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  iap.googleapis.com \
  aiplatform.googleapis.com

export BUCKET_NAME="job-agent-files-${PROJECT_ID}"
gsutil mb -l "$REGION" "gs://$BUCKET_NAME" || echo "Bucket may already exist"

echo "Storing secrets in Secret Manager..."
echo "Run these commands with your actual values:"
echo ""
echo "  echo -n 'your_linkedin_email'    | gcloud secrets create LINKEDIN_EMAIL --data-file=-"
echo "  echo -n 'your_linkedin_password' | gcloud secrets create LINKEDIN_PASSWORD --data-file=-"
echo "  echo -n 'your_indeed_email'      | gcloud secrets create INDEED_EMAIL --data-file=-"
echo "  echo -n 'your_indeed_password'   | gcloud secrets create INDEED_PASSWORD --data-file=-"
echo "  echo -n 'your_handshake_email'   | gcloud secrets create HANDSHAKE_EMAIL --data-file=-"
echo "  echo -n 'your_handshake_password'| gcloud secrets create HANDSHAKE_PASSWORD --data-file=-"
echo "  echo -n 'your_glassdoor_email'   | gcloud secrets create GLASSDOOR_EMAIL --data-file=-"
echo "  echo -n 'your_glassdoor_password'| gcloud secrets create GLASSDOOR_PASSWORD --data-file=-"
echo "  echo -n 'your_greenhouse_email'  | gcloud secrets create GREENHOUSE_EMAIL --data-file=-"
echo "  echo -n 'your_greenhouse_pw'     | gcloud secrets create GREENHOUSE_PASSWORD --data-file=-"
echo "  echo -n 'your_sendgrid_key'      | gcloud secrets create SENDGRID_API_KEY --data-file=-"
echo "  echo -n 'Your'                   | gcloud secrets create CANDIDATE_FIRST_NAME --data-file=-"
echo "  echo -n 'Name'                   | gcloud secrets create CANDIDATE_LAST_NAME --data-file=-"
echo "  echo -n 'youremail@gmail.com'    | gcloud secrets create CANDIDATE_EMAIL --data-file=-"

echo ""
echo "Creating Compute Engine VM..."
gcloud compute instances create job-agent-vm \
  --zone="${REGION}-a" \
  --machine-type=e2-small \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --boot-disk-size=20GB \
  --scopes=cloud-platform \
  --tags=job-agent \
  --metadata-from-file=startup-script=infra/vm_startup.sh

echo "GCP setup complete. VM: job-agent-vm in zone ${REGION}-a"
echo "SSH: gcloud compute ssh job-agent-vm --zone=${REGION}-a"
