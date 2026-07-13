import React, { useEffect, useState } from "react";
import apiClient from "../lib/apiClient";
import { MetricCard } from "../components/MetricCard";
import { ActivityTable } from "../components/ActivityTable";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const AGENT_LABELS: Record<string, string> = {
  npi: "NPI Lookup",
  icd10_code: "ICD-10 Crosswalk",
  address: "Address Standardization",
  payer_id: "COB Re-sequencing",
  dob: "DOB/Gender Fix",
  gender: "DOB/Gender Fix",
  employer_name: "Employer Lookup",
  patient_id: "Patient MPI Match",
  patient_name: "Patient Info Restore",
};

const BAR_COLORS = [
  "#006039", "#008752", "#00a86b", "#33b584", "#66c39d",
  "#99d2b6", "#cce0cf", "#3b82f6", "#ef4444"
];

function computeDashboardStats(orders: any[]) {
  const total = orders.length;
  const cleanList = orders.filter((o: any) => o.status === "clean");
  const hitlList = orders.filter((o: any) => o.status === "hitl" || o.status === "escalated");
  const scoredList = orders.filter((o: any) => o.status === "scored");

  const fixedCount = cleanList.length;
  const escalatedCount = hitlList.length;
  const pendingCount = scoredList.length;

  return { total, fixedCount, escalatedCount, pendingCount };
}

function computeRemediationDistribution(orders: any[]) {
  const counts: Record<string, number> = {
    "NPI Lookup": 0,
    "ICD-10 Crosswalk": 0,
    "Address Standardization": 0,
    "COB Re-sequencing": 0,
    "DOB/Gender Fix": 0,
    "Employer Lookup": 0,
    "Patient MPI Match": 0,
    "Patient Info Restore": 0,
    "HITL Queue Gated": 0,
  };

  // Count HITL/escalated orders directly from their database status
  const hitlOrders = orders.filter((o: any) => o.status === "hitl" || o.status === "escalated");
  counts["HITL Queue Gated"] = hitlOrders.length;

  for (const order of orders) {
    let history = order.risk_history;
    if (!history) continue;
    if (typeof history === "string") {
      try { history = JSON.parse(history); } catch { continue; }
    }
    if (!Array.isArray(history)) continue;

    const countedLabelsForOrder = new Set<string>();

    for (const entry of history) {
      const patches: string[] = entry.patches || [];
      for (const patch of patches) {
        for (const [field, label] of Object.entries(AGENT_LABELS)) {
          if (
            (patch.toLowerCase().includes(field.toLowerCase().replace("_", " ")) ||
             patch.toLowerCase().includes(label.toLowerCase())) &&
            !countedLabelsForOrder.has(label)
          ) {
            counts[label]++;
            countedLabelsForOrder.add(label);
            break;
          }
        }
      }
    }
  }

  // Filter out categories with 0 count to show only active metrics
  const activeEntries = Object.entries(counts)
    .filter(([, count]) => count > 0)
    .sort(([, a], [, b]) => b - a);

  const totalActions = activeEntries.reduce((sum, [, count]) => sum + count, 0);

  return activeEntries.map(([label, count]) => ({
    label,
    count,
    pct: totalActions > 0 ? Math.round((count / totalActions) * 100) : 0,
  }));
}

export const ManagerDashboard: React.FC = () => {
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    total: 0, fixedCount: 0, escalatedCount: 0, pendingCount: 0,
  });
  const [distribution, setDistribution] = useState<{ label: string; count: number; pct: number }[]>([]);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get("/api/v1/orders");
      const list = response.data;
      setOrders(list);

      const computed = computeDashboardStats(list);
      setStats({
        total: computed.total,
        fixedCount: computed.fixedCount,
        escalatedCount: computed.escalatedCount,
        pendingCount: computed.pendingCount,
      });

      setDistribution(computeRemediationDistribution(list));
    } catch (err: any) {
      console.error(err);
      setError("Failed to fetch executive dashboard metrics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
        <h2 style={{ fontSize: "24px", fontWeight: 600, letterSpacing: "-0.75px" }}>
          Executive Performance Dashboard
        </h2>
        <button className="btn btn-secondary" onClick={fetchDashboardData} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh Report"}
        </button>
      </div>

      {error && (
        <div className="card" style={{ backgroundColor: "var(--color-warning-bg)", borderColor: "var(--color-warning)", color: "var(--color-warning)", padding: "12px", marginBottom: "24px" }}>
          {error}
        </div>
      )}

      {/* Metric Cards Row */}
      <div className="metric-grid">
        <MetricCard
          label="Total Claims Processed"
          value={stats.total}
          subtext={`${stats.pendingCount} pending remediation`}
          trend="neutral"
        />
        <MetricCard
          label="Auto-Remediated Claims"
          value={stats.fixedCount}
          subtext={stats.total > 0 ? `${Math.round((stats.fixedCount / stats.total) * 100)}% auto-fix rate` : "No claims yet"}
          trend="up"
        />
        <MetricCard
          label="Escalated to HITL Queue"
          value={stats.escalatedCount}
          subtext={stats.total > 0 ? `${Math.round((stats.escalatedCount / stats.total) * 100)}% escalation rate` : "No claims yet"}
          trend={stats.escalatedCount > 5 ? "down" : "neutral"}
        />
      </div>

      {/* Chart and Distribution Section */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "32px", marginBottom: "32px" }}>
        <div className="card">
          <div className="card-title">Remediation & Routing Statistics</div>
          {distribution.length > 0 ? (
            <div style={{ width: "100%", height: "260px" }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distribution} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis dataKey="label" stroke="var(--text-muted)" fontSize={10} tickLine={false} />
                  <YAxis stroke="var(--text-muted)" fontSize={11} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#006039" radius={[4, 4, 0, 0]}>
                    {distribution.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={BAR_COLORS[index % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "48px", color: "var(--text-muted)" }}>
              No remediation data available yet. Process orders to populate.
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-title">Remediation Distribution</div>
          {distribution.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px", fontSize: "14px", marginTop: "12px" }}>
              {distribution.map((item, idx) => (
                <div key={item.label} style={{ display: "flex", flexDirection: "column", gap: "4px", borderBottom: idx < distribution.length - 1 ? "0.5px solid var(--border-color)" : "none", paddingBottom: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--text-muted)" }}>{item.label}</span>
                    <strong style={{ color: "var(--text-main)" }}>{item.pct}%</strong>
                  </div>
                  <div style={{ height: "4px", backgroundColor: "var(--color-neutral-bg)", borderRadius: "2px" }}>
                    <div style={{ height: "100%", width: `${item.pct}%`, backgroundColor: BAR_COLORS[idx % BAR_COLORS.length], borderRadius: "2px" }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "32px", color: "var(--text-muted)", fontSize: "13px" }}>
              No remediation data yet. Run auto-remediation on orders to populate.
            </div>
          )}
        </div>
      </div>

      {/* Recent Activity Table */}
      <div className="card">
        <div className="card-title">Audited Order Queue</div>
        {loading ? (
          <div style={{ textAlign: "center", padding: "24px" }}>Retrieving orders list...</div>
        ) : (
          <ActivityTable
            orders={orders.filter((o: any) => o.status !== "clean").slice(0, 3)}
            onAction={async (id) => {
              try {
                await apiClient.post(`/api/v1/orders/${id}/remediate`);
                fetchDashboardData();
              } catch (err) {
                console.error("Manual remediation trigger failed:", err);
              }
            }}
          />
        )}
      </div>
    </div>
  );
};
