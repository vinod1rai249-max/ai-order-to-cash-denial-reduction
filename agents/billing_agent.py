import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_billing_agent(state: dict) -> dict:
    """Mock billing agent to submit clean claims."""
    order = state.get("order", state)
    order["status"] = "clean"
    logger.info(f"Billing Agent: Claim submitted successfully for order {order.get('order_id')}")
    if "order" in state:
        state["order"] = order
    return state
