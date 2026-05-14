# deploy.ps1 — Ceph V3 GCP deployment script
# Copyright (c) 2026 David Hans Elze / Cuttlefish Labs
#
# TODO: gcloud auth login (interactive — run manually before executing this script)
# TODO: gcloud config set project $env:GOOGLE_CLOUD_PROJECT
# TODO: gcloud services enable aiplatform.googleapis.com run.googleapis.com secretmanager.googleapis.com logging.googleapis.com
# TODO: Deploy agent service to Cloud Run
# TODO: Set secrets in Secret Manager (ARIZE_API_KEY, ARIZE_SPACE_ID)
# TODO: Assign service account IAM roles (roles/aiplatform.user, roles/secretmanager.secretAccessor)

param(
    [string]$Project = $env:GOOGLE_CLOUD_PROJECT,
    [string]$Region  = "us-central1"
)

Write-Host "ceph-v3 deploy — not yet implemented. See infra/README.md for manual steps."
