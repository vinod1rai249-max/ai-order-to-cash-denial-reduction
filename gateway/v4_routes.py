import os
import json
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status

try:
    from google.cloud import bigquery
except ImportError:  # pragma: no cover - exercised in local/demo environments
    bigquery = None

# Import security and graph Orchestrator
from gateway.auth_middleware import get_current_user, require_role
from auth.roles import ROLE_BILLING_OPS, ROLE_AUDITOR, ROLE_EXECUTIVE, ROLE_ADMIN
from orchestrator.graph_v4 import app_graph, get_table_ref, save_order_to_db, get_order_from_db as graph_get_order_from_db
from ml.score_risk import score_risk
from agents.reason_detection import detect_reject_codes
from governance.governance_logger import log_governance_sink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")

def get_order_from_db(order_id: str) -> dict | None:
    """Helper to fetch a single order from the shared local or BigQuery-backed store."""
    return graph_get_order_from_db(order_id)

# Endpoints

@router.post(
    "/orders",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role([ROLE_BILLING_OPS, ROLE_AUDITOR, ROLE_ADMIN]))]
)
def create_order(payload: Dict[str, Any]):
    """
    POST /api/v1/orders
    Ingests a raw billing order, evaluates initial pre-submission risk and runs reason detection.
    """
    order = dict(payload)
    order_id = order.get("order_id") or order.get("claim_id")
    if not order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing order_id or claim_id in request payload."
        )

    trace_id = order.get("trace_id") or f"TRC-ORD-{order_id}"
    order["trace_id"] = trace_id

    try:
        # Execute deterministic scoring and reason detection
        risk_score = score_risk(order)
        codes = detect_reject_codes(order)
    except Exception as e:
        logger.error(f"Scoring/detection failed for order {order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk evaluation failed: {str(e)}"
        )

    # Format detected codes as list of strings for BQ compatibility
    detected_codes = [c.get("reject_code") if isinstance(c, dict) else c for c in codes]

    status_str = "scored"
    if risk_score < 0.50 and not detected_codes:
        status_str = "clean"

    # Save intake record
    save_order_to_db(
        order=order,
        risk_score=risk_score,
        attempts=0,
        history=[],
        status=status_str,
        trace_id=trace_id
    )

    return {
        "order_id": order_id,
        "risk_score": risk_score,
        "reject_codes_detected": codes,
        "status": status_str,
        "trace_id": trace_id
    }

@router.post(
    "/orders/{order_id}/remediate",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role([ROLE_BILLING_OPS, ROLE_AUDITOR, ROLE_ADMIN]))]
)
def remediate_order(order_id: str):
    """
    POST /api/v1/orders/{order_id}/remediate
    Executes the remediation state machine loop for a previously ingested order.
    """
    order = get_order_from_db(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found."
        )
        
    # Store initial values for endpoint return contract comparison
    risk_score_before = float(order.get("risk_score", 0.0))
    npi_before = order.get("npi")
    
    # Initialize graph state
    initial_state = {
        "order": order,
        "risk_score": risk_score_before,
        "reject_codes_detected": [],
        "remediation_attempts": int(order.get("remediation_attempts") or 0),
        "remediation_history": order.get("risk_history") or []
    }
    
    try:
        # Execute LangGraph loop
        logger.info(f"Invoking remediation graph for order {order_id}...")
        result = app_graph.invoke(initial_state)
    except Exception as e:
        logger.error(f"LangGraph execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing remediation loop: {str(e)}"
        )
        
    final_order = result.get("order", {})
    risk_score_after = float(result.get("risk_score", 0.0))
    remediation_attempts = int(result.get("remediation_attempts", 0))
    hitl_required = bool(final_order.get("hitl_required", False))
    
    # Detect patched fields
    fields_patched = []
    monitored_keys = ["npi", "payer_id", "cpt_code", "icd10_code", "dob", "gender", "address", "patient_id", "employer_name"]
    for key in monitored_keys:
        if order.get(key) != final_order.get(key):
            fields_patched.append(key)
            
    # Determine agent(s) invoked
    agent_invoked = "none"
    npi_changed = (npi_before != final_order.get("npi"))
    others_changed = any(k != "npi" for k in fields_patched)
    
    if npi_changed and others_changed:
        agent_invoked = "both"
    elif npi_changed:
        agent_invoked = "npi_agent"
    elif others_changed:
        agent_invoked = "universal_remediation_agent"
        
    return {
        "order_id": order_id,
        "agent_invoked": agent_invoked,
        "fields_patched": fields_patched,
        "risk_score_before": round(risk_score_before, 2),
        "risk_score_after": round(risk_score_after, 2),
        "remediation_attempts": remediation_attempts,
        "hitl_required": hitl_required
    }

@router.get(
    "/orders/{order_id}",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role([ROLE_BILLING_OPS, ROLE_AUDITOR, ROLE_ADMIN, ROLE_EXECUTIVE]))]
)
def get_order(order_id: str):
    """
    GET /api/v1/orders/{order_id}
    Retrieves the current state of a single order.
    """
    order = get_order_from_db(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found."
        )
    return order

