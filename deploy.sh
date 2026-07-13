# ============================================================
#  Antigravity OTC — Deploy to Google Cloud Run
# ============================================================
#
#  Prerequisites:
#    1. Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
#    2. Log in:       gcloud auth login
#    3. Set project:  gcloud config set project adpo-healthcare-agent
#    4. Enable APIs:  gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
#
#  Run this script from the project root (F:\order_to_cash_denial_reduction)
#  in VS Code terminal (Git Bash or PowerShell).
# ============================================================

# ---------- Configuration ----------
PROJECT_ID="adpo-healthcare-agent"
REGION="us-central1"
SERVICE_NAME="quest-smart-otc"
REPO_NAME="quest-smart-otc-repo"
IMAGE_TAG="latest"
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"

# ---------- Step 1: Create Artifact Registry (one-time) ----------
echo ">>> Creating Artifact Registry repository (if not exists)..."
gcloud artifacts repositories create ${REPO_NAME} \
  --repository-format=docker \
  --location=${REGION} \
  --description="Quest Smart OTC container images" \
  --project=${PROJECT_ID} 2>/dev/null || true

# ---------- Step 2: Build with Cloud Build ----------
echo ">>> Building container image with Cloud Build..."
gcloud builds submit \
  --tag ${IMAGE_URL} \
  --project=${PROJECT_ID} \
  --timeout=1200s

# ---------- Step 3: Deploy to Cloud Run ----------
echo ">>> Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_URL} \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --port 8080 \
  --memory 1Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 120 \
  --allow-unauthenticated \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID}" \
  --set-env-vars "RISK_THRESHOLD_HIGH=0.50" \
  --set-env-vars "MAX_REMEDIATION_ATTEMPTS=3" \
  --set-env-vars "NPPES_API_BASE=https://npiregistry.cms.hhs.gov/api/" \
  --set-env-vars "NPI_MATCH_CONFIDENCE_THRESHOLD=0.90" \
  --set-env-vars "USE_MOCK_AUTH=true"

# ---------- Step 4: Get the service URL ----------
echo ""
echo ">>> Deployment complete!"
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --format "value(status.url)")
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "  Frontend:  ${SERVICE_URL}"
echo "  API:       ${SERVICE_URL}/api/v1/orders"
echo "  Health:    ${SERVICE_URL}/health"
