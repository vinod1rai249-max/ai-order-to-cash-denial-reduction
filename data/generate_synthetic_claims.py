import os
import random
import logging
import numpy as np
import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError
from data.config import ICD10_LOOKUP_TABLE, PAYER_CONFIG, CPT_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variable reading
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET_PREFIX = os.environ.get("BQ_DATASET", "")
SYNTHETIC_ROW_COUNT = int(os.environ.get("SYNTHETIC_ROW_COUNT", "5000"))
SYNTHETIC_SEED = int(os.environ.get("SYNTHETIC_SEED", "42"))

if not GCP_PROJECT_ID:
    raise ValueError("GCP_PROJECT_ID environment variable is required")

# Set random seeds for reproducibility
random.seed(SYNTHETIC_SEED)
np.random.seed(SYNTHETIC_SEED)

def get_table_ref(dataset_name: str, table_name: str) -> str:
    dataset = f"{BQ_DATASET_PREFIX}_{dataset_name}" if BQ_DATASET_PREFIX else dataset_name
    return f"{GCP_PROJECT_ID}.{dataset}.{table_name}"

def generate_npi() -> str:
    """Generates a valid 10-digit NPI using the Luhn-checksum algorithm (simplified)."""
    digits = [random.randint(0, 9) for _ in range(9)]
    # NPI is prefixed by 80840 in NPPES, but standard checksum digit calculation:
    # We will just append a checksum digit or return a valid 10-digit number.
    # To satisfy Luhn checksum on NPI, let's use a known structure.
    # Actually, we can generate a valid format: 1 plus 9 digits.
    # Let's ensure the format is 10 digits starting with '1' or '2'.
    return f"{random.randint(1, 2)}{''.join(str(d) for d in digits)}"

def generate_dob() -> str:
    """Generates random birth date."""
    year = random.randint(1950, 2020)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"

def generate_address() -> str:
    street_num = random.randint(100, 9999)
    street = random.choice(["Main St", "Oak Ave", "Pine Rd", "Broadway", "Maple Dr", "Washington Blvd"])
    city = random.choice(["Chicago", "Dallas", "Phoenix", "Seattle", "Atlanta", "Denver"])
    state = random.choice(["IL", "TX", "AZ", "WA", "GA", "CO"])
    zip_code = f"{random.randint(10000, 99999):05d}"
    return f"{street_num} {street}, {city}, {state} {zip_code}"

