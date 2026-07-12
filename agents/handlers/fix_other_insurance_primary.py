import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COB_RESOLUTION_TABLE = {
    "PAYER_E": [
        {"primary": "PAYER_A", "name": "UnitedHealthcare"},
        {"primary": "PAYER_B", "name": "Aetna"},
        {"primary": "PAYER_C", "name": "Cigna"},
        {"primary": "PAYER_D", "name": "Anthem"},
    ],
    "PAYER_A": [
        {"primary": "PAYER_C", "name": "Cigna"},
        {"primary": "PAYER_D", "name": "Anthem"},
    ],
    "PAYER_B": [
        {"primary": "PAYER_A", "name": "UnitedHealthcare"},
        {"primary": "PAYER_D", "name": "Anthem"},
    ],
}


def get_cob_status(payer_id: str, patient_id: str) -> dict | None:
    """
    Simulates a Coordination of Benefits (COB) eligibility lookup.
    Uses the current payer_id to determine which commercial payer is actually
    primary, and hashes patient_id to select among candidates deterministically.
    """
    if not patient_id:
        return None

    candidates = COB_RESOLUTION_TABLE.get(payer_id)
    if not candidates:
        return None

    digest = int(hashlib.sha256(patient_id.encode()).hexdigest(), 16)
    selected = candidates[digest % len(candidates)]

    logger.info(
        f"COB lookup: patient {patient_id} current payer {payer_id} -> "
        f"primary is {selected['primary']} ({selected['name']})"
    )
    return {
        "primary_payer_id": selected["primary"],
        "secondary_payer_id": payer_id,
        "cob_resolved": True,
    }


def fix_other_insurance_primary(order: dict) -> dict:
    """Handler for reject code 15 (Other insurance primary)."""
    payer_id = order.get("payer_id")
    patient_id = order.get("patient_id")

    cob = get_cob_status(payer_id, patient_id)
    if cob and cob.get("cob_resolved"):
        order["payer_id"] = cob["primary_payer_id"]
        order["cob_resolved"] = True
        order.setdefault("_sources", {})["payer_id"] = "coordination of benefits lookup"
        logger.info(f"COB resolved: re-sequenced payer to {cob['primary_payer_id']}")
    else:
        order["hitl_required"] = True
        order["hitl_reason"] = "Coordination of Benefits (COB) could not resolve primary payer ordering."
    return order
