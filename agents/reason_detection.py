import os
import logging
import time
from data.config import ICD10_LOOKUP_TABLE, PAYER_CONFIG
from governance.governance_logger import log_governance_sink

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_valid_npi_format(npi_str: str) -> bool:
    """
    Validates a 10-digit NPI using the standard Luhn algorithm with US national ID prefix (80840).
    """
    if not npi_str:
        return False
    npi_str = str(npi_str).strip()
    if len(npi_str) != 10 or not npi_str.isdigit():
        return False
        
    # National identifier prefix for US health providers is 80840
    full_str = "80840" + npi_str[:-1]
    check_digit = int(npi_str[-1])
    
    total_sum = 0
    double = True  # The rightmost digit of full_str (index 13, which is 0-based index 13) is doubled
    for char in reversed(full_str):
        val = int(char)
        if double:
            val *= 2
            if val > 9:
                val -= 9
        total_sum += val
        double = not double
        
    calc_check = (10 - (total_sum % 10)) % 10
    return calc_check == check_digit

def check_npi(order: dict) -> str:
    npi = order.get("npi")
    if not npi or not is_valid_npi_format(npi):
        return "FAILED"
    return "PASSED"

def check_invalid_diagnosis(order: dict) -> str:
    icd = order.get("icd10_code")
    if not icd or icd not in ICD10_LOOKUP_TABLE:
        return "FAILED"
    return "PASSED"

def check_other_insurance_primary(order: dict) -> str:
    # If order has a flag indicating other primary insurance, and COB is not resolved
    if order.get("other_insurance_primary") is True and not order.get("cob_resolved"):
        return "FAILED"
    return "PASSED"

def check_invalid_dob_gender(order: dict) -> str:
    dob = order.get("dob")
    gender = order.get("gender")
    if not dob or not gender or gender not in ["M", "F", "U"]:
        return "FAILED"
    return "PASSED"

def check_cannot_identify_patient(order: dict) -> str:
    patient_id = order.get("patient_id")
    if not patient_id or patient_id == "UNKNOWN_PATIENT":
        return "FAILED"
    return "PASSED"

def check_incorrect_address(order: dict) -> str:
    address = order.get("address")
    if not address or "Fake" in address or "PO Box" in address or len(address) < 10:
        return "FAILED"
    return "PASSED"

def check_lab_out_of_network(order: dict) -> str:
    # Check if network_status is OON or CPT code is 81408 (which we mock as out of network for some payers)
    if order.get("network_status") == "OON" or order.get("cpt_code") == "81408":
        return "FAILED"
    return "PASSED"

def check_visit_benefit_exceeded(order: dict) -> str:
    if int(order.get("visit_number") or 1) > 10:
        return "FAILED"
    return "PASSED"

def check_employer_name_needed(order: dict) -> str:
    payer_id = order.get("payer_id")
    employer_name = order.get("employer_name")
    requires_employer = PAYER_CONFIG.get(payer_id, {}).get("requires_employer", False)
    if requires_employer and not employer_name:
        return "FAILED"
    return "PASSED"

def check_patient_info_needed(order: dict) -> str:
    # Code 40: Patient info needed (e.g. missing patient name)
    if not order.get("patient_name") and not (order.get("patient_first_name") and order.get("patient_last_name")):
        return "FAILED"
    return "PASSED"

def check_non_covered_service(order: dict) -> str:
    cpt = order.get("cpt_code")
    payer = order.get("payer_id")
    # Mocking 81479 as non-covered for Medicare or PAYER_E
    if cpt == "81479" and payer in ["PAYER_E", "Medicare"]:
        return "FAILED"
    return "PASSED"

def check_another_provider_paid(order: dict) -> str:
    if order.get("another_provider_paid") is True:
        return "FAILED"
    return "PASSED"

def check_partial_response(order: dict) -> str:
    """Code 13: Payer response artifact, not a pre-submission defect."""
    if order.get("is_presubmission", True):
        return "NOT_APPLICABLE_PRESUBMISSION"
    if order.get("payer_response_partial") is True:
        return "FAILED"
    return "PASSED"

# CHECKS Registry mapping code -> check function
CHECKS_REGISTRY = {
    "NPI_MISSING_OR_INVALID": check_npi,
    "13": check_partial_response,
    "14": check_invalid_diagnosis,
    "15": check_other_insurance_primary,
    "19": check_invalid_dob_gender,
    "21": check_cannot_identify_patient,
    "30": check_incorrect_address,
    "32": check_lab_out_of_network,
    "33": check_visit_benefit_exceeded,
    "39": check_employer_name_needed,
    "40": check_patient_info_needed,
    "45": check_non_covered_service,
    "52": check_another_provider_paid
}

def detect_reject_codes(order: dict, catalog: list[dict] = None) -> list[dict]:
    """
    Evaluates order dictionary against deterministic checks.
    Returns a list of detected reject codes with metadata.
    """
    start_time = time.time()
    detected = []
    
    # If no catalog is provided, we can rely on our internal keys
    target_codes = [c["reject_code"] for c in catalog] if catalog else list(CHECKS_REGISTRY.keys())
    
    for code in target_codes:
        check_fn = CHECKS_REGISTRY.get(code)
        if not check_fn:
            logger.warning(f"No check function registered for code: {code}")
            continue
            
        try:
            status = check_fn(order)
            if status == "FAILED":
                detected.append({
                    "reject_code": code,
                    "detection_source": f"check_{code}" if code != "NPI_MISSING_OR_INVALID" else "check_npi"
                })
            elif status == "NOT_APPLICABLE_PRESUBMISSION" and code == "13":
                # Do not flag as failed, but we log the query check
                pass
        except Exception as e:
            logger.error(f"Check for code {code} failed internally: {e}")
            detected.append({
                "reject_code": code,
                "detection_source": f"check_{code}_error",
                "status": "undetermined"
            })
            
    duration_ms = (time.time() - start_time) * 1000.0
    
    # Log execution to governance sink
    log_governance_sink(
        action="REASON_DETECTED",
        rule_applied="reason_detection_layer",
        input_payload={"order_id": order.get("order_id") or order.get("claim_id")},
        output_payload={"detected_codes": detected},
        duration_ms=duration_ms,
        claim_id=order.get("claim_id") or order.get("order_id"),
        trace_id=order.get("trace_id")
    )
    
    return detected
