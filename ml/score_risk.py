import os
import time
import logging
from functools import lru_cache

try:
    from google.cloud import bigquery
except ImportError:  # pragma: no cover - exercised in local/demo environments
    bigquery = None

from governance.governance_logger import log_governance_sink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET_PREFIX = os.environ.get("BQ_DATASET", "")


def _get_bigquery_client():
    if not GCP_PROJECT_ID or bigquery is None:
        raise RuntimeError("BigQuery client is unavailable; using rule-based fallback")
    return bigquery.Client(project=GCP_PROJECT_ID)

FALLBACK_RULES = {
    "81479": 0.82,
    "81408": 0.82,
    "87798": 0.82
}
DEFAULT_RISK = 0.25

def get_table_ref(dataset_name: str, table_name: str) -> str:
    dataset = f"{BQ_DATASET_PREFIX}_{dataset_name}" if BQ_DATASET_PREFIX else dataset_name
    return f"{GCP_PROJECT_ID}.{dataset}.{table_name}"

@lru_cache(maxsize=1024)
def _get_cached_bq_score(
    payer_id: str, 
    cpt_code: str, 
    icd10_code: str, 
    prior_auth: bool, 
    timely_filing: int, 
    denial_rate: float
) -> tuple[float, str, str]:
    """
    Internal helper to call BigQuery ML.PREDICT. Cached using lru_cache.
    Returns (score, which_path, model_version)
    """
    client = _get_bigquery_client()
    model_ref = get_table_ref("ml", "risk_model")
    
    # Retrieve model version
    try:
        model = client.get_model(model_ref)
        model_version = model.created.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception as e:
        logger.warning(f"Could not retrieve model metadata for versioning: {e}")
        model_version = "unknown_model_version"
        
    query = f"""
    SELECT p.prob 
    FROM ML.PREDICT(MODEL `{model_ref}`, (
      SELECT 
        @payer_id AS payer_id, 
        @cpt_code AS cpt_code, 
        @icd10_code AS icd10_code, 
        @prior_auth AS prior_auth_on_file, 
        @timely_filing AS timely_filing_days_remaining,
        @denial_rate AS historical_payer_denial_rate_for_cpt
    )), UNNEST(predicted_label_denied_probs) p 
    WHERE p.label = TRUE
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("payer_id", "STRING", payer_id),
            bigquery.ScalarQueryParameter("cpt_code", "STRING", cpt_code),
            bigquery.ScalarQueryParameter("icd10_code", "STRING", icd10_code),
            bigquery.ScalarQueryParameter("prior_auth", "BOOL", prior_auth),
            bigquery.ScalarQueryParameter("timely_filing", "INT64", timely_filing),
            bigquery.ScalarQueryParameter("denial_rate", "FLOAT64", denial_rate),
        ]
    )
    
    query_job = client.query(query, job_config=job_config)
    results = list(query_job.result())
    
    if len(results) > 0:
        score = float(results[0].prob)
        return score, "bqml", model_version
    else:
        raise ValueError("ML.PREDICT returned empty results.")

def score_risk(order: dict) -> float:
    """
    Scores the pre-submission denial risk of an order.
    Uses BQML log-reg prediction, caching identical requests, and falling back
    to rule-based scoring if BigQuery fails.
    """
    start_time = time.time()
    
    # Extraction and default formatting for caching
    payer_id = str(order.get("payer_id") or "")
    cpt_code = str(order.get("cpt_code") or "")
    icd10_code = str(order.get("icd10_code") or "")
    prior_auth = bool(order.get("prior_auth_on_file") or False)
    
    # Default timely filing to 90 days if not present
    val_tf = order.get("timely_filing_days_remaining")
    if val_tf is None:
        timely_filing = 90
    else:
        try:
            timely_filing = int(val_tf)
        except (ValueError, TypeError):
            timely_filing = 90
        
    val_dr = order.get("historical_payer_denial_rate_for_cpt")
    if val_dr is None:
        denial_rate = 0.0
    else:
        try:
            denial_rate = float(val_dr)
        except (ValueError, TypeError):
            denial_rate = 0.0

    which_path = "bqml"
    model_version = None
    score = 0.0
    
    from agents.reason_detection import detect_reject_codes
    remaining_codes = detect_reject_codes(order)
    
    if not remaining_codes:
        score = 0.05
        which_path = "clean_override"
        model_version = "override_v1"
    else:
        try:
            score, which_path, model_version = _get_cached_bq_score(
                payer_id, cpt_code, icd10_code, prior_auth, timely_filing, denial_rate
            )
        except Exception as e:
            logger.warning(f"BQML scoring failed, falling back to rule-based: {e}")
            which_path = "rules_fallback"
            model_version = "rules_fallback_v1"
            
            # Apply rule fallback
            score = FALLBACK_RULES.get(cpt_code, DEFAULT_RISK)

    duration_ms = (time.time() - start_time) * 1000.0
    
    # Log to governance sink
    log_governance_sink(
        action="RISK_SCORED",
        rule_applied=f"path={which_path}",
        input_payload={
            "payer_id": payer_id,
            "cpt_code": cpt_code,
            "icd10_code": icd10_code,
            "prior_auth_on_file": prior_auth,
            "timely_filing_days_remaining": timely_filing,
            "historical_payer_denial_rate_for_cpt": denial_rate
        },
        output_payload={"risk_score": score},
        model_version=model_version,
        duration_ms=duration_ms,
        claim_id=order.get("claim_id") or order.get("order_id"),
        trace_id=order.get("trace_id")
    )
    
    return round(score, 4)
