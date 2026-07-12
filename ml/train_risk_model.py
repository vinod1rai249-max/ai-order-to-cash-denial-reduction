import os
import logging
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enforce Design Review Item #2 in code via assertions
REQUIRED_FEATURES = [
    "payer_id",
    "cpt_code",
    "icd10_code",
    "prior_auth_on_file",
    "timely_filing_days_remaining",
    "historical_payer_denial_rate_for_cpt"
]

# Assert that no demographic features are in this list
PROHIBITED_FEATURES = {"npi", "dob", "gender", "address", "patient_id"}
assert not set(REQUIRED_FEATURES).intersection(PROHIBITED_FEATURES), (
    "Security Violation: Demographics and hard-fail presence columns are "
    "prohibited from model training features to prevent memorization."
)

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET_PREFIX = os.environ.get("BQ_DATASET", "")

if not GCP_PROJECT_ID:
    raise ValueError("GCP_PROJECT_ID environment variable is required")

def get_table_ref(dataset_name: str, table_name: str) -> str:
    dataset = f"{BQ_DATASET_PREFIX}_{dataset_name}" if BQ_DATASET_PREFIX else dataset_name
    return f"{GCP_PROJECT_ID}.{dataset}.{table_name}"

def train_model() -> None:
    client = bigquery.Client(project=GCP_PROJECT_ID)
    model_ref = get_table_ref("ml", "risk_model")
    training_table_ref = get_table_ref("ml", "synthetic_claims_training")
    
    # Constructing SQL query dynamically with the configured tables
    features_str = ",\n  ".join(REQUIRED_FEATURES)
    sql = f"""
    CREATE OR REPLACE MODEL `{model_ref}`
    OPTIONS(
      model_type = 'LOGISTIC_REG',
      input_label_cols = ['label_denied'],
      auto_class_weights = TRUE
    ) AS
    SELECT
      {features_str},
      label_denied
    FROM `{training_table_ref}`;
    """
    
    logger.info(f"Starting BQML training job for model: {model_ref}...")
    try:
        query_job = client.query(sql)
        query_job.result()  # Wait for training to complete
        logger.info(f"BQML Model {model_ref} trained successfully.")
    except GoogleAPICallError as e:
        logger.error(f"BQML training failed: {e}")
        raise

if __name__ == "__main__":
    train_model()