@router.get(
    "/orders/{order_id}/risk-history",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(require_role([ROLE_BILLING_OPS, ROLE_AUDITOR, ROLE_EXECUTIVE, ROLE_ADMIN]))]
)
def get_risk_history(order_id: str):
    """
    GET /api/v1/orders/{order_id}/risk-history
    Returns the step-by-step audit remediation timeline.
    """
    order = get_order_from_db(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found."
        )
    return order.get("risk_history") or []

@router.get(
    "/reference/reject-codes",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(require_role([ROLE_BILLING_OPS, ROLE_AUDITOR, ROLE_EXECUTIVE, ROLE_ADMIN]))]
)
def get_reject_codes():
    """
    GET /api/v1/reference/reject-codes
    Returns the seeded reference reject code catalog.
    """
    fallback_codes = [
        {"reject_code": "13", "description": "Partial response", "owning_agent": "universal_remediation_agent", "auto_fixable": False, "data_source_key": "payer_response_partial"},
        {"reject_code": "14", "description": "Invalid diagnosis", "owning_agent": "universal_remediation_agent", "auto_fixable": True, "data_source_key": "icd10_lookup"},
        {"reject_code": "15", "description": "Other insurance primary", "owning_agent": "universal_remediation_agent", "auto_fixable": True, "data_source_key": "cob_lookup"},
        {"reject_code": "19", "description": "Invalid DOB / gender", "owning_agent": "universal_remediation_agent", "auto_fixable": True, "data_source_key": "demographics_lookup"},
        {"reject_code": "21", "description": "Cannot identify patient", "owning_agent": "universal_remediation_agent", "auto_fixable": True, "data_source_key": "patient_id_lookup"},
        {"reject_code": "30", "description": "Incorrect address", "owning_agent": "universal_remediation_agent", "auto_fixable": True, "data_source_key": "address_lookup"},
        {"reject_code": "32", "description": "Lab out of network", "owning_agent": "universal_remediation_agent", "auto_fixable": False, "data_source_key": "network_status_lookup"},
        {"reject_code": "33", "description": "Visit/benefit exceeded", "owning_agent": "universal_remediation_agent", "auto_fixable": False, "data_source_key": "visit_number_lookup"},
        {"reject_code": "39", "description": "Employer name needed", "owning_agent": "universal_remediation_agent", "auto_fixable": True, "data_source_key": "employer_name_lookup"},
        {"reject_code": "40", "description": "Patient info needed", "owning_agent": "universal_remediation_agent", "auto_fixable": True, "data_source_key": "patient_name_lookup"},
        {"reject_code": "45", "description": "Non-covered service", "owning_agent": "universal_remediation_agent", "auto_fixable": False, "data_source_key": "non_covered_lookup"},
        {"reject_code": "52", "description": "Another provider was paid", "owning_agent": "universal_remediation_agent", "auto_fixable": False, "data_source_key": "another_provider_paid_lookup"},
    ]
    if not GCP_PROJECT_ID or bigquery is None:
        return fallback_codes

    try:
        client = bigquery.Client(project=GCP_PROJECT_ID)
        table_id = get_table_ref("reference", "reject_code_catalog")
        query = f"SELECT reject_code, description, owning_agent, auto_fixable, data_source_key FROM `{table_id}`"
        results = list(client.query(query).result())
        return [dict(row.items()) for row in results]
    except Exception as e:
        logger.warning(f"Failed to query reject code catalog from BigQuery, using fallback: {e}")
        return fallback_codes


@router.post(
    "/auth/session",
    response_model=Dict[str, Any]
)
def auth_session(user: dict = Depends(get_current_user)):
    """
    POST /api/v1/auth/session
    Verifies user Firebase ID token and returns authenticated role + display name.
    """
    return {
        "uid": user.get("uid"),
        "email": user.get("email"),
        "role": user.get("role"),
        "display_name": user.get("display_name")
    }


