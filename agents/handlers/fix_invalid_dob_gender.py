import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMOGRAPHICS_REGISTRY = [
    {"dob": "1985-06-15", "gender": "F"},
    {"dob": "1972-08-20", "gender": "M"},
    {"dob": "1990-11-03", "gender": "F"},
    {"dob": "1968-02-14", "gender": "M"},
    {"dob": "1995-12-01", "gender": "M"},
    {"dob": "1988-03-22", "gender": "F"},
    {"dob": "1975-07-09", "gender": "M"},
    {"dob": "2001-05-30", "gender": "F"},
    {"dob": "1960-09-17", "gender": "M"},
    {"dob": "1993-01-25", "gender": "F"},
]


def get_demographics_from_source(patient_id: str) -> dict | None:
    """
    Simulates a Master Patient Index demographic lookup.
    Returns DOB and gender that vary by patient_id using deterministic hashing.
    """
    if not patient_id:
        return None

    digest = int(hashlib.sha256(patient_id.encode()).hexdigest(), 16)
    selected = DEMOGRAPHICS_REGISTRY[digest % len(DEMOGRAPHICS_REGISTRY)]

    logger.info(
        f"MPI demographics lookup: patient {patient_id} -> "
        f"dob={selected['dob']}, gender={selected['gender']}"
    )
    return selected


def fix_invalid_dob_gender(order: dict) -> dict:
    """Handler for reject code 19 (Invalid DOB / gender)."""
    patient_id = order.get("patient_id")

    demo = get_demographics_from_source(patient_id)
    if demo:
        if not order.get("dob"):
            order["dob"] = demo["dob"]
            order.setdefault("_sources", {})["dob"] = "demographic registry"
        if not order.get("gender") or order.get("gender") not in ("M", "F", "U"):
            order["gender"] = demo["gender"]
            order.setdefault("_sources", {})["gender"] = "demographic registry"
        logger.info(f"Fixed DOB/gender for patient {patient_id} from demographic registry.")
    else:
        order["hitl_required"] = True
        order["hitl_reason"] = "Failed to locate patient master demographic record."
    return order
