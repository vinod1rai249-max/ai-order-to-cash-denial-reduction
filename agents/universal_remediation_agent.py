import os
import logging

try:
    from google.cloud import bigquery
except ImportError:  # pragma: no cover - exercised in local/demo environments
    bigquery = None

from governance.governance_logger import log_governance_sink

# Import the handlers
from agents.handlers.fix_invalid_diagnosis import fix_invalid_diagnosis
from agents.handlers.fix_other_insurance_primary import fix_other_insurance_primary
from agents.handlers.fix_invalid_dob_gender import fix_invalid_dob_gender
from agents.handlers.fix_patient_identification import fix_patient_identification
from agents.handlers.fix_incorrect_address import fix_incorrect_address
from agents.handlers.fix_employer_name import fix_employer_name
from agents.handlers.fix_patient_info import fix_patient_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET_PREFIX = os.environ.get("BQ_DATASET", "")

if not GCP_PROJECT_ID:
    logger.warning("GCP_PROJECT_ID not configured; using local reject code catalog fallback.")

def get_table_ref(dataset_name: str, table_name: str) -> str:
    dataset = f"{BQ_DATASET_PREFIX}_{dataset_name}" if BQ_DATASET_PREFIX else dataset_name
    return f"{GCP_PROJECT_ID}.{dataset}.{table_name}"

LOCAL_CATALOG_FALLBACK = {
    "13": {"description": "Partial response", "auto_fixable": False},
    "14": {"description": "Invalid diagnosis", "auto_fixable": True},
    "15": {"description": "Other insurance primary", "auto_fixable": True},
    "19": {"description": "Invalid DOB / gender", "auto_fixable": True},
    "21": {"description": "Cannot identify patient", "auto_fixable": True},
    "30": {"description": "Incorrect address", "auto_fixable": True},
    "32": {"description": "Lab out of network", "auto_fixable": False},
    "33": {"description": "Visit/benefit exceeded", "auto_fixable": False},
    "39": {"description": "Employer name needed", "auto_fixable": True},
    "40": {"description": "Patient info needed", "auto_fixable": True},
    "45": {"description": "Non-covered service", "auto_fixable": False},
    "52": {"description": "Another provider was paid", "auto_fixable": False},
}

HANDLER_REGISTRY = {
    "14": fix_invalid_diagnosis,
    "15": fix_other_insurance_primary,
    "19": fix_invalid_dob_gender,
    "21": fix_patient_identification,
    "30": fix_incorrect_address,
    "39": fix_employer_name,
    "40": fix_patient_info,
}

def load_catalog() -> dict:
    """Loads the reject code catalog from BigQuery reference table with local fallback."""
    if not GCP_PROJECT_ID or bigquery is None:
        logger.warning("BigQuery client unavailable, using local catalog fallback")
        return LOCAL_CATALOG_FALLBACK

    client = bigquery.Client(project=GCP_PROJECT_ID)
    catalog_table_id = get_table_ref("reference", "reject_code_catalog")
    
    query = f"SELECT reject_code, description, auto_fixable FROM `{catalog_table_id}`"
    try:
        logger.info(f"Loading catalog metadata from BigQuery table: {catalog_table_id}...")
        query_job = client.query(query)
        results = query_job.result()
        catalog = {}
        for r in results:
            catalog[r.reject_code] = {
                "description": r.description,
                "auto_fixable": r.auto_fixable
            }
        return catalog
    except Exception as e:
        logger.warning(f"Failed to fetch reject catalog from BigQuery, using local fallback: {e}")
        return LOCAL_CATALOG_FALLBACK

def run_universal_remediation(state: dict) -> dict:
    """
    Dispatcher agent for code-specific remediation.
    Determines whether a code is fixable dynamically and executes the proper handler.
    """
    order = state.get("order", state)
    detected_codes_list = state.get("reject_codes_detected", [])
    
    # Normalize list of codes
    detected_codes = []
    for item in detected_codes_list:
        if isinstance(item, dict):
            detected_codes.append(item.get("reject_code"))
        elif isinstance(item, str):
            detected_codes.append(item)
            
    # Exclude NPI code as it is handled by the dedicated NPI Agent
    detected_codes = [c for c in detected_codes if c != "NPI_MISSING_OR_INVALID"]
    
    if not detected_codes:
        logger.info("No universal remediation codes detected.")
        return state
        
    catalog = load_catalog()
    
    for code in detected_codes:
        catalog_entry = catalog.get(code, LOCAL_CATALOG_FALLBACK.get(code))
        if not catalog_entry:
            order["hitl_required"] = True
            order["hitl_reason"] = f"Detected unknown reject code {code}."
            continue
            
        auto_fixable = catalog_entry.get("auto_fixable", False)
        description = catalog_entry.get("description", "Unknown issue")
        
        # Guardrail: Route to HITL immediately if non-fixable
        if not auto_fixable:
            order["hitl_required"] = True
            order["hitl_reason"] = f"Reject code {code} ({description}) requires human review."
            
            log_governance_sink(
                action="ROUTE_TO_HITL_NONFIXABLE",
                rule_applied=f"code={code}",
                input_payload={"code": code, "description": description},
                output_payload={"hitl_reason": order["hitl_reason"]},
                claim_id=order.get("claim_id") or order.get("order_id"),
                trace_id=order.get("trace_id")
            )
            continue
            
        # Dispatch to registered handler
        handler = HANDLER_REGISTRY.get(code)
        if not handler:
            order["hitl_required"] = True
            order["hitl_reason"] = f"Fixable code {code} does not have a registered handler."
            continue
            
        try:
            # Capture state pre-fix for audit trail
            fields_pre = {
                "npi": order.get("npi"),
                "payer_id": order.get("payer_id"),
                "cpt_code": order.get("cpt_code"),
                "icd10_code": order.get("icd10_code"),
                "dob": order.get("dob"),
                "gender": order.get("gender"),
                "address": order.get("address"),
                "patient_id": order.get("patient_id"),
                "employer_name": order.get("employer_name")
            }
            
            order = handler(order)
            
            # Capture state post-fix
            fields_post = {
                "npi": order.get("npi"),
                "payer_id": order.get("payer_id"),
                "cpt_code": order.get("cpt_code"),
                "icd10_code": order.get("icd10_code"),
                "dob": order.get("dob"),
                "gender": order.get("gender"),
                "address": order.get("address"),
                "patient_id": order.get("patient_id"),
                "employer_name": order.get("employer_name")
            }
            
            if order.get("hitl_required"):
                log_governance_sink(
                    action="UNIVERSAL_REMEDIATION_UNRESOLVED",
                    rule_applied=f"handler_code_{code}",
                    input_payload=fields_pre,
                    output_payload={"hitl_reason": order.get("hitl_reason")},
                    claim_id=order.get("claim_id") or order.get("order_id"),
                    trace_id=order.get("trace_id")
                )
            else:
                log_governance_sink(
                    action="UNIVERSAL_REMEDIATION_FIX",
                    rule_applied=f"handler_code_{code}",
                    input_payload=fields_pre,
                    output_payload={"patched_fields": fields_post, "reject_code": code},
                    claim_id=order.get("claim_id") or order.get("order_id"),
                    trace_id=order.get("trace_id")
                )
        except Exception as e:
            logger.error(f"Error in handler for code {code}: {e}")
            order["hitl_required"] = True
            order["hitl_reason"] = f"Error during auto-remediation of code {code}: {str(e)}"

    if "order" in state:
        state["order"] = order
    return state
