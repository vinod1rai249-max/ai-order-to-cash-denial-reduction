import React from "react";

export interface HistoryEvent {
  attempt: number;
  risk_score: number;
  reject_codes_detected: any[];
  patches?: string[];
  timestamp: string;
  hitl_required?: boolean;
  status?: string;
}

interface RemediationTimelineProps {
  history: HistoryEvent[];
}

export const RemediationTimeline: React.FC<RemediationTimelineProps> = ({ history }) => {
  if (!history || history.length === 0) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "14px", padding: "16px 0" }}>
        No remediation trail registered. The order is waiting to trigger the remediation loop.
      </div>
    );
  }
  
  return (
    <div className="timeline">
      {history.map((event, idx) => {
        // Handle both list of strings or list of dicts for detected codes
        const codes = (event.reject_codes_detected || []).map(
          (c) => (typeof c === "object" && c !== null) ? c.reject_code : c
        );
        const hasCodes = codes.length > 0;
        
        // Determine header title based on status and non-fixable codes
        const nonFixableCodes = ["13", "32", "33", "45", "52"];
        const hasNonFixable = codes.some((c) => nonFixableCodes.includes(c));
        const isHitl = event.hitl_required || event.status === "hitl" || hasNonFixable;
        
        let title = "Order Cleared";
        if (isHitl) {
          title = "Unfixable Errors - Routed to HITL Queue";
        } else if (hasCodes) {
          title = "Deterministic Errors Corrected";
        }
        
        return (
          <div className="timeline-event" key={idx}>
            <div className={`timeline-marker ${isHitl ? "failed" : hasCodes ? "failed" : "resolved"}`}></div>
            <div className="timeline-header">
              <span className="timeline-title">
                Remediation Pass #{event.attempt} - {title}
              </span>
              <span className="timeline-time">
                {new Date(event.timestamp).toLocaleTimeString()}
              </span>
            </div>
            <div className="timeline-body">
              <p style={{ margin: "4px 0" }}>
                Re-computed Denial Risk: <strong style={{ color: event.risk_score >= 0.5 ? "var(--color-warning)" : "var(--color-good)" }}>
                  {(event.risk_score * 100).toFixed(0)}%
                </strong>
              </p>
              
              {event.patches && event.patches.length > 0 && (
                <div style={{ marginTop: "8px", padding: "8px 12px", backgroundColor: "var(--color-neutral-bg)", borderRadius: "4px", border: "0.5px solid var(--border-color)", marginBottom: "8px" }}>
                  <div style={{ fontSize: "10px", fontWeight: 600, color: "var(--text-muted)", marginBottom: "4px", textTransform: "uppercase" }}>
                    Audited Patches Applied:
                  </div>
                  <ul style={{ listStyleType: "disc", paddingLeft: "16px", fontSize: "12px", color: "var(--text-main)", display: "flex", flexDirection: "column", gap: "2px" }}>
                    {event.patches.map((patch: string, pIdx: number) => (
                      <li key={pIdx}>{patch}</li>
                    ))}
                  </ul>
                </div>
              )}

              {hasCodes ? (
                <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  Remediated reject codes: <span style={{ color: "var(--color-warning)", fontWeight: 600 }}>{codes.join(", ")}</span>. Re-submitting to the risk validation engine...
                </p>
              ) : (
                <p style={{ fontSize: "12px", color: "var(--color-good)", fontWeight: 600 }}>
                  ✓ Order verified clean. Ready to submit to the claims department.
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};
