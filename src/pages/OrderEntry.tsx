import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../lib/apiClient";
import { StatusBadge } from "../components/StatusBadge";
import { ActivityTable } from "../components/ActivityTable";

const REJECT_CODE_DESCRIPTIONS: Record<string, string> = {
  "NPI_MISSING_OR_INVALID": "NPI provider registry identifier is missing or failed checksum validation.",
  "13": "Partial response received from payor (non-auto-fixable).",
  "14": "Invalid procedure code CPT and diagnosis code ICD-10 combination.",
  "15": "Coordination of Benefits (COB) secondary coverage mismatch (requires primary re-sequencing).",
  "19": "Invalid or mismatched patient Date of Birth or Gender attribute.",
  "21": "Patient identity mismatch in the Master Patient Index (MPI) registry.",
  "30": "Incorrect patient address format (failed standardized USPS formatting).",
  "32": "Lab service is Out-of-Network for this commercial payor (non-auto-fixable).",
  "33": "Maximum benefit visit count limit has been exceeded (non-auto-fixable).",
  "39": "Employer name is missing and required for group plan verification.",
  "40": "Patient name is missing or incomplete in demographics.",
  "45": "Non-covered service category for this commercial payor (non-auto-fixable).",
  "52": "Prior provider claim already paid for this patient visit (non-auto-fixable)."
};

