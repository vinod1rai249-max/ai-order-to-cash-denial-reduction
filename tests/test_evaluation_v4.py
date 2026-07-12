import os
import json
import importlib
import unittest
import logging

# Set env variables before imports to avoid validation failures
os.environ["GCP_PROJECT_ID"] = os.environ.get("GCP_PROJECT_ID", "adpo-healthcare-agent")

from agents.reason_detection import detect_reject_codes
from orchestrator.graph_v4 import app_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestEvaluationV4(unittest.TestCase):
    
    def setUp(self):
        # Load the golden dataset
        dataset_path = os.path.join(os.path.dirname(__file__), "golden_dataset_v4.json")
        with open(dataset_path, "r") as f:
            self.golden_dataset = json.load(f)

    def test_score_risk_falls_back_without_bigquery_project(self):
        original_project_id = os.environ.get("GCP_PROJECT_ID")
        try:
            os.environ.pop("GCP_PROJECT_ID", None)
            governance_logger = importlib.reload(importlib.import_module("governance.governance_logger"))
            score_risk_module = importlib.reload(importlib.import_module("ml.score_risk"))

            order = {
                "order_id": "ORD-FALLBACK-001",
                "payer_id": "PAYER_A",
                "cpt_code": "81479",
                "icd10_code": "INVALID_ICD",
                "prior_auth_on_file": False,
                "timely_filing_days_remaining": 15,
                "npi": "INVALIDNPI",
            }

            score = score_risk_module.score_risk(order)
            self.assertEqual(score, 0.82)
        finally:
            if original_project_id is None:
                os.environ.pop("GCP_PROJECT_ID", None)
            else:
                os.environ["GCP_PROJECT_ID"] = original_project_id
            importlib.reload(importlib.import_module("governance.governance_logger"))
            importlib.reload(importlib.import_module("ml.score_risk"))

    def test_remediation_evaluation(self):
        passed_tests = 0
        total_tests = len(self.golden_dataset)
        non_fixable_violations = 0
        
        logger.info(f"Starting evaluation of {total_tests} golden records...")
        
        for case in self.golden_dataset:
            order_id = case["order_id"]
            logger.info(f"Evaluating Case: {order_id}")
            
            # Step 1: Evaluate deterministic reason detection
            detected = detect_reject_codes(case)
            detected_codes = [c.get("reject_code") for c in detected]
            expected_codes = case["expected_reject_codes_detected"]
            
            self.assertEqual(
                sorted(detected_codes), sorted(expected_codes),
                f"Mismatch in detected codes for {order_id}. Found: {detected_codes}, Expected: {expected_codes}"
            )
            
            # Step 2: Run through the graph workflow
            initial_state = {
                "order": dict(case),
                "risk_score": 0.0,
                "reject_codes_detected": [],
                "remediation_attempts": 0,
                "remediation_history": []
            }
            
            result = app_graph.invoke(initial_state)
            final_order = result.get("order", {})
            
            # Verify HITL Gating
            expected_hitl = case["expected_hitl_required"]
            actual_hitl = final_order.get("hitl_required", False)
            
            # Assert SLO: Non-auto-fixable reject codes must never bypass the HITL gate
            is_auto_fixable_scenario = case["expected_auto_fixable"]
            
            if not is_auto_fixable_scenario:
                # Crucial SLO check: verify it was never sent to clean status or bypassed HITL
                if not actual_hitl or final_order.get("status") == "clean":
                    non_fixable_violations += 1
                    logger.error(f"SLO VIOLATION for {order_id}: Non-fixable reject code bypassed HITL review!")
                    
            self.assertEqual(
                actual_hitl, expected_hitl,
                f"HITL status mismatch for {order_id}. Actual: {actual_hitl}, Expected: {expected_hitl}"
            )
            
            passed_tests += 1
            logger.info(f"Case {order_id} passed evaluation.")
            
        logger.info(f"Evaluation Complete. Passed: {passed_tests}/{total_tests}")
        
        # Enforce 0% SLO
        self.assertEqual(
            non_fixable_violations, 0,
            f"SLO failure: {non_fixable_violations} non-auto-fixable claims bypassed human-in-the-loop review."
        )

if __name__ == "__main__":
    unittest.main()
