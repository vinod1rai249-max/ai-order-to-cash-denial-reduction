import React from "react";

interface StatusBadgeProps {
  status: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normalized = (status || "").toLowerCase();
  let className = "badge badge-scored";
  
  if (normalized === "clean") {
    className = "badge badge-clean";
  } else if (normalized === "hitl" || normalized === "denied") {
    className = "badge badge-hitl";
  } else if (normalized === "scored" || normalized === "remediating") {
    className = "badge badge-scored";
  }
  
  return (
    <span className={className}>
      {status || "UNKNOWN"}
    </span>
  );
};