const GOLDEN_TEMPLATES = [
  // Clean Baseline (1 sample)
  {
    id: "TST-CLN-001",
    category: "Clean Baseline",
    title: "1. Routine Office Visit (Clean)",
    description: "Standard established patient visit with no defects. Low risk score (5%).",
    data: {
      patient_id: "PAT-000001",
      patient_name: "Jane Doe",
      provider_first_name: "John Roster",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "1000000004",
      payer_id: "PAYER_B",
      cpt_code: "99213",
      icd10_code: "M54.5",
      dob: "1980-01-01",
      gender: "F",
      address: "123 Main St, Chicago, IL 60601",
      employer_name: "",
      prior_auth_on_file: true,
      timely_filing_days_remaining: 90
    }
  },

  // High-Risk Auto-Fixable — Single Defect
  {
    id: "TST-NPI-001",
    category: "High-Risk (Auto-Fixable)",
    title: "2. Fuzzy NPI Match",
    description: "Invalid NPI on high-risk CPT 87798. Fuzzy matches provider name to patch NPI.",
    data: {
      patient_id: "PAT-000004",
      patient_name: "Jane Doe",
      provider_first_name: "John Roster",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "INVALIDNPI",
      payer_id: "PAYER_B",
      cpt_code: "87798",
      icd10_code: "M54.5",
      dob: "1980-01-01",
      gender: "F",
      address: "123 Main St, Chicago, IL 60601",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 15
    }
  },
  {
    id: "TST-14-001",
    category: "High-Risk (Auto-Fixable)",
    title: "3. Invalid ICD-10 Code",
    description: "ICD-10 is 'INVALID_ICD'. Clinical crosswalk swaps to valid code.",
    data: {
      patient_id: "PAT-000005",
      patient_name: "Jane Doe",
      provider_first_name: "John",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "1000000004",
      payer_id: "PAYER_B",
      cpt_code: "81479",
      icd10_code: "INVALID_ICD",
      dob: "1980-01-01",
      gender: "F",
      address: "123 Main St, Chicago, IL 60601",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 15
    }
  },
  {
    id: "TST-19-001",
    category: "High-Risk (Auto-Fixable)",
    title: "4. Missing DOB & Gender",
    description: "DOB and Gender both missing. Pulls demographics from Master Patient Index.",
    data: {
      patient_id: "PAT-000007",
      patient_name: "Jane Doe",
      provider_first_name: "John",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "1000000004",
      payer_id: "PAYER_B",
      cpt_code: "87798",
      icd10_code: "M54.5",
      dob: "",
      gender: "",
      address: "123 Main St, Chicago, IL 60601",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 15
    }
  },
  {
    id: "TST-30-001",
    category: "High-Risk (Auto-Fixable)",
    title: "5. Invalid Patient Address",
    description: "Address is '123 Fake St'. USPS standardization fixes the address.",
    data: {
      patient_id: "PAT-000008",
      patient_name: "Jane Doe",
      provider_first_name: "John",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "1000000004",
      payer_id: "PAYER_B",
      cpt_code: "81479",
      icd10_code: "M54.5",
      dob: "1980-01-01",
      gender: "F",
      address: "123 Fake St",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 15
    }
  },

  // High-Risk Auto-Fixable — Multi-Defect Combinations
  {
    id: "TST-MULTI-001",
    category: "High-Risk (Multi-Defect)",
    title: "6. NPI + ICD-10 + Address",
    description: "Three defects: invalid NPI, bad ICD-10, and fake address. All auto-fixable by agents in sequence.",
    data: {
      patient_id: "PAT-000016",
      patient_name: "Maria Garcia",
      provider_first_name: "John Roster",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "INVALIDNPI",
      payer_id: "PAYER_B",
      cpt_code: "81479",
      icd10_code: "INVALID_ICD",
      dob: "1988-03-14",
      gender: "F",
      address: "123 Fake St",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 10
    }
  },
  {
    id: "TST-MULTI-002",
    category: "High-Risk (Multi-Defect)",
    title: "7. NPI + Demographics + Employer",
    description: "Invalid NPI, missing DOB/gender, and missing employer for PAYER_C. Agents fix all three.",
    data: {
      patient_id: "PAT-000017",
      patient_name: "Carlos Rivera",
      provider_first_name: "John Roster",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "INVALIDNPI",
      payer_id: "PAYER_C",
      cpt_code: "87798",
      icd10_code: "M54.5",
      dob: "",
      gender: "",
      address: "321 Elm St, Chicago, IL 60605",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 12
    }
  },
  {
    id: "TST-MULTI-003",
    category: "High-Risk (Multi-Defect)",
    title: "8. Empty NPI + COB Mismatch + Missing Name",
    description: "Blank NPI, Medicare billed as secondary (COB), and missing patient name. Three-agent cascade fix.",
    data: {
      patient_id: "PAT-000018",
      patient_name: "",
      provider_first_name: "John Roster",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "",
      payer_id: "PAYER_E",
      cpt_code: "81479",
      icd10_code: "M54.5",
      dob: "1972-08-20",
      gender: "M",
      address: "456 Oak Ave, Chicago, IL 60614",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 8,
      other_insurance_primary: true,
      cob_resolved: false
    }
  },
  {
    id: "TST-MULTI-004",
    category: "High-Risk (Multi-Defect)",
    title: "9. ICD-10 + Demographics + Address + Employer",
    description: "Four defects: invalid ICD-10, missing DOB/gender, fake address, and missing employer for PAYER_A.",
    data: {
      patient_id: "PAT-000019",
      patient_name: "Priya Sharma",
      provider_first_name: "John",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "1000000004",
      payer_id: "PAYER_A",
      cpt_code: "81479",
      icd10_code: "XX.999",
      dob: "",
      gender: "",
      address: "PO Box 999",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 5
    }
  },
  {
    id: "TST-MULTI-005",
    category: "High-Risk (Multi-Defect)",
    title: "10. NPI + ICD-10 + Patient ID + Employer",
    description: "Invalid NPI, bad ICD-10, unknown patient ID, and missing employer for PAYER_A. Full agent pipeline.",
    data: {
      patient_id: "UNKNOWN_PATIENT",
      patient_name: "David Chen",
      provider_first_name: "John Roster",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "12345",
      payer_id: "PAYER_A",
      cpt_code: "87798",
      icd10_code: "INVALID_ICD",
      dob: "1995-12-01",
      gender: "M",
      address: "789 Pine Rd, Chicago, IL 60622",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 7
    }
  },
  {
    id: "TST-MULTI-006",
    category: "High-Risk (Multi-Defect)",
    title: "11. All Fixable Defects Combined",
    description: "Every auto-fixable defect at once: invalid NPI, bad ICD-10, missing DOB/gender, fake address, missing employer, missing patient name. Maximum agent cascade.",
    data: {
      patient_id: "UNKNOWN_PATIENT",
      patient_name: "",
      provider_first_name: "John Roster",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "INVALIDNPI",
      payer_id: "PAYER_A",
      cpt_code: "81479",
      icd10_code: "XX.999",
      dob: "",
      gender: "",
      address: "PO Box 999",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 3
    }
  },

  // HITL Gated (1 sample)
  {
    id: "TST-32-001",
    category: "HITL Gated (Unfixable)",
    title: "12. Out-of-Network Service (HITL)",
    description: "CPT 81408 is out-of-network. Non-auto-fixable: routes to human review.",
    data: {
      patient_id: "PAT-000010",
      patient_name: "Jane Doe",
      provider_first_name: "John",
      provider_last_name: "Smith",
      provider_state: "IL",
      provider_taxonomy: "Family Medicine",
      npi: "1000000004",
      payer_id: "PAYER_B",
      cpt_code: "81408",
      icd10_code: "M54.5",
      dob: "1980-01-01",
      gender: "F",
      address: "123 Main St, Chicago, IL 60601",
      employer_name: "",
      prior_auth_on_file: false,
      timely_filing_days_remaining: 15
    }
  }
];

