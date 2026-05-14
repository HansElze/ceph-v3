# GCP Bootstrap — ceph-v3-sentinel

Manual setup steps for the GCP project. Run these once before week 2 infra work.

## 1. Create or reuse GCP project

```powershell
gcloud projects create ceph-v3-sentinel --name="Ceph V3 Sentinel"
gcloud config set project ceph-v3-sentinel
```

Or reuse an existing project and update `.env` with `GOOGLE_CLOUD_PROJECT`.

## 2. Enable required APIs

```powershell
gcloud services enable `
    aiplatform.googleapis.com `
    run.googleapis.com `
    secretmanager.googleapis.com `
    logging.googleapis.com
```

## 3. Create service account and download key

```powershell
gcloud iam service-accounts create ceph-v3-sa `
    --display-name="Ceph V3 Service Account"

gcloud projects add-iam-policy-binding ceph-v3-sentinel `
    --member="serviceAccount:ceph-v3-sa@ceph-v3-sentinel.iam.gserviceaccount.com" `
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding ceph-v3-sentinel `
    --member="serviceAccount:ceph-v3-sa@ceph-v3-sentinel.iam.gserviceaccount.com" `
    --role="roles/secretmanager.secretAccessor"

gcloud iam service-accounts keys create gcp-key.json `
    --iam-account="ceph-v3-sa@ceph-v3-sentinel.iam.gserviceaccount.com"
```

> `gcp-key.json` is gitignored. Never commit it.

## 4. Set environment variables

Copy `.env.example` to `.env` and fill in:

```
GOOGLE_CLOUD_PROJECT=ceph-v3-sentinel
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\dvdel\Cuttlefish\ceph-v3\gcp-key.json
```

## 5. Verify setup

```powershell
gcloud auth list
gcloud projects describe ceph-v3-sentinel
python -c "import google.adk; print('ADK OK')"
```

## APIs enabled

| API | Purpose |
|-----|---------|
| `aiplatform.googleapis.com` | Vertex AI / Gemini 3.1 |
| `run.googleapis.com` | Cloud Run deployment |
| `secretmanager.googleapis.com` | Arize keys at runtime |
| `logging.googleapis.com` | Cloud Logging |
