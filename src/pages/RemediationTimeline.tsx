import React, { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import apiClient from "../lib/apiClient";
import { RemediationTimeline as TimelineComponent } from "../components/RemediationTimeline";

export const RemediationTimeline: React.FC = () => {
  const [searchParams] = useSearchParams();
  const orderIdParam = searchParams.get("order_id") || "";
  const [orderId, setOrderId] = useState(orderIdParam);
  const [history, setHistory] = useState<any[]>([]);
  const [order, setOrder] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleResolveOrder = async (action: "approve" | "override" | "escalate") => {
    if (!orderIdParam) return;
    setResolving(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const response = await apiClient.post(`/api/v1/orders/${orderIdParam}/resolve`, {
        action,
        notes: `${action} via audit timeline manual action`
      });
      const result = response.data;
      setSuccessMsg(`Order successfully resolved: ${result.resolution} (New Status: ${result.new_status})`);
      fetchHistory(orderIdParam);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || `Failed to ${action} order.`);
    } finally {
      setResolving(false);
    }
  };

  const fetchHistory = async (targetId: string) => {
    if (!targetId) return;
    setLoading(true);
    setError(null);
    try {
      const [historyRes, orderRes] = await Promise.all([
        apiClient.get(`/api/v1/orders/${targetId}/risk-history`),
        apiClient.get(`/api/v1/orders/${targetId}`)
      ]);
      setHistory(historyRes.data);
      setOrder(orderRes.data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || `Failed to fetch history for order ${targetId}`);
      setHistory([]);
      setOrder(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (orderIdParam) {
      setOrderId(orderIdParam);
      fetchHistory(orderIdParam);
    }
  }, [orderIdParam]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchHistory(orderId);
  };

  return (
    <div>
      <h2 style={{ fontSize: "20px", fontWeight: 600, marginBottom: "24px", letterSpacing: "-0.5px" }}>
        Remediation Audit Trail
      </h2>

      <div className="card">
        <form onSubmit={handleSearchSubmit} style={{ display: "flex", gap: "16px", alignItems: "end" }}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label className="form-label" htmlFor="order_id_search">Order ID / Claim ID</label>
            <input
              id="order_id_search"
              className="form-input"
              value={orderId}
              onChange={(e) => setOrderId(e.target.value)}
              placeholder="e.g. ORD-123456"
              required
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? "Searching..." : "View Timeline"}
          </button>
        </form>
      </div>

      {error && (
        <div className="card" style={{ backgroundColor: "var(--color-warning-bg)", borderColor: "var(--color-warning)", color: "var(--color-warning)" }}>
          {error}
        </div>
      )}

      {successMsg && (
        <div className="card" style={{ backgroundColor: "var(--color-good-bg)", borderColor: "var(--color-good)", color: "var(--color-good)" }}>
          {successMsg}
        </div>
      )}

      {orderIdParam && !loading && !error && history.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: "48px", color: "var(--text-muted)" }}>
          No remediation events have been recorded for this order yet.
        </div>
      )}

      {(history.length > 0 || loading) && (
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "32px" }}>
          <div className="card">
            <div className="card-title">Remediation Timeline</div>
            {loading ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div style={{ height: "40px", backgroundColor: "var(--color-neutral-bg)", borderRadius: "4px" }}></div>
                <div style={{ height: "40px", backgroundColor: "var(--color-neutral-bg)", borderRadius: "4px" }}></div>
              </div>
            ) : (
              <TimelineComponent history={history} />
            )}
          </div>
          <div>
            <div className="card">
              <div className="card-title">Audit Metadata</div>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px", fontSize: "14px" }}>
                <div>
                  <div style={{ color: "var(--text-muted)", fontSize: "12px", fontWeight: 500 }}>ORDER REFERENCE</div>
                  <div style={{ fontWeight: 600 }}>{orderIdParam}</div>
                </div>
                <div>
                  <div style={{ color: "var(--text-muted)", fontSize: "12px", fontWeight: 500 }}>REMEDIATION PASSES</div>
                  <div style={{ fontWeight: 600 }}>{history.length} attempts</div>
                </div>
                <div>
                  <div style={{ color: "var(--text-muted)", fontSize: "12px", fontWeight: 500 }}>AUDIT COMPLIANCE</div>
                  <div style={{ color: "var(--color-good)", fontWeight: 600 }}>✓ Deterministic Trace Logged</div>
                </div>
              </div>
            </div>

            {order && (order.status === "hitl" || order.hitl_required) && (
              <div className="card" style={{ border: "1px solid var(--color-warning)", backgroundColor: "var(--color-neutral-bg)", marginTop: "24px" }}>
                <div className="card-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                  <span style={{ fontSize: "14px", fontWeight: 700 }}>⚠️ Human Review Required</span>
                  <Link to="/hitl" style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-primary)", textDecoration: "underline" }}>
                    Go to HITL Queue →
                  </Link>
                </div>
                <p style={{ fontSize: "12px", margin: "0 0 16px 0", color: "var(--text-muted)", lineHeight: "1.4" }}>
                  This order contains non-fixable errors or failed all automated remediation passes. Please select an action to resolve this claim:
                </p>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                  <button
                    onClick={() => handleResolveOrder("approve")}
                    className="btn btn-primary"
                    style={{ padding: "6px 12px", fontSize: "12px", flex: "1 1 auto" }}
                    disabled={resolving}
                  >
                    {resolving ? "..." : "Approve Patch"}
                  </button>
                  <button
                    onClick={() => handleResolveOrder("override")}
                    className="btn btn-secondary"
                    style={{ padding: "6px 12px", fontSize: "12px", flex: "1 1 auto" }}
                    disabled={resolving}
                  >
                    Override
                  </button>
                  <button
                    onClick={() => handleResolveOrder("escalate")}
                    className="btn btn-secondary"
                    style={{ padding: "6px 12px", fontSize: "12px", color: "var(--color-warning)", borderColor: "var(--color-warning)", flex: "1 1 auto" }}
                    disabled={resolving}
                  >
                    Escalate
                  </button>
                </div>
              </div>
            )}

            {order && (
              <div className="card" style={{ marginTop: "24px" }}>
                <div className="card-title">Current Patched Details</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "13px" }}>
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: "11px", fontWeight: 500, textTransform: "uppercase" }}>NPI Number</div>
                    <div style={{ fontWeight: 600, fontFamily: "monospace" }}>{order.npi || "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: "11px", fontWeight: 500, textTransform: "uppercase" }}>Patient Name</div>
                    <div style={{ fontWeight: 600 }}>{order.patient_name || "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: "11px", fontWeight: 500, textTransform: "uppercase" }}>Date of Birth</div>
                    <div style={{ fontWeight: 600 }}>{order.dob || "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: "11px", fontWeight: 500, textTransform: "uppercase" }}>Gender</div>
                    <div style={{ fontWeight: 600 }}>{order.gender || "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: "11px", fontWeight: 500, textTransform: "uppercase" }}>Patient Address</div>
                    <div style={{ fontWeight: 600, fontSize: "12px" }}>{order.address || "—"}</div>
                  </div>
                  <div>
                    <div style={{ color: "var(--text-muted)", fontSize: "11px", fontWeight: 500, textTransform: "uppercase" }}>ICD-10 Diagnosis</div>
                    <div style={{ fontWeight: 600, fontFamily: "monospace" }}>{order.icd10_code || "—"}</div>
                  </div>
                  {order.employer_name && (
                    <div>
                      <div style={{ color: "var(--text-muted)", fontSize: "11px", fontWeight: 500, textTransform: "uppercase" }}>Employer Name</div>
                      <div style={{ fontWeight: 600 }}>{order.employer_name}</div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