export const OrderEntry: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    order_id: `ORD-${Math.floor(100000 + Math.random() * 900000)}`,
    patient_id: "PAT-100293",
    patient_name: "Jane Doe",
    provider_first_name: "John Roster",
    provider_last_name: "Smith",
    provider_state: "IL",
    provider_taxonomy: "Family Medicine",
    npi: "INVALIDNPI",
    payer_id: "PAYER_A",
    cpt_code: "81479",
    icd10_code: "INVALID_ICD",
    dob: "1985-06-15",
    gender: "F",
    address: "123 Fake St",
    employer_name: "",
    prior_auth_on_file: false,
    timely_filing_days_remaining: 15,
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [recentOrders, setRecentOrders] = useState<any[]>([]);

  const fetchRecent = async () => {
    try {
      const response = await apiClient.get("/api/v1/orders");
      setRecentOrders(response.data);
    } catch (err) {
      console.error("Failed to fetch recent orders:", err);
    }
  };

  useEffect(() => {
    fetchRecent();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { id, value, type } = e.target;
    const checked = (e.target as HTMLInputElement).checked;
    
    setFormData((prev) => ({
      ...prev,
      [id]: type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.post("/api/v1/orders", formData);
      setResult(response.data);
      fetchRecent();
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "Intake submission failed. Please verify BQML connection.");
    } finally {
      setLoading(false);
    }
  };

  const handleRemediate = async () => {
    if (!result) return;
    setLoading(true);
    try {
      const orderId = result.order_id;
      const response = await apiClient.post(`/api/v1/orders/${orderId}/remediate`);
      
      // Fetch fully updated order details from BigQuery
      const orderRes = await apiClient.get(`/api/v1/orders/${orderId}`);
      const updatedOrder = orderRes.data;
      
      setResult({
        ...result,
        ...updatedOrder,
        reject_codes_detected: response.data.hitl_required ? result.reject_codes_detected : []
      });

      // Update form values with the patched values
      setFormData(prev => ({
        ...prev,
        npi: updatedOrder.npi !== undefined ? updatedOrder.npi : prev.npi,
        dob: updatedOrder.dob !== undefined ? updatedOrder.dob : prev.dob,
        gender: updatedOrder.gender !== undefined ? updatedOrder.gender : prev.gender,
        address: updatedOrder.address !== undefined ? updatedOrder.address : prev.address,
        employer_name: updatedOrder.employer_name !== undefined ? updatedOrder.employer_name : prev.employer_name,
        icd10_code: updatedOrder.icd10_code !== undefined ? updatedOrder.icd10_code : prev.icd10_code,
        patient_name: updatedOrder.patient_name !== undefined ? updatedOrder.patient_name : prev.patient_name,
      }));

      fetchRecent();
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "Remediation trigger failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleLoadTemplate = (template: any) => {
    const demoId = `DEMO-${template.id}-${Math.floor(1000 + Math.random() * 9000)}`;
    setFormData({
      ...template.data,
      order_id: demoId
    });
    setResult(null); 
    setError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleLoadOrder = (order: any) => {
    // smart lookup: if the loaded claim is a test scenario, find the original erroneous template
    const templateMatch = GOLDEN_TEMPLATES.find(t => order.order_id.includes(t.id));
    if (templateMatch) {
      handleLoadTemplate(templateMatch);
      return;
    }

    setFormData({
      order_id: order.order_id,
      patient_id: order.patient_id || "PAT-100293",
      patient_name: order.patient_name !== undefined ? order.patient_name : "Jane Doe",
      provider_first_name: order.provider_first_name || "John Roster",
      provider_last_name: order.provider_last_name || "Smith",
      provider_state: order.provider_state || "IL",
      provider_taxonomy: order.provider_taxonomy || "Family Medicine",
      npi: order.npi || "",
      payer_id: order.payer_id || "PAYER_A",
      cpt_code: order.cpt_code || "",
      icd10_code: order.icd10_code || "",
      dob: order.dob || "",
      gender: order.gender || "F",
      address: order.address || "",
      employer_name: order.employer_name || "",
      prior_auth_on_file: order.prior_auth_on_file || false,
      timely_filing_days_remaining: order.timely_filing_days_remaining || 15,
    });
    setResult(order);
    setError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "32px", alignItems: "start" }}>
      {/* Column 1: Load Test Scenarios Sidebar */}
      <div style={{ borderRight: "0.5px solid var(--border-color)", paddingRight: "24px" }}>
        <h3 style={{ fontSize: "20px", fontWeight: 600, marginBottom: "24px", letterSpacing: "-0.5px" }}>
          Load Test Scenarios
        </h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxHeight: "calc(100vh - 120px)", overflowY: "auto", paddingRight: "8px" }}>
          {["Clean Baseline", "High-Risk (Auto-Fixable)", "High-Risk (Multi-Defect)", "HITL Gated (Unfixable)"].map((cat) => (
            <div key={cat} style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginTop: "8px" }}>
                {cat}
              </div>
              {GOLDEN_TEMPLATES.filter(t => t.category === cat).map(t => (
                <button
                  key={t.id}
                  onClick={() => handleLoadTemplate(t)}
                  style={{
                    textAlign: "left",
                    padding: "10px 14px",
                    border: "1px solid var(--border-color)",
                    borderRadius: "8px",
                    backgroundColor: "white",
                    cursor: "pointer",
                    fontSize: "13px",
                    lineHeight: "1.5",
                    fontFamily: "var(--font-sans)",
                    transition: "all 0.2s",
                    display: "block",
                    width: "100%"
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "#006039";
                    e.currentTarget.style.backgroundColor = "var(--quest-green-light)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = "var(--border-color)";
                    e.currentTarget.style.backgroundColor = "white";
                  }}
                >
                  <div style={{ fontWeight: 600, color: "var(--text-main)", marginBottom: "2px", fontSize: "13px" }}>{t.title}</div>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", lineHeight: "1.4" }}>{t.description}</div>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Column 2: Main Area (Form + Result + Table) */}
      <div style={{ display: "flex", flexDirection: "column", gap: "32px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "32px", alignItems: "start" }}>
          {/* Intake Form */}
          <div>
            <h2 style={{ fontSize: "20px", fontWeight: 600, marginBottom: "24px", letterSpacing: "-0.5px" }}>
              Intake Order Entry
            </h2>
            
            <form onSubmit={handleSubmit} className="card" style={{ marginBottom: 0 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="order_id">Order ID</label>
                  <input className="form-input" id="order_id" required value={formData.order_id} onChange={handleChange} />
                </div>
                
                <div className="form-group">
                  <label className="form-label" htmlFor="patient_id">Patient ID</label>
                  <input className="form-input" id="patient_id" required value={formData.patient_id} onChange={handleChange} />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="patient_name">Patient Name</label>
                <input className="form-input" id="patient_name" value={formData.patient_name} onChange={handleChange} placeholder="Jane Doe" />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "16px" }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="provider_first_name">Provider Name (First / Last)</label>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <input className="form-input" id="provider_first_name" required placeholder="First" value={formData.provider_first_name} onChange={handleChange} />
                    <input className="form-input" id="provider_last_name" required placeholder="Last" value={formData.provider_last_name} onChange={handleChange} />
                  </div>
                </div>
                
                <div className="form-group">
                  <label className="form-label" htmlFor="provider_state">State</label>
                  <input className="form-input" id="provider_state" required placeholder="IL" value={formData.provider_state} onChange={handleChange} />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="npi">NPI Number</label>
                  <input className="form-input" id="npi" value={formData.npi} onChange={handleChange} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="payer_id">Payer ID</label>
                  <select className="form-select" id="payer_id" value={formData.payer_id} onChange={handleChange}>
                    <option value="PAYER_A">UnitedHealthcare</option>
                    <option value="PAYER_B">Aetna</option>
                    <option value="PAYER_C">Cigna</option>
                    <option value="PAYER_D">Anthem</option>
                    <option value="PAYER_E">Medicare</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="cpt_code">CPT Code</label>
                  <input className="form-input" id="cpt_code" required value={formData.cpt_code} onChange={handleChange} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="icd10_code">ICD-10 Diagnosis</label>
                  <input className="form-input" id="icd10_code" required value={formData.icd10_code} onChange={handleChange} />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="dob">Date of Birth</label>
                  <input className="form-input" id="dob" type="date" value={formData.dob} onChange={handleChange} />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="gender">Gender</label>
                  <select className="form-select" id="gender" value={formData.gender} onChange={handleChange}>
                    <option value="F">Female</option>
                    <option value="M">Male</option>
                    <option value="U">Unspecified</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="address">Patient Address</label>
                <input className="form-input" id="address" value={formData.address} onChange={handleChange} />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="employer_name">Employer Name (Optional)</label>
                <input className="form-input" id="employer_name" value={formData.employer_name} onChange={handleChange} />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", margin: "16px 0 24px 0" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", cursor: "pointer" }}>
                  <input type="checkbox" id="prior_auth_on_file" checked={formData.prior_auth_on_file} onChange={handleChange} />
                  Prior Auth on File
                </label>
                
                <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <label htmlFor="timely_filing_days_remaining" style={{ fontSize: "12px", color: "var(--text-muted)", fontWeight: 500 }}>
                    Timely Filing Days
                  </label>
                  <input 
                    type="number" 
                    id="timely_filing_days_remaining" 
                    className="form-input" 
                    style={{ padding: "6px 12px" }}
                    value={formData.timely_filing_days_remaining} 
                    onChange={handleChange} 
                  />
                </div>
              </div>

              <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%", justifyContent: "center" }}>
                {loading ? "Evaluating Risk..." : "Evaluate Pre-Submission Risk"}
              </button>
            </form>
          </div>

          {/* Validation & Scoring Result */}
          <div>
            <h2 style={{ fontSize: "20px", fontWeight: 600, marginBottom: "24px", letterSpacing: "-0.5px" }}>
              Validation & Scoring Result
            </h2>

            {error && (
              <div className="card" style={{ backgroundColor: "var(--color-warning-bg)", borderColor: "var(--color-warning)", color: "var(--color-warning)" }}>
                <strong>Submission Error:</strong> {error}
              </div>
            )}

            {result ? (
              <div className="card" style={{ marginBottom: 0 }}>
                <div style={{ display: "flex", justifyContent: "between", alignItems: "center", marginBottom: "24px" }}>
                  <div>
                    <span style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
                      Order Risk Score
                    </span>
                    <div style={{ fontSize: "48px", fontWeight: 600, color: result.risk_score >= 0.50 ? "var(--color-warning)" : "var(--color-good)" }}>
                      {(result.risk_score * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div style={{ marginLeft: "auto" }}>
                    <StatusBadge status={result.status} />
                  </div>
                </div>

                <div style={{ borderTop: "0.5px solid var(--border-color)", padding: "16px 0" }}>
                  <div style={{ fontSize: "13px", color: "var(--text-muted)", fontWeight: 500, marginBottom: "12px" }}>
                    DETERMINISTIC REJECT CODES DETECTED
                  </div>
                  
                  {result.reject_codes_detected && result.reject_codes_detected.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {result.reject_codes_detected.map((codeObj: any) => {
                        const code = typeof codeObj === "object" ? codeObj.reject_code : codeObj;
                        const description = REJECT_CODE_DESCRIPTIONS[code] || "Data defect detected.";
                        return (
                          <div 
                            key={code} 
                            style={{ 
                              backgroundColor: "var(--color-warning-bg)", 
                              color: "var(--color-warning)", 
                              border: "0.5px solid var(--color-warning)",
                              padding: "10px 14px",
                              borderRadius: "6px",
                              fontSize: "13px",
                              fontWeight: 500,
                              display: "flex",
                              flexDirection: "column",
                              gap: "2px"
                            }}
                          >
                            <div style={{ fontWeight: 700, fontSize: "11px", textTransform: "uppercase" }}>
                              Code {code}
                            </div>
                            <div style={{ fontSize: "13px" }}>
                              {description}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div style={{ fontSize: "14px", color: "var(--color-good)", fontWeight: 500 }}>
                      ✓ No deterministic coding errors found.
                    </div>
                  )}
                </div>

                <div style={{ borderTop: "0.5px solid var(--border-color)", paddingTop: "24px", marginTop: "16px", display: "flex", justifyContent: "end", gap: "10px" }}>
                  {result.status !== "scored" && (
                    <button 
                      onClick={() => navigate(`/remediation?order_id=${result.order_id}`)}
                      className="btn btn-secondary"
                    >
                      View Audit Trail
                    </button>
                  )}
                  {result.status === "scored" && result.reject_codes_detected && result.reject_codes_detected.length > 0 && (
                    <button 
                      onClick={handleRemediate}
                      className="btn btn-primary"
                      disabled={loading}
                    >
                      {loading ? "Invoking Agents..." : "Trigger Auto-Remediation"}
                    </button>
                  )}
                </div>
                
                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "24px", textAlign: "right" }}>
                  X-Trace-ID: <code>{result.trace_id || "none"}</code>
                </div>
              </div>
            ) : (
              <div className="card" style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "300px", color: "var(--text-muted)", marginBottom: 0 }}>
                Submit an intake order to evaluate pre-submission scoring.
              </div>
            )}
          </div>
        </div>

        {/* Recent Ingested Claims */}
        <div>
          <h3 style={{ fontSize: "14px", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "16px" }}>
            Recent Ingested Claims
          </h3>
          <div className="card">
            <ActivityTable 
              orders={recentOrders} 
              onLoadOrder={handleLoadOrder}
              onAction={async (id) => {
                try {
                  await apiClient.post(`/api/v1/orders/${id}/remediate`);
                  fetchRecent();
                } catch (err) {
                  console.error("Remediation trigger failed:", err);
                }
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
