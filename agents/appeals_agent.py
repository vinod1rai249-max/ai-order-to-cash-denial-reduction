import logging
from datetime import datetime, timezone
from governance.governance_logger import log_governance_sink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NON_FIXABLE_CODE_GUIDANCE = {
    "13": {
        "description": "Partial response from payer",
        "next_steps": [
            "Contact payer representative to request complete response",
            "Resubmit claim with additional supporting documentation",
            "File formal appeal if denial is sustained",
        ],
    },
    "32": {
        "description": "Lab service is out-of-network",
        "next_steps": [
            "Verify network status with payer provider directory",
            "Request single-case agreement (SCA) for out-of-network coverage",
            "Re-route to in-network lab if patient consents",
        ],
    },
    "33": {
        "description": "Visit or benefit limit exceeded",
        "next_steps": [
            "Verify benefit accumulator with payer eligibility system",
            "Request medical necessity override with clinical documentation",
            "Advise patient of remaining benefit status",
        ],
    },
    "45": {
        "description": "Non-covered service for this payer",
        "next_steps": [
            "Review payer coverage policy for applicable exceptions",
            "Submit prior authorization with clinical justification",
            "Explore alternative CPT codes that may be covered",
        ],
    },
    "52": {
        "description": "Another provider was already paid for this service",
        "next_steps": [
            "Review claims history for duplicate submissions",
            "Contact original provider to confirm payment status",
            "File coordination of benefits (COB) adjustment if applicable",
        ],
    },
}

DEFAULT_GUIDANCE = {
    "description": "Unresolved claim issue",
    "next_steps": [
        "Review complete claim details and rejection history",
        "Contact payer for clarification on denial reason",
        "Prepare appeal documentation with supporting evidence",
    ],
}


def build_appeal_case(order: dict, reject_codes: list) -> dict:
    """
    Constructs a structured appeal case with reason analysis,
    affected fields, and recommended next steps.
    """
    case = {
        "case_id": f"APPEAL-{order.get('order_id', 'UNKNOWN')}",
        "order_id": order.get("order_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "risk_score": order.get("risk_score"),
        "reject_codes": [],
        "affected_fields": [],
        "recommended_actions": [],
        "priority": "standard",
    }

    monitored_fields = {
        "npi": order.get("npi"),
        "payer_id": order.get("payer_id"),
        "cpt_code": order.get("cpt_code"),
        "icd10_code": order.get("icd10_code"),
        "dob": order.get("dob"),
        "gender": order.get("gender"),
        "address": order.get("address"),
        "patient_id": order.get("patient_id"),
        "employer_name": order.get("employer_name"),
    }

    for field, value in monitored_fields.items():
        if not value or value in ("", "INVALIDNPI", "INVALID_ICD", "XX.999", "UNKNOWN_PATIENT"):
            case["affected_fields"].append(field)

    seen_steps = set()
    for code in reject_codes:
        code_str = code.get("reject_code") if isinstance(code, dict) else str(code)
        guidance = NON_FIXABLE_CODE_GUIDANCE.get(code_str, DEFAULT_GUIDANCE)
        case["reject_codes"].append({
            "code": code_str,
            "description": guidance["description"],
        })
        for step in guidance["next_steps"]:
            if step not in seen_steps:
                case["recommended_actions"].append(step)
                seen_steps.add(step)

    if order.get("hitl_reason"):
        case["hitl_reason"] = order["hitl_reason"]

    risk = float(order.get("risk_score", 0) or 0)
    if risk >= 0.80 or len(reject_codes) >= 3:
        case["priority"] = "high"
    elif risk >= 0.60:
        case["priority"] = "medium"

    return case


def run_appeals_agent(state: dict) -> dict:
    """
    Appeals agent: constructs a structured appeal case with reason analysis,
    affected fields, and recommended next steps, then logs to governance.
    """
    order = state.get("order", state)
    order["status"] = "hitl"

    reject_codes = state.get("reject_codes_detected", [])
    appeal_case = build_appeal_case(order, reject_codes)

    logger.info(
        f"Appeals Agent: Order {order.get('order_id')} routed to HITL. "
        f"Priority: {appeal_case['priority']}. "
        f"Codes: {[c['code'] for c in appeal_case['reject_codes']]}. "
        f"Actions: {len(appeal_case['recommended_actions'])} recommended."
    )

    log_governance_sink(
        action="APPEAL_CASE_CREATED",
        rule_applied=f"priority={appeal_case['priority']}",
        input_payload={
            "order_id": order.get("order_id"),
            "reject_codes": [c["code"] for c in appeal_case["reject_codes"]],
            "affected_fields": appeal_case["affected_fields"],
            "hitl_reason": order.get("hitl_reason"),
        },
        output_payload={
            "case_id": appeal_case["case_id"],
            "priority": appeal_case["priority"],
            "recommended_actions": appeal_case["recommended_actions"],
        },
        claim_id=order.get("claim_id") or order.get("order_id"),
        trace_id=order.get("trace_id"),
    )

    if "order" in state:
        state["order"] = order
    return state
