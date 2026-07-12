import os
import json
import dotenv

# Load .env explicitly with absolute path
dotenv.load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

os.environ["GCP_PROJECT_ID"] = os.environ.get("GCP_PROJECT_ID", "adpo-healthcare-agent")

from google.cloud import bigquery
from agents.reason_detection import detect_reject_codes

client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])

query = f"SELECT * FROM `{os.environ['GCP_PROJECT_ID']}.silver.orders` WHERE status = 'hitl'"
orders = [dict(r.items()) for r in client.query(query).result()]

print(f"Total status='hitl' orders in DB: {len(orders)}")

non_fixable_codes = {"13", "32", "33", "45", "52"}
filtered_orders = []
for order in orders:
    codes_detected = detect_reject_codes(order)
    codes = [c.get("reject_code") if isinstance(c, dict) else c for c in codes_detected]
    is_non_fixable = any(code in non_fixable_codes for code in codes)
    print(f"Order: {order['order_id']}, Detected Codes: {codes}, Is Non-Fixable: {is_non_fixable}")
    if is_non_fixable:
        filtered_orders.append(order)

print(f"Filtered orders (returned by endpoint): {len(filtered_orders)}")
for o in filtered_orders:
    print(f"  - {o['order_id']}")