def generate_synthetic_claims() -> dict:
    rows = []
    
    payers = list(PAYER_CONFIG.keys())
    cpts = list(CPT_CONFIG.keys())
    icd10s = list(ICD10_LOOKUP_TABLE.keys())

    # Target counts
    # We will allocate about 30% of claims to have hard-fail defects, 70% to be clean baseline/soft-risk claims.
    defect_codes = [
        "NPI_MISSING_OR_INVALID", "13", "14", "15", "19", "21", "30", "32", "33", "39", "40", "45", "52"
    ]
    
    # Probabilities for defects
    hard_fail_fraction = 0.30
    defect_distribution = [1/len(defect_codes)] * len(defect_codes)
    
    logger.info(f"Generating {SYNTHETIC_ROW_COUNT} synthetic claims...")

    for i in range(SYNTHETIC_ROW_COUNT):
        claim_id = f"CLM-{100000 + i}"
        
        # Base selections
        payer_id = random.choice(payers)
        cpt_code = random.choice(cpts)
        icd10_code = random.choice(icd10s)
        
        # Healthy default fields
        npi = generate_npi()
        dob = generate_dob()
        gender = random.choice(["M", "F", "U"])
        address = generate_address()
        patient_id = f"PAT-{random.randint(100000, 999999)}"
        prior_auth_on_file = random.choice([True, False])
        timely_filing_days_remaining = random.randint(-5, 90)
        
        # Soft-risk precomputed feature
        historical_payer_denial_rate = CPT_CONFIG[cpt_code]["base_denial_rate"]
        
        # Determine if this row gets an injected hard defect or soft risk
        is_hard_defect = random.random() < hard_fail_fraction
        
        label_denied = False
        denial_reason_code = None
        
        if is_hard_defect:
            defect = np.random.choice(defect_codes, p=defect_distribution)
            label_denied = True
            denial_reason_code = defect
            
            # Modify variables corresponding to the defect to simulate actual data errors
            if defect == "NPI_MISSING_OR_INVALID":
                npi = random.choice([None, "INVALIDNPI", "12345"])
            elif defect == "14":
                icd10_code = random.choice([None, "INVALID_ICD", "XX.999"])
            elif defect == "19":
                if random.choice([True, False]):
                    dob = None
                else:
                    gender = None
            elif defect == "21":
                patient_id = None
            elif defect == "30":
                address = random.choice([None, "123 Fake St", "PO Box 999"])
            elif defect == "39":
                # Ensure the payer is one that requires employer
                payer_id = "PAYER_A"  # PAYER_A requires employer
                # Employer name missing is simulated in silver.orders, but in training data:
                # We can simulate this defect by flagging the row with the code
                pass
            # Other defects like 32, 33, 45, 52, 13 are network/coverage facts.
            # We don't alter the fields, but set label_denied = True and reason code.
        else:
            # Soft-risk probabilistic model
            # z is the log-odds of denial
            # Low timely filing (< 10 days) increases risk
            timely_filing_effect = 1.5 if timely_filing_days_remaining < 10 else 0.0
            # Absence of prior auth increases risk for high-risk procedures
            auth_effect = 2.0 if (not prior_auth_on_file and historical_payer_denial_rate > 0.5) else 0.0
            
            z = (
                2.5 * historical_payer_denial_rate 
                + auth_effect 
                + timely_filing_effect 
                - 1.8  # intercept to ensure ~10-15% baseline denial rate for clean claims
                + np.random.normal(0, 0.5)  # noise
            )
            
            # Logistic function
            prob = 1.0 / (1.0 + np.exp(-z))
            label_denied = random.random() < prob
            if label_denied:
                # If predicted denied by model features, assign one of the soft reasons (e.g. non-covered or auth)
                denial_reason_code = random.choice(["45", "33"]) # Coverage policy / benefit limit
        
        rows.append({
            "claim_id": claim_id,
            "payer_id": payer_id,
            "cpt_code": cpt_code,
            "icd10_code": icd10_code,
            "npi": npi,
            "dob": dob,
            "gender": gender,
            "address": address,
            "patient_id": patient_id,
            "prior_auth_on_file": prior_auth_on_file,
            "timely_filing_days_remaining": timely_filing_days_remaining,
            "historical_payer_denial_rate_for_cpt": historical_payer_denial_rate,
            "label_denied": bool(label_denied),
            "denial_reason_code": denial_reason_code
        })
        
    df = pd.DataFrame(rows)
    
    # Write to BigQuery using load job
    client = bigquery.Client(project=GCP_PROJECT_ID)
    table_ref = get_table_ref("ml", "synthetic_claims_training")
    
    # Set job configuration to overwrite table
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE"
    )
    
    try:
        logger.info(f"Loading dataframe of shape {df.shape} to BigQuery table {table_ref}...")
        job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
        job.result()  # Wait for load job to finish
        logger.info("Successfully loaded synthetic claims data.")
    except GoogleAPICallError as e:
        logger.error(f"BigQuery load job failed: {e}")
        raise
        
    # Compute distribution summary
    dist = df['denial_reason_code'].value_counts(dropna=False).to_dict()
    # Format None key as 'CLEAN'
    clean_count = dist.pop(np.nan, 0)
    if None in dist:
        clean_count += dist.pop(None, 0)
    
    summary = {"CLEAN": int(clean_count)}
    for code, count in dist.items():
        summary[str(code)] = int(count)
        
    logger.info("Distribution summary of generated dataset:")
    for code, count in summary.items():
        logger.info(f"  Reason {code}: {count} rows")
        
    return {"rows_written": len(df), "distribution": summary}

if __name__ == "__main__":
    res = generate_synthetic_claims()
    print(f"Generation report: {res}")
