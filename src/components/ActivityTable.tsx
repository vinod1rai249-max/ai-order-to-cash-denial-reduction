import React from "react";
import { Link } from "react-router-dom";
import { StatusBadge } from "./StatusBadge";

export interface OrderItem {
  order_id: string;
  claim_id?: string;
  payer_id: string;
  cpt_code: string;
  icd10_code: string;
  risk_score: number;
  status: string;
}

interface ActivityTableProps {
  orders: any[];
  onAction?: (orderId: string) => void;
  actionLabel?: string;
  onLoadOrder?: (order: any) => void;
}

export const ActivityTable: React.FC<ActivityTableProps> = ({ 
  orders, 
  onAction, 
  actionLabel = "Remediate",
  onLoadOrder
}) => {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Order ID</th>
            <th>Payer</th>
            <th>CPT</th>
            <th>ICD-10</th>
            <th>Risk Score</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {orders.length === 0 ? (
            <tr>
              <td colSpan={7} style={{ textAlign: "center", color: "var(--text-muted)", padding: "32px" }}>
                No recent activity.
              </td>
            </tr>
          ) : (
            orders.map((order) => (
              <tr key={order.order_id}>
                <td style={{ fontWeight: 600 }}>
                  {order.remediation_attempts && order.remediation_attempts > 0 ? (
                    <Link 
                      to={`/remediation?order_id=${order.order_id}`}
                      style={{ color: "inherit", textDecoration: "none" }}
                      className="hover-link"
                    >
                      {order.order_id}
                    </Link>
                  ) : (
                    <span>{order.order_id}</span>
                  )}
                </td>
                <td>{order.payer_id}</td>
                <td><code>{order.cpt_code}</code></td>
                <td><code>{order.icd10_code}</code></td>
                <td style={{ fontWeight: 500 }}>
                  {(order.risk_score * 100).toFixed(0)}%
                </td>
                <td>
                  <StatusBadge status={order.status} />
                </td>
                <td>
                  <div style={{ display: "flex", gap: "8px" }}>
                    {onLoadOrder && (
                      <button 
                        onClick={() => onLoadOrder(order)}
                        className="btn btn-secondary"
                        style={{ padding: "6px 12px", fontSize: "12px" }}
                      >
                        Load Claim
                      </button>
                    )}
                    {order.status === "scored" && onAction && (
                      <button 
                        onClick={() => onAction(order.order_id)}
                        className="btn btn-primary"
                        style={{ padding: "6px 12px", fontSize: "12px" }}
                      >
                        {actionLabel}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};
