import React from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  trend?: "up" | "down" | "neutral";
}

export const MetricCard: React.FC<MetricCardProps> = ({ 
  label, 
  value, 
  subtext, 
  trend 
}) => {
  let trendColor = "var(--text-muted)";
  if (trend === "up") trendColor = "var(--color-good)";
  if (trend === "down") trendColor = "var(--color-warning)";

  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {subtext && (
        <div 
          style={{ 
            fontSize: "12px", 
            color: trendColor, 
            marginTop: "8px",
            fontWeight: 500
          }}
        >
          {subtext}
        </div>
      )}
    </div>
  );
};
