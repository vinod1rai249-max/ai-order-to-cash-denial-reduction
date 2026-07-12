import os
import time
import json
import logging
from datetime import datetime, timezone
from typing import TypedDict, List, Dict, Any, Union

try:
    from google.cloud import bigquery
except ImportError:  # pragma: no cover - exercised in local/demo environments
    bigquery = None

from langgraph.graph import StateGraph, END

# Import backend modules
from ml.score_risk import score_risk
from agents.reason_detection import detect_reject_codes
from agents.npi_agent import run_npi_agent
from agents.universal_remediation_agent import run_universal_remediation
from agents.billing_agent import run_billing_agent
from agents.appeals_agent import run_appeals_agent
from governance.governance_logger import log_governance_sink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET_PREFIX = os.environ.get("BQ_DATASET", "")
RISK_THRESHOLD_HIGH = float(os.environ.get("RISK_THRESHOLD_HIGH", "0.50"))
MAX_REMEDIATION_ATTEMPTS = int(os.environ.get("MAX_REMEDIATION_ATTEMPTS", "3"))

LOCAL_ORDER_STORE: Dict[str, Dict[str, Any]] = {}


def get_table_ref(dataset_name: str, table_name: str) -> str:
    dataset = f"{BQ_DATASET_PREFIX}_{dataset_name}" if BQ_DATASET_PREFIX else dataset_name
    return f"{GCP_PROJECT_ID}.{dataset}.{table_name}"

# 1. State Definition
class OrderState(TypedDict):
    order: Dict[str, Any]
    risk_score: float
    reject_codes_detected: List[Any]
    remediation_attempts: int
    remediation_history: List[Dict[str, Any]]

