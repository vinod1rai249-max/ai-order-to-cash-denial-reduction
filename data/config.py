# Configuration for synthetic data generation and lookup tables

ICD10_LOOKUP_TABLE = {
    "M54.5": "Low back pain",
    "I10": "Essential (primary) hypertension",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "Z00.00": "Encounter for general adult medical examination without abnormal findings",
    "J06.9": "Acute upper respiratory infection, unspecified",
    "K21.9": "Gastro-esophageal reflux disease without esophagitis",
    "F41.1": "Generalized anxiety disorder",
    "N39.0": "Urinary tract infection, site not specified",
    "D64.9": "Anemia, unspecified",
    "H10.9": "Conjunctivitis, unspecified",
    "Z13.71": "Encounter for screening for genetic disease carrier status",
    "Z15.01": "Genetic susceptibility to malignant neoplasm of breast",
    "Z31.430": "Encounter for genetic testing of female for procreative management",
    "C50.911": "Malignant neoplasm of unspecified site of right female breast",
    "Z84.81": "Family history of carrier of genetic disease",
    "A49.9": "Bacterial infection, unspecified",
    "B34.9": "Viral infection, unspecified",
    "R78.81": "Bacteremia",
    "D70.9": "Neutropenia, unspecified"
}

PAYER_CONFIG = {
    "PAYER_A": {"name": "UnitedHealthcare", "requires_employer": True, "base_denial_rate": 0.12},
    "PAYER_B": {"name": "Aetna", "requires_employer": False, "base_denial_rate": 0.15},
    "PAYER_C": {"name": "Cigna", "requires_employer": True, "base_denial_rate": 0.18},
    "PAYER_D": {"name": "Anthem", "requires_employer": False, "base_denial_rate": 0.10},
    "PAYER_E": {"name": "Medicare", "requires_employer": False, "base_denial_rate": 0.05}
}

CPT_CONFIG = {
    "81479": {"description": "Unlisted molecular pathology", "base_denial_rate": 0.82},
    "81408": {"description": "Molecular pathology level 9", "base_denial_rate": 0.82},
    "87798": {"description": "Infectious agent detection", "base_denial_rate": 0.82},
    "99213": {"description": "Office visit established patient lvl 3", "base_denial_rate": 0.05},
    "99214": {"description": "Office visit established patient lvl 4", "base_denial_rate": 0.07},
    "99203": {"description": "Office visit new patient lvl 3", "base_denial_rate": 0.08},
    "36415": {"description": "Collection of venous blood", "base_denial_rate": 0.02},
    "85025": {"description": "Complete blood count", "base_denial_rate": 0.03}
}
