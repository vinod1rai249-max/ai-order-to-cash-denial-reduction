import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMPLOYER_REGISTRY = {
    "PAT-000015": "Advocate Aurora Health",
    "PAT-000016": "Northwestern Memorial Healthcare",
    "PAT-000017": "Rush University Medical Center",
    "PAT-000018": "Loyola University Health System",
    "PAT-000019": "University of Chicago Medicine",
}

FALLBACK_EMPLOYERS = [
    "Advocate Aurora Health",
    "Northwestern Memorial Healthcare",
    "Rush University Medical Center",
    "UnitedHealth Group Inc.",
    "Walgreens Boots Alliance",
    "Abbott Laboratories",
    "Baxter International Inc.",
    "Caterpillar Inc.",
    "Deere & Company",
    "State Farm Insurance",
]


def get_employer_name_from_master(patient_id: str) -> str | None:
    """
    Simulates an HR / employer master database lookup.
    Known patient IDs return specific employers; unknown IDs get a
    deterministic selection from the fallback pool.
    """
    if not patient_id:
        return None

    if patient_id in EMPLOYER_REGISTRY:
        employer = EMPLOYER_REGISTRY[patient_id]
        logger.info(f"Employer lookup: patient {patient_id} -> {employer} (direct match)")
        return employer

    digest = int(hashlib.sha256(patient_id.encode()).hexdigest(), 16)
    employer = FALLBACK_EMPLOYERS[digest % len(FALLBACK_EMPLOYERS)]
    logger.info(f"Employer lookup: patient {patient_id} -> {employer} (registry fallback)")
    return employer


def fix_employer_name(order: dict) -> dict:
    """Handler for reject code 39 (Employer name needed)."""
    patient_id = order.get("patient_id")

    employer = get_employer_name_from_master(patient_id)
    if employer:
        order["employer_name"] = employer
        order.setdefault("_sources", {})["employer_name"] = "HR / employer master database"
        logger.info(f"Patched employer name: '{employer}' for patient {patient_id}")
    else:
        order["hitl_required"] = True
        order["hitl_reason"] = "Failed to locate employer name in master HR files."
    return order
