import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MPI_PATIENT_REGISTRY = [
    {"patient_id": "PAT-200101", "confidence": 0.97},
    {"patient_id": "PAT-200202", "confidence": 0.94},
    {"patient_id": "PAT-200303", "confidence": 0.96},
    {"patient_id": "PAT-200404", "confidence": 0.92},
    {"patient_id": "PAT-200505", "confidence": 0.98},
    {"patient_id": "PAT-200606", "confidence": 0.91},
    {"patient_id": "PAT-200707", "confidence": 0.95},
    {"patient_id": "PAT-200808", "confidence": 0.93},
]

MPI_CONFIDENCE_THRESHOLD = 0.90


def find_patient_mpi(order: dict) -> dict | None:
    """
    Simulates a Master Patient Index (MPI) fuzzy search using available
    demographics (name, DOB, address). Returns a resolved patient_id with
    a match confidence score that varies by input.
    """
    patient_name = order.get("patient_name", "")
    dob = order.get("dob", "")
    address = order.get("address", "")

    search_key = f"{patient_name}:{dob}:{address}"
    if not patient_name and not dob and not address:
        return None

    digest = int(hashlib.sha256(search_key.encode()).hexdigest(), 16)
    selected = MPI_PATIENT_REGISTRY[digest % len(MPI_PATIENT_REGISTRY)]

    logger.info(
        f"MPI search: '{search_key}' -> matched {selected['patient_id']} "
        f"(confidence={selected['confidence']:.2f})"
    )
    return selected


def fix_patient_identification(order: dict) -> dict:
    """Handler for reject code 21 (Cannot identify patient)."""
    mpi = find_patient_mpi(order)
    if mpi and mpi.get("match_confidence", mpi.get("confidence", 0.0)) >= MPI_CONFIDENCE_THRESHOLD:
        resolved_id = mpi["patient_id"]
        confidence = mpi.get("confidence", mpi.get("match_confidence", 0.0))
        order["patient_id"] = resolved_id
        order.setdefault("_sources", {})["patient_id"] = "Master Patient Index (MPI) search"
        logger.info(
            f"MPI resolution successful: patched patient_id to {resolved_id} "
            f"(confidence={confidence:.2f})"
        )
    else:
        order["hitl_required"] = True
        order["hitl_reason"] = (
            "Master Patient Index (MPI) search returned low-confidence matches. "
            "Manual identity verification required."
        )
    return order
