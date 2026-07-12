import os
import json
import time
import logging
from datetime import datetime, timezone

try:
    from google.cloud import bigquery
    from google.api_core.exceptions import GoogleAPICallError
except ImportError:  # pragma: no cover - exercised in local/demo environments
    bigquery = None
    GoogleAPICallError = Exception

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET_PREFIX = os.environ.get("BQ_DATASET", "")


def get_table_ref(dataset_name: str, table_name: str) -> str:
    dataset = f"{BQ_DATASET_PREFIX}_{dataset_name}" if BQ_DATASET_PREFIX else dataset_name
    return f"{GCP_PROJECT_ID}.{dataset}.{table_name}"

def init_governance_sink() -> None:
    """Idempotently creates the governance_sink table if not exists."""
    if not GCP_PROJECT_ID or bigquery is None:
        logger.warning("GCP_PROJECT_ID not configured or BigQuery client unavailable; governance sink logging disabled.")
        return

    client = bigquery.Client(project=GCP_PROJECT_ID)
    dataset_ref = f"{GCP_PROJECT_ID}.{BQ_DATASET_PREFIX}_governance" if BQ_DATASET_PREFIX else f"{GCP_PROJECT_ID}.governance"
    
    # Create governance dataset if not exists
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = "US"
    try:
        client.create_dataset(dataset, exists_ok=True)
    except GoogleAPICallError as e:
        logger.error(f"Failed to create dataset {dataset_ref}: {e}")
        raise

    table_id = get_table_ref("governance", "governance_sink")
    schema = [
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("action", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("rule_applied", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("input_payload", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("output_payload", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("model_version", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("duration_ms", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("claim_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("trace_id", "STRING", mode="NULLABLE"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    try:
        client.create_table(table, exists_ok=True)
        logger.info(f"Governance table {table_id} verified/created.")
    except GoogleAPICallError as e:
        logger.error(f"Failed to create table {table_id}: {e}")
        raise

def log_governance_sink(
    action: str,
    rule_applied: str = None,
    input_payload: dict = None,
    output_payload: dict = None,
    model_version: str = None,
    duration_ms: float = 0.0,
    claim_id: str = None,
    trace_id: str = None
) -> None:
    """
    Logs an event to governance_sink via BigQuery streaming insert.
    Does not raise exceptions on logging failures (non-blocking).
    """
    if not GCP_PROJECT_ID or bigquery is None:
        return

    client = bigquery.Client(project=GCP_PROJECT_ID)
    table_id = get_table_ref("governance", "governance_sink")
    
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "rule_applied": rule_applied,
        "input_payload": json.dumps(input_payload) if input_payload is not None else None,
        "output_payload": json.dumps(output_payload) if output_payload is not None else None,
        "model_version": model_version,
        "duration_ms": float(duration_ms),
        "claim_id": claim_id,
        "trace_id": trace_id
    }
    
    try:
        errors = client.insert_rows_json(table_id, [row])
        if errors:
            logger.error(f"Failed to insert row to governance_sink: {errors}")
        else:
            logger.debug(f"Governance logged: {action}")
    except Exception as e:
        logger.error(f"Failed to write to governance_sink: {e}")
