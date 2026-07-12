import React, { useEffect, useState } from "react";
import apiClient from "../lib/apiClient";
import { StatusBadge } from "../components/StatusBadge";

export const ReviewQueue: React.FC = () => {
  const [hitlOrders, setHitlOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);

  const fetchQueue = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get("/api/v1/orders?status=hitl");
      setHitlOrders(response.data);
    } catch (err: any) {
      console.error(err);
      setError("Failed to load HITL manual review queue.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, []);

  const handleResolve = async (orderId: string, action: "approve" | "override" | "escalate") => {
    setSuccessMsg(null);
    setError(null);
    setProcessingId(orderId);
    try {
      const response = await apiClient.post(`/api/v1/orders/${orderId}/resolve`, {
        action,
        notes: `${action} via HITL review queue`
      });
      const result = response.data;
      setSuccessMsg(
        `Order ${orderId}: ${result.resolution} (Status: ${result.new_status})`
      );
      setHitlOrders((prev) => prev.filter((o) => o.order_id !== orderId));
    } catch (err: any) {
      console.error(err);
      setError(
        err.response?.data?.detail || `Failed to ${action} order ${orderId}.`
      );
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <h2 style={{ fontSize: "20px", fontWeight: 600, letterSpacing: "-0.5px", margin: 0 }}>
          HITL / Appeals Review Queue
        </h2>
        <button className="btn btn-secondary" onClick={fetchQueue} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh Queue"}
        </button>
      </div>

      {successMsg && (
        <div className="card" style={{ backgroundColor: "var(--color-good-bg)", borderColor: "var(--color-good)", color: "var(--color-good)", padding: "12px", marginBottom: "20px" }}>
          {successMsg}
        </div>
      )}

      {error && (
        <div className="card" style={{ backgroundColor: "var(--color-warning-bg)", borderColor: "var(--color-warning)", color: "var(--color-warning)", padding: "12px", marginBottom: "20px" }}>
          {error}
        </div>
      )}

      <div className="card">
        <div className="card-title">Pending claims requiring human review</div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "32px", color: "var(--text-muted)" }}>
            Loading queue...
          </div>
        ) : hitlOrders.length === 0 ? (
          <div style={{ textAlign: "center", padding: "48px", color: "var(--text-muted)" }}>
            Queue is empty. No claims require manual review.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Payer</th>
                <th>CPT Code</th>
                <th>ICD-10</th>
                <th>Initial Risk</th>
                <th>Status</th>
                <th>Action Gating</th>
              </tr>
            </thead>
            <tbody>
              {hitlOrders.map((order) => {
                const isProcessing = processingId === order.order_id;
                return (
                  <tr key={order.order_id}>
                    <td style={{ fontWeight: 600 }}>{order.order_id}</td>
                    <td>{order.payer_id}</td>
                    <td><code>{order.cpt_code}</code></td>
                    <td><code>{order.icd10_code}</code></td>
                    <td style={{ fontWeight: 600, color: "var(--color-warning)" }}>
                      {(order.risk_score * 100).toFixed(0)}%
                    </td>
                    <td>
                      <StatusBadge status={order.status} />
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          onClick={() => handleResolve(order.order_id, "approve")}
                          className="btn btn-primary"
                          style={{ padding: "6px 12px", fontSize: "12px" }}
                          disabled={isProcessing}
                        >
                          {isProcessing ? "..." : "Approve Patch"}
                        </button>
                        <button
                          onClick={() => handleResolve(order.order_id, "override")}
                          className="btn btn-secondary"
                          style={{ padding: "6px 12px", fontSize: "12px" }}
                          disabled={isProcessing}
                        >
                          Override
                        </button>
                        <button
                          onClick={() => handleResolve(order.order_id, "escalate")}
                          className="btn btn-secondary"
                          style={{ padding: "6px 12px", fontSize: "12px", color: "var(--color-warning)", borderColor: "var(--color-warning)" }}
                          disabled={isProcessing}
                        >
                          Escalate
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