# 2. Database Persistence Helper
def save_order_to_db(order: dict, risk_score: float, attempts: int, history: list, status: str, trace_id: str):
    """Saves the current order state and remediation history to silver.orders."""
    order_id = order.get("order_id") or order.get("claim_id")
    if order_id:
        local_order = dict(order)
        local_order.update({
            "risk_score": risk_score,
            "remediation_attempts": attempts,
            "risk_history": list(history or []),
            "status": status,
            "trace_id": trace_id,
        })
        LOCAL_ORDER_STORE[order_id] = local_order

    if not GCP_PROJECT_ID or bigquery is None:
        logger.warning("GCP_PROJECT_ID not configured or BigQuery client unavailable; using local in-memory persistence.")
        return

    try:
        client = bigquery.Client(project=GCP_PROJECT_ID)
        table_id = get_table_ref("silver", "orders")
        history_json = json.dumps(history)

        merge_query = f"""
        MERGE `{table_id}` T
        USING (
          SELECT
            @order_id AS order_id,
            @claim_id AS claim_id,
            @patient_name AS patient_name,
            @npi AS npi,
            @payer_id AS payer_id,
            @cpt_code AS cpt_code,
            @icd10_code AS icd10_code,
            @dob AS dob,
            @gender AS gender,
            @address AS address,
            @patient_id AS patient_id,
            @employer_name AS employer_name,
            @provider_first_name AS provider_first_name,
            @provider_last_name AS provider_last_name,
            @provider_state AS provider_state,
            @provider_taxonomy AS provider_taxonomy,
            @risk_score AS risk_score,
            SAFE.PARSE_JSON(@risk_history) AS risk_history,
            @remediation_attempts AS remediation_attempts,
            @status AS status,
            @trace_id AS trace_id
        ) S
        ON T.order_id = S.order_id
        WHEN MATCHED THEN
          UPDATE SET
            claim_id = S.claim_id,
            patient_name = S.patient_name,
            npi = S.npi,
            payer_id = S.payer_id,
            cpt_code = S.cpt_code,
            icd10_code = S.icd10_code,
            dob = S.dob,
            gender = S.gender,
            address = S.address,
            patient_id = S.patient_id,
            employer_name = S.employer_name,
            provider_first_name = S.provider_first_name,
            provider_last_name = S.provider_last_name,
            provider_state = S.provider_state,
            provider_taxonomy = S.provider_taxonomy,
            risk_score = S.risk_score,
            risk_history = S.risk_history,
            remediation_attempts = S.remediation_attempts,
            status = S.status,
            trace_id = S.trace_id
        WHEN NOT MATCHED THEN
          INSERT (order_id, claim_id, patient_name, npi, payer_id, cpt_code, icd10_code, dob, gender, address, patient_id, employer_name, provider_first_name, provider_last_name, provider_state, provider_taxonomy, risk_score, risk_history, remediation_attempts, status, trace_id)
          VALUES (S.order_id, S.claim_id, S.patient_name, S.npi, S.payer_id, S.cpt_code, S.icd10_code, S.dob, S.gender, S.address, S.patient_id, S.employer_name, S.provider_first_name, S.provider_last_name, S.provider_state, S.provider_taxonomy, S.risk_score, S.risk_history, S.remediation_attempts, S.status, S.trace_id)
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("order_id", "STRING", order.get("order_id") or order.get("claim_id")),
                bigquery.ScalarQueryParameter("claim_id", "STRING", order.get("claim_id")),
                bigquery.ScalarQueryParameter("patient_name", "STRING", order.get("patient_name")),
                bigquery.ScalarQueryParameter("npi", "STRING", order.get("npi")),
                bigquery.ScalarQueryParameter("payer_id", "STRING", order.get("payer_id")),
                bigquery.ScalarQueryParameter("cpt_code", "STRING", order.get("cpt_code")),
                bigquery.ScalarQueryParameter("icd10_code", "STRING", order.get("icd10_code")),
                bigquery.ScalarQueryParameter("dob", "STRING", order.get("dob")),
                bigquery.ScalarQueryParameter("gender", "STRING", order.get("gender")),
                bigquery.ScalarQueryParameter("address", "STRING", order.get("address")),
                bigquery.ScalarQueryParameter("patient_id", "STRING", order.get("patient_id")),
                bigquery.ScalarQueryParameter("employer_name", "STRING", order.get("employer_name")),
                bigquery.ScalarQueryParameter("provider_first_name", "STRING", order.get("provider_first_name")),
                bigquery.ScalarQueryParameter("provider_last_name", "STRING", order.get("provider_last_name")),
                bigquery.ScalarQueryParameter("provider_state", "STRING", order.get("provider_state")),
                bigquery.ScalarQueryParameter("provider_taxonomy", "STRING", order.get("provider_taxonomy")),
                bigquery.ScalarQueryParameter("risk_score", "FLOAT64", risk_score),
                bigquery.ScalarQueryParameter("risk_history", "STRING", history_json),
                bigquery.ScalarQueryParameter("remediation_attempts", "INT64", attempts),
                bigquery.ScalarQueryParameter("status", "STRING", status),
                bigquery.ScalarQueryParameter("trace_id", "STRING", trace_id),
            ]
        )

        query_job = client.query(merge_query, job_config=job_config)
        query_job.result()
        logger.info(f"Persisted order {order.get('order_id')} in silver.orders (status: {status}).")
    except Exception as e:
        logger.error(f"Failed to persist order to silver.orders: {e}")

def get_order_from_db(order_id: str) -> dict | None:
    """Helper to fetch a single order from BigQuery or the local fallback store."""
    if order_id in LOCAL_ORDER_STORE:
        return dict(LOCAL_ORDER_STORE[order_id])

    if not GCP_PROJECT_ID or bigquery is None:
        return None

    try:
        client = bigquery.Client(project=GCP_PROJECT_ID)
        table_id = get_table_ref("silver", "orders")

        query = f"SELECT * FROM `{table_id}` WHERE order_id = @order_id LIMIT 1"
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("order_id", "STRING", order_id)]
        )

        results = list(client.query(query, job_config=job_config).result())
        if results:
            row = results[0]
            order = dict(row.items())

            if order.get("risk_history"):
                if isinstance(order["risk_history"], str):
                    order["risk_history"] = json.loads(order["risk_history"])
            else:
                order["risk_history"] = []
            return order
    except Exception as e:
        logger.error(f"Failed to fetch order {order_id} from BigQuery: {e}")
    return None

# 3. Graph Nodes
def risk_scoring_node(state: OrderState) -> Dict[str, Any]:
    """Node: Scores order risk via BQML model."""
    order = state.get("order")
    # Generate trace ID if not present
    if not order.get("trace_id"):
        order["trace_id"] = f"TRC-ORD-{order.get('order_id') or order.get('claim_id')}"
        
    score = score_risk(order)
    codes = detect_reject_codes(order)
    
    attempts = state.get("remediation_attempts", 0)
    history = state.get("remediation_history", [])
    
    return {
        "order": order,
        "risk_score": score,
        "reject_codes_detected": codes,
        "remediation_attempts": attempts,
        "remediation_history": history
    }

def reason_detection_node(state: OrderState) -> Dict[str, Any]:
    """Node: Deterministic code error checks."""
    order = state.get("order")
    codes = detect_reject_codes(order)
    return {
        "reject_codes_detected": codes
    }

def npi_agent_node(state: OrderState) -> Dict[str, Any]:
    """Node: NPI Registry repair."""
    logger.info("Routing to Agent 1: NPI Remediation Agent")
    updated_state = run_npi_agent(dict(state))
    return {
        "order": updated_state.get("order")
    }

def universal_remediation_agent_node(state: OrderState) -> Dict[str, Any]:
    """Node: Universal repair routing."""
    logger.info("Routing to Agent 2: Universal Remediation Agent")
    updated_state = run_universal_remediation(dict(state))
    return {
        "order": updated_state.get("order")
    }

def rescore_node(state: OrderState) -> Dict[str, Any]:
    """Node: Rescores risk after remediation and updates audit trail."""
    order = state.get("order")
    attempts = state.get("remediation_attempts", 0) + 1
    
    # Calculate new risk score
    new_score = score_risk(order)
    
    # Detect patched fields in this step by comparing against database state
    patch_descriptions = []
    try:
        prev_order = get_order_from_db(order.get("order_id"))
        if prev_order:
            monitored_keys = {
                "npi": "NPI Number",
                "payer_id": "Payer ID",
                "cpt_code": "CPT Code",
                "icd10_code": "ICD-10 Code",
                "dob": "Date of Birth",
                "gender": "Gender",
                "address": "Patient Address",
                "patient_name": "Patient Name",
                "patient_id": "Patient ID",
                "employer_name": "Employer Name"
            }
            for key, label in monitored_keys.items():
                old_val = prev_order.get(key)
                new_val = order.get(key)
                if old_val != new_val:
                    source = None
                    if isinstance(order.get("_sources"), dict):
                        source = order["_sources"].get(key)
                    if not source:
                        fallback_sources = {
                            "npi": "NPPES Registry",
                            "payer_id": "coordination of benefits lookup",
                            "cpt_code": "clinical crosswalk",
                            "icd10_code": "clinical crosswalk",
                            "dob": "demographic registry",
                            "gender": "demographic registry",
                            "address": "USPS Address Validation Service",
                            "patient_name": "patient master registry",
                            "patient_id": "Master Patient Index (MPI) search",
                            "employer_name": "HR / employer master database"
                        }
                        source = fallback_sources.get(key)
                    source_str = f" from {source}" if source else ""
                    
                    if not old_val or str(old_val).strip() in ("", "None", "NULL", "INVALIDNPI", "INVALID_ICD", "UNKNOWN_PATIENT", "XX.999"):
                        patch_descriptions.append(f"{label} restored/corrected to '{new_val}'{source_str}")
                    else:
                        patch_descriptions.append(f"{label} corrected from '{old_val}' to '{new_val}'{source_str}")
    except Exception as e:
        logger.warning(f"Could not compute patch diff for history log: {e}")
    
    status = "remediating"
    if order.get("hitl_required"):
        status = "hitl"
    elif new_score < RISK_THRESHOLD_HIGH:
        status = "clean"
    elif attempts >= MAX_REMEDIATION_ATTEMPTS:
        status = "hitl"

    # Record history log
    history_entry = {
        "attempt": attempts,
        "risk_score": new_score,
        "reject_codes_detected": state.get("reject_codes_detected", []),
        "patches": patch_descriptions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hitl_required": bool(order.get("hitl_required", False)),
        "status": status
    }
    
    history = list(state.get("remediation_history", []))
    history.append(history_entry)
        
    save_order_to_db(
        order=order,
        risk_score=new_score,
        attempts=attempts,
        history=history,
        status=status,
        trace_id=order.get("trace_id")
    )
    
    # Log RESCORED action to governance sink
    log_governance_sink(
        action="RISK_RESCORED",
        rule_applied=f"attempt={attempts}",
        input_payload={"order_id": order.get("order_id"), "attempt": attempts},
        output_payload={"new_risk_score": new_score, "status": status},
        claim_id=order.get("claim_id") or order.get("order_id"),
        trace_id=order.get("trace_id")
    )
    
    return {
        "order": order,
        "risk_score": new_score,
        "remediation_attempts": attempts,
        "remediation_history": history
    }

# 4. Conditional Edges
def route_after_scoring(state: OrderState) -> str:
    """Routes based on initial risk scoring."""
    score = state.get("risk_score", 0.0)
    codes = state.get("reject_codes_detected", [])
    # Route to billing only if score is low AND no deterministic defects are present
    if score < RISK_THRESHOLD_HIGH and not codes:
        return "billing_agent"
    return "reason_detection_node"

def route_after_detection(state: OrderState) -> str:
    """Routes based on detected codes."""
    order = state.get("order")
    
    # Route straight to HITL if marked by previous validations
    if order.get("hitl_required"):
        return "appeals_agent"
        
    detected = state.get("reject_codes_detected", [])
    codes = [c.get("reject_code") if isinstance(c, dict) else c for c in detected]
    
    if not codes:
        # High risk, but no deterministic error patterns found -> HITL
        return "appeals_agent"
        
    if "NPI_MISSING_OR_INVALID" in codes:
        return "npi_agent"
        
    return "universal_remediation_agent"

def route_after_rescoring(state: OrderState) -> str:
    """Routes after rescoring verification."""
    order = state.get("order")
    score = state.get("risk_score", 0.0)
    attempts = state.get("remediation_attempts", 0)
    
    if score < RISK_THRESHOLD_HIGH and not order.get("hitl_required"):
        return "billing_agent"
        
    if attempts >= MAX_REMEDIATION_ATTEMPTS or order.get("hitl_required"):
        return "appeals_agent"
        
    # Loops back to reason detection for subsequent checks
    return "reason_detection_node"

# 5. Build Graph Workflow
workflow = StateGraph(OrderState)

# Register Nodes
workflow.add_node("risk_scoring_node", risk_scoring_node)
workflow.add_node("reason_detection_node", reason_detection_node)
workflow.add_node("npi_agent", npi_agent_node)
workflow.add_node("universal_remediation_agent", universal_remediation_agent_node)
workflow.add_node("rescore_node", rescore_node)
workflow.add_node("billing_agent", run_billing_agent)
workflow.add_node("appeals_agent", run_appeals_agent)

# Set Entry Point
workflow.set_entry_point("risk_scoring_node")

# Wire Conditional Edges
workflow.add_conditional_edges(
    "risk_scoring_node",
    route_after_scoring,
    {
        "billing_agent": "billing_agent",
        "reason_detection_node": "reason_detection_node"
    }
)

workflow.add_conditional_edges(
    "reason_detection_node",
    route_after_detection,
    {
        "npi_agent": "npi_agent",
        "universal_remediation_agent": "universal_remediation_agent",
        "appeals_agent": "appeals_agent"
    }
)

# Nodes transition to rescore node
workflow.add_edge("npi_agent", "rescore_node")
workflow.add_edge("universal_remediation_agent", "rescore_node")

workflow.add_conditional_edges(
    "rescore_node",
    route_after_rescoring,
    {
        "billing_agent": "billing_agent",
        "appeals_agent": "appeals_agent",
        "reason_detection_node": "reason_detection_node"
    }
)

workflow.add_edge("billing_agent", END)
workflow.add_edge("appeals_agent", END)

# Compile Graph
app_graph = workflow.compile()
