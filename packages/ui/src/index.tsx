import type { ReactNode } from "react";

type PillProps = {
  children: ReactNode;
  tone?: "default" | "success";
};

/** Pure presentational component; no business/verification claims. */
export function Pill({ children, tone = "default" }: PillProps) {
  return (
    <span className={`pill ${tone === "success" ? "pill-success" : ""}`}>
      {children}
    </span>
  );
}
