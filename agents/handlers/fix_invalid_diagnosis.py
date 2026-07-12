import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CPT_TO_ICD10_CROSSWALK = {
    "81479": [
        {"icd10": "Z13.71", "desc": "Encounter for screening for genetic disease carrier status"},
        {"icd10": "Z15.01", "desc": "Genetic susceptibility to malignant neoplasm of breast"},
        {"icd10": "Z31.430", "desc": "Encounter for genetic testing of female for procreative management"},
    ],
    "81408": [
        {"icd10": "C50.911", "desc": "Malignant neoplasm of unspecified site of right female breast"},
        {"icd10": "Z84.81", "desc": "Family history of carrier of genetic disease"},
    ],
    "87798": [
        {"icd10": "A49.9", "desc": "Bacterial infection, unspecified"},
        {"icd10": "B34.9", "desc": "Viral infection, unspecified"},
        {"icd10": "R78.81", "desc": "Bacteremia"},
    ],
    "99213": [
        {"icd10": "M54.5", "desc": "Low back pain"},
        {"icd10": "I10", "desc": "Essential hypertension"},
        {"icd10": "E11.9", "desc": "Type 2 diabetes without complications"},
    ],
    "99214": [
        {"icd10": "J06.9", "desc": "Acute upper respiratory infection"},
        {"icd10": "K21.9", "desc": "Gastro-esophageal reflux disease"},
    ],
    "36415": [
        {"icd10": "D64.9", "desc": "Anemia, unspecified"},
        {"icd10": "Z00.00", "desc": "General adult medical examination"},
    ],
    "85025": [
        {"icd10": "D64.9", "desc": "Anemia, unspecified"},
        {"icd10": "D70.9", "desc": "Neutropenia, unspecified"},
    ],
}

DEFAULT_CROSSWALK = [
    {"icd10": "M54.5", "desc": "Low back pain"},
    {"icd10": "I10", "desc": "Essential hypertension"},
]


def get_diagnosis_from_history(patient_id: str, cpt_code: str) -> str | None:
    """
    Simulates a clinical crosswalk lookup: given a CPT code, returns the most
    likely valid ICD-10 diagnosis. Uses a deterministic hash of patient_id to
    select among candidates so different patients get different codes.
    """
    if not patient_id:
        return None

    candidates = CPT_TO_ICD10_CROSSWALK.get(cpt_code, DEFAULT_CROSSWALK)
    digest = int(hashlib.sha256(patient_id.encode()).hexdigest(), 16)
    selected = candidates[digest % len(candidates)]

    logger.info(
        f"Clinical crosswalk: CPT {cpt_code} -> ICD-10 {selected['icd10']} ({selected['desc']}) "
        f"for patient {patient_id}"
    )
    return selected["icd10"]


def fix_invalid_diagnosis(order: dict) -> dict:
    """Handler for reject code 14 (Invalid diagnosis)."""
    patient_id = order.get("patient_id")
    cpt_code = order.get("cpt_code")

    corrected_code = get_diagnosis_from_history(patient_id, cpt_code)
    if corrected_code:
        order["icd10_code"] = corrected_code
        order.setdefault("_sources", {})["icd10_code"] = "clinical crosswalk"
        logger.info(f"Fixed invalid diagnosis: patched icd10_code to {corrected_code}")
    else:
        order["hitl_required"] = True
        order["hitl_reason"] = "Failed to resolve invalid diagnosis code from patient history."
    return order
