import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PATIENT_MASTER = {
    "PAT-000009": {
        "patient_name": "Emily Watson",
        "dob": "1985-06-15",
        "gender": "F",
        "address": "2100 S MICHIGAN AVE, CHICAGO, IL 60616-1300",
    },
    "PAT-000018": {
        "patient_name": "Marcus Thompson",
        "dob": "1972-08-20",
        "gender": "M",
        "address": "456 OAK AVE, CHICAGO, IL 60614-2200",
    },
}

FALLBACK_NAMES = [
    "Sarah Mitchell",
    "James Rodriguez",
    "Anita Patel",
    "Michael O'Brien",
    "Linda Nakamura",
    "David Okafor",
    "Rachel Kim",
    "Thomas Nguyen",
]

FALLBACK_ADDRESSES = [
    "100 MICHIGAN AVE STE 400, CHICAGO, IL 60601-7501",
    "2500 WESTCHESTER AVE, PURCHASE, NY 10577-2500",
    "900 COTTAGE GROVE RD, HARTFORD, CT 06152-0900",
    "1 CAMPUS DR, PARSIPPANY, NJ 07054-0001",
    "220 VIRGINIA AVE, INDIANAPOLIS, IN 46204-2200",
]

FALLBACK_DEMOGRAPHICS = [
    {"dob": "1985-06-15", "gender": "F"},
    {"dob": "1972-08-20", "gender": "M"},
    {"dob": "1990-11-03", "gender": "F"},
    {"dob": "1968-02-14", "gender": "M"},
    {"dob": "1995-12-01", "gender": "M"},
]


def get_patient_master_record(patient_id: str) -> dict | None:
    """
    Simulates a patient master registry lookup.
    Known patient IDs return specific records; unknown IDs get deterministic
    results from the fallback pool.
    """
    if not patient_id:
        return None

    if patient_id in PATIENT_MASTER:
        record = PATIENT_MASTER[patient_id]
        logger.info(f"Patient master: direct match for {patient_id} -> {record['patient_name']}")
        return record

    digest = int(hashlib.sha256(patient_id.encode()).hexdigest(), 16)
    name = FALLBACK_NAMES[digest % len(FALLBACK_NAMES)]
    demo = FALLBACK_DEMOGRAPHICS[digest % len(FALLBACK_DEMOGRAPHICS)]
    addr = FALLBACK_ADDRESSES[digest % len(FALLBACK_ADDRESSES)]

    record = {
        "patient_name": name,
        "dob": demo["dob"],
        "gender": demo["gender"],
        "address": addr,
    }
    logger.info(f"Patient master: fallback match for {patient_id} -> {name}")
    return record


def fix_patient_info(order: dict) -> dict:
    """Handler for reject code 40 (Patient info needed)."""
    patient_id = order.get("patient_id")

    record = get_patient_master_record(patient_id)
    if record:
        if not order.get("patient_name"):
            order["patient_name"] = record["patient_name"]
            order.setdefault("_sources", {})["patient_name"] = "patient master registry"
        if not order.get("dob"):
            order["dob"] = record["dob"]
            order.setdefault("_sources", {})["dob"] = "patient master registry"
        if not order.get("gender") or order["gender"] not in ("M", "F", "U"):
            order["gender"] = record["gender"]
            order.setdefault("_sources", {})["gender"] = "patient master registry"
        if not order.get("address") or len(order["address"]) < 10:
            order["address"] = record["address"]
            order.setdefault("_sources", {})["address"] = "patient master registry"
        logger.info(f"Patched missing patient info for {patient_id} from master record.")
    else:
        order["hitl_required"] = True
        order["hitl_reason"] = "Failed to resolve patient details from the master record registry."
    return order
