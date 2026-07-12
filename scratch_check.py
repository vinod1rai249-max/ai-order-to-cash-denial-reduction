import os
import json
import dotenv
from google.cloud import bigquery

dotenv.load_dotenv()

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "adpo-healthcare-agent")
client = bigquery.Client(project=GCP_PROJECT_ID)

query = f"SELECT order_id, status, risk_history FROM `{GCP_PROJECT_ID}.silver.orders`"
results = list(client.query(query).result())

print(f"Total orders: {len(results)}")
for r in results:
    row = dict(r.items())
    history = row.get("risk_history")
    if history:
        if isinstance(history, str):
            history = json.loads(history)
    else:
        history = []
    
    codes = []
    for h in history:
        detected = h.get("reject_codes_detected") or []
        for c in detected:
            if isinstance(c, dict):
                codes.append(c.get("reject_code"))
            else:
                codes.append(c)
                
    print(f"Order: {row['order_id']}, Status: {row['status']}, Codes in History: {codes}")
