# ============================================================
#  Antigravity OTC - Deploy to Google Cloud Run (PowerShell)
# ============================================================
#
#  Prerequisites:
#    1. Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
#    2. Log in:       gcloud auth login
#    3. Set project:  gcloud config set project adpo-healthcare-agent
#    4. Enable APIs:  gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
#
#  Run from VS Code terminal (PowerShell):
#    .\deploy.ps1
# ============================================================

$PROJECT_ID = "adpo-healthcare-agent"
$REGION = "us-central1"
$SERVICE_NAME = "antigravity-otc"
$REPO_NAME = "antigravity-repo"
$IMAGE_TAG = "latest"
$IMAGE_URL = "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_NAME/${SERVICE_NAME}:$IMAGE_TAG"

# Step 1: Create Artifact Registry (one-time, ignore error if exists)
Write-Host ">>> Creating Artifact Registry repository (if not exists)..." -ForegroundColor Cyan
gcloud artifacts repositories create $REPO_NAME `
  --repository-format=docker `
  --location=$REGION `
  --description="Antigravity OTC container images" `
  --project=$PROJECT_ID 2>$null

# Step 2: Build with Cloud Build
Write-Host ">>> Building container image with Cloud Build..." -ForegroundColor Cyan
gcloud builds submit `
  --tag $IMAGE_URL `
  --project=$PROJECT_ID `
  --timeout=1200s

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Cloud Build failed. Check logs above." -ForegroundColor Red
    exit 1
}

# Step 3: Deploy to Cloud Run
Write-Host ">>> Deploying to Cloud Run..." -ForegroundColor Cyan
gcloud run deploy $SERVICE_NAME `
  --image $IMAGE_URL `
  --platform managed `
  --region $REGION `
  --project $PROJECT_ID `
  --port 8080 `
  --memory 1Gi `
  --cpu 2 `
  --min-instances 0 `
  --max-instances 3 `
  --timeout 120 `
  --allow-unauthenticated `
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID" `
  --set-env-vars "RISK_THRESHOLD_HIGH=0.50" `
  --set-env-vars "MAX_REMEDIATION_ATTEMPTS=3" `
  --set-env-vars "NPPES_API_BASE=https://npiregistry.cms.hhs.gov/api/" `
  --set-env-vars "NPI_MATCH_CONFIDENCE_THRESHOLD=0.90" `
  --set-env-vars "USE_MOCK_AUTH=true"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Cloud Run deployment failed." -ForegroundColor Red
    exit 1
}

# Step 4: Get the service URL
$SERVICE_URL = gcloud run services describe $SERVICE_NAME `
  --region $REGION `
  --project $PROJECT_ID `
  --format "value(status.url)"

Write-Host ""
Write-Host ">>> Deployment complete!" -ForegroundColor Green
Write-Host "  Frontend:  $SERVICE_URL" -ForegroundColor Yellow
Write-Host "  API:       $SERVICE_URL/api/v1/orders" -ForegroundColor Yellow
Write-Host "  Health:    $SERVICE_URL/health" -ForegroundColor Yellow
