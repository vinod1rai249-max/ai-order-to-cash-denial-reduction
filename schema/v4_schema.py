import os
import logging
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Retrieve environment variables
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET_PREFIX = os.environ.get("BQ_DATASET", "")

if not GCP_PROJECT_ID:
    raise ValueError("GCP_PROJECT_ID environment variable is required")

def get_table_ref(dataset_name: str, table_name: str) -> str:
    """Constructs fully qualified table reference."""
    dataset = f"{BQ_DATASET_PREFIX}_{dataset_name}" if BQ_DATASET_PREFIX else dataset_name
    return f"{GCP_PROJECT_ID}.{dataset}.{table_name}"

def get_dataset_ref(dataset_name: str) -> str:
    """Constructs fully qualified dataset reference."""
    dataset = f"{BQ_DATASET_PREFIX}_{dataset_name}" if BQ_DATASET_PREFIX else dataset_name
    return f"{GCP_PROJECT_ID}.{dataset}"

def create_v4_tables() -> None:
    """
    Idempotently creates the BigQuery datasets and tables required for the
    denial reduction and auto-remediation system.
    """
    client = bigquery.Client(project=GCP_PROJECT_ID)

    datasets = ["ml", "reference", "silver"]
    for ds_name in datasets:
        ds_ref = get_dataset_ref(ds_name)
        dataset = bigquery.Dataset(ds_ref)
        dataset.location = "US"
        try:
            client.create_dataset(dataset, exists_ok=True)
            logger.info(f"Dataset {ds_ref} verified/created.")
        except GoogleAPICallError as e:
            logger.error(f"Failed to create dataset {ds_ref}: {e}")
            raise

    # 1. ml.synthetic_claims_training
    synthetic_table_id = get_table_ref("ml", "synthetic_claims_training")
    synthetic_schema = [
        bigquery.SchemaField("claim_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("payer_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("cpt_code", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("icd10_code", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("npi", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("dob", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("gender", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("address", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("patient_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("prior_auth_on_file", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("timely_filing_days_remaining", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("historical_payer_denial_rate_for_cpt", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("label_denied", "BOOLEAN", mode="REQUIRED"),
        bigquery.SchemaField("denial_reason_code", "STRING", mode="NULLABLE"),
    ]
    
    # 2. reference.reject_code_catalog
    catalog_table_id = get_table_ref("reference", "reject_code_catalog")
    catalog_schema = [
        bigquery.SchemaField("reject_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("description", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("owning_agent", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("auto_fixable", "BOOLEAN", mode="REQUIRED"),
        bigquery.SchemaField("data_source_key", "STRING", mode="NULLABLE"),
    ]

    # 3. silver.orders
    orders_table_id = get_table_ref("silver", "orders")
    orders_schema = [
        bigquery.SchemaField("order_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("claim_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("npi", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("payer_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("cpt_code", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("icd10_code", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("dob", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("gender", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("address", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("patient_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("employer_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("provider_first_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("provider_last_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("provider_state", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("provider_taxonomy", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("risk_score", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("risk_history", "JSON", mode="NULLABLE"),
        bigquery.SchemaField("remediation_attempts", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("trace_id", "STRING", mode="NULLABLE"),
    ]

    tables_to_create = [
        (synthetic_table_id, synthetic_schema),
        (catalog_table_id, catalog_schema),
        (orders_table_id, orders_schema),
    ]

    for table_id, schema in tables_to_create:
        table = bigquery.Table(table_id, schema=schema)
        try:
            client.create_table(table, exists_ok=True)
            logger.info(f"Table {table_id} verified/created.")
        except GoogleAPICallError as e:
            logger.error(f"Failed to create table {table_id}: {e}")
            raise

    # Initialize governance sink
    from governance.governance_logger import init_governance_sink
    init_governance_sink()

def seed_reject_code_catalog() -> int:
    """
    Seeds the reference.reject_code_catalog table using MERGE query to avoid duplicate rows.
    Returns the number of rows upserted.
    """
    client = bigquery.Client(project=GCP_PROJECT_ID)
    catalog_table_id = get_table_ref("reference", "reject_code_catalog")

    # Catalog rows from §2 of the specification
    catalog_data = [
        {"reject_code": "NPI_MISSING_OR_INVALID", "description": "NPI missing or incorrect", "owning_agent": "AGENT_NPI", "auto_fixable": True, "data_source_key": "NPPES_API"},
        {"reject_code": "13", "description": "Partial response", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": False, "data_source_key": "PAYER_RESPONSE_HISTORY"},
        {"reject_code": "14", "description": "Invalid diagnosis", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": True, "data_source_key": "ICD10_LOOKUP_TABLE"},
        {"reject_code": "15", "description": "Other insurance primary", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": True, "data_source_key": "COB_PAYER_ELIGIBILITY_API"},
        {"reject_code": "19", "description": "Invalid DOB / gender", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": True, "data_source_key": "PATIENT_DEMOGRAPHICS"},
        {"reject_code": "21", "description": "Cannot identify patient", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": True, "data_source_key": "MPI_MATCH"},
        {"reject_code": "30", "description": "Incorrect address", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": True, "data_source_key": "ADDRESS_VALIDATION_SERVICE"},
        {"reject_code": "32", "description": "Lab out of network", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": False, "data_source_key": "PROVIDER_NETWORK_DIRECTORY"},
        {"reject_code": "33", "description": "Visit/benefit exceeded", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": False, "data_source_key": "BENEFIT_ACCUMULATOR"},
        {"reject_code": "39", "description": "Employer name needed", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": True, "data_source_key": "EMPLOYER_MASTER"},
        {"reject_code": "40", "description": "Patient info needed", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": True, "data_source_key": "PATIENT_MASTER"},
        {"reject_code": "45", "description": "Non-covered service", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": False, "data_source_key": "PAYER_COVERAGE_POLICY"},
        {"reject_code": "52", "description": "Another provider was paid", "owning_agent": "AGENT_UNIVERSAL", "auto_fixable": False, "data_source_key": "CLAIMS_COB_HISTORY"},
    ]

    # Construction of MERGE statement
    values_list = []
    for item in catalog_data:
        val_str = f"('{item['reject_code']}', '{item['description']}', '{item['owning_agent']}', {str(item['auto_fixable']).upper()}, '{item['data_source_key']}')"
        values_list.append(val_str)
    
    values_joined = ",\n  ".join(values_list)

    merge_query = f"""
    MERGE `{catalog_table_id}` T
    USING (
      SELECT * FROM UNNEST([
        STRUCT<reject_code STRING, description STRING, owning_agent STRING, auto_fixable BOOL, data_source_key STRING>
        {values_joined}
      ])
    ) S
    ON T.reject_code = S.reject_code
    WHEN MATCHED THEN
      UPDATE SET 
        description = S.description, 
        owning_agent = S.owning_agent, 
        auto_fixable = S.auto_fixable, 
        data_source_key = S.data_source_key
    WHEN NOT MATCHED THEN
      INSERT (reject_code, description, owning_agent, auto_fixable, data_source_key)
      VALUES (S.reject_code, S.description, S.owning_agent, S.auto_fixable, S.data_source_key);
    """

    try:
        query_job = client.query(merge_query)
        query_job.result()  # Wait for query to complete
        logger.info("Successfully seeded reference.reject_code_catalog using MERGE.")
        return len(catalog_data)
    except GoogleAPICallError as e:
        logger.error(f"Failed to seed catalog: {e}")
        raise

if __name__ == "__main__":
    create_v4_tables()
    rows = seed_reject_code_catalog()
    print(f"Tables created successfully and catalog seeded with {rows} rows.")