@router.get(
    "/orders",
    response_model=List[Dict[str, Any]],
    dependencies=[Depends(require_role([ROLE_BILLING_OPS, ROLE_AUDITOR, ROLE_ADMIN, ROLE_EXECUTIVE]))]
)
def list_orders(status: str = None):
    """
    GET /api/v1/orders
    Lists orders with optional status filtering.
    """
    status_filter = status
    orders = []

    if not GCP_PROJECT_ID or bigquery is None:
        from orchestrator.graph_v4 import LOCAL_ORDER_STORE
        orders = list(LOCAL_ORDER_STORE.values())
        if status_filter:
            orders = [o for o in orders if o.get("status") == status_filter]
    else:
        try:
            client = bigquery.Client(project=GCP_PROJECT_ID)
            table_id = get_table_ref("silver", "orders")

            query = f"SELECT * FROM `{table_id}`"
            if status_filter:
                query += " WHERE status = @status"

            query_params = [bigquery.ScalarQueryParameter("status", "STRING", status_filter)] if status_filter else []
            job_config = bigquery.QueryJobConfig(query_parameters=query_params)

            results = list(client.query(query, job_config=job_config).result())
            orders = [dict(row.items()) for row in results]
        except Exception as e:
            logger.warning(f"Failed to query orders from BigQuery, falling back to local store: {e}")
            from orchestrator.graph_v4 import LOCAL_ORDER_STORE
            orders = list(LOCAL_ORDER_STORE.values())
            if status_filter:
                orders = [o for o in orders if o.get("status") == status_filter]

    # Keep only orders related to load test scenarios (containing 'TST-' or 'DEMO-')
    orders = [o for o in orders if "TST-" in (o.get("order_id") or "") or "DEMO-" in (o.get("order_id") or "")]

    # If filtering for the HITL queue, only show orders which cannot be fixable
    if status_filter == "hitl":
        non_fixable_codes = {"13", "32", "33", "45", "52"}
        filtered_orders = []
        for order in orders:
            is_oon = order.get("network_status") == "OON" or order.get("cpt_code") == "81408"
            is_partial = not order.get("is_presubmission", True) and order.get("payer_response_partial") is True
            is_exceeded = False
            try:
                if int(order.get("visit_number") or 1) > 10:
                    is_exceeded = True
            except:
                pass
            is_noncovered = order.get("cpt_code") == "81479" and order.get("payer_id") in ["PAYER_E", "Medicare"]
            is_another_paid = order.get("another_provider_paid") is True

            if is_oon or is_partial or is_exceeded or is_noncovered or is_another_paid:
                filtered_orders.append(order)
                continue

            # Check risk history for non-fixable codes
            history = order.get("risk_history") or []
            if isinstance(history, str):
                try:
                    history = json.loads(history)
                except:
                    history = []

            has_historical_non_fixable = False
            for entry in history:
                codes_detected = entry.get("reject_codes_detected") or []
                for c in codes_detected:
                    code_str = c.get("reject_code") if isinstance(c, dict) else str(c)
                    if code_str in non_fixable_codes:
                        has_historical_non_fixable = True
                        break
                if has_historical_non_fixable:
                    break

            if has_historical_non_fixable:
                filtered_orders.append(order)
        return filtered_orders[:2]

    # Limit clean and hitl messages to 2 max each for the general list
    clean_orders = []
    hitl_orders = []
    other_orders = []
    for o in orders:
        st = o.get("status")
        if st == "clean":
            if len(clean_orders) < 2:
                clean_orders.append(o)
        elif st in ["hitl", "escalated"]:
            if len(hitl_orders) < 2:
                hitl_orders.append(o)
        else:
            other_orders.append(o)
    return clean_orders + hitl_orders + other_orders


@router.post(
    "/orders/{order_id}/resolve",
    response_model=Dict[str, Any],
    dependencies=[Depends(require_role([ROLE_AUDITOR, ROLE_ADMIN]))]
)
def resolve_hitl_order(order_id: str, payload: Dict[str, Any]):
    """
    POST /api/v1/orders/{order_id}/resolve
    Resolves a HITL-queued order via human review decision.
    Actions: approve (accept current state), override (force-clear), escalate (flag for senior review).
    """
    order = get_order_from_db(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found."
        )

    action = payload.get("action", "").lower()
    reviewer_notes = payload.get("notes", "")

    if action not in ("approve", "override", "escalate"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action '{action}'. Must be 'approve', 'override', or 'escalate'."
        )

    if action == "approve":
        new_status = "clean"
        resolution = "HITL reviewer approved the current remediated state."
    elif action == "override":
        new_status = "clean"
        resolution = "HITL reviewer overrode the rejection and force-cleared the claim."
    else:
        new_status = "escalated"
        resolution = "HITL reviewer escalated to senior review / appeals committee."

    history = order.get("risk_history", [])
    if isinstance(history, str):
        import json as _json
        history = _json.loads(history)

    from datetime import datetime, timezone
    history.append({
        "attempt": "HITL_REVIEW",
        "action": action,
        "resolution": resolution,
        "reviewer_notes": reviewer_notes,
        "risk_score": float(order.get("risk_score", 0.0)),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    save_order_to_db(
        order=order,
        risk_score=float(order.get("risk_score", 0.0)),
        attempts=int(order.get("remediation_attempts", 0)),
        history=history,
        status=new_status,
        trace_id=order.get("trace_id", "")
    )

    log_governance_sink(
        action=f"HITL_RESOLVED_{action.upper()}",
        rule_applied=f"hitl_action={action}",
        input_payload={
            "order_id": order_id,
            "previous_status": order.get("status"),
            "reviewer_notes": reviewer_notes,
        },
        output_payload={
            "new_status": new_status,
            "resolution": resolution,
        },
        claim_id=order.get("claim_id") or order_id,
        trace_id=order.get("trace_id")
    )

    return {
        "order_id": order_id,
        "action": action,
        "new_status": new_status,
        "resolution": resolution
    }
