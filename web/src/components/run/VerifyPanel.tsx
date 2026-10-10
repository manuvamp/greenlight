import { memo } from "react";
import type { VerifyEvent } from "../../types";
import { Icon } from "../Icon";
import { Panel } from "../ui";

const EXPECTED = [
  "baseline tests still pass",
  "target version is installed",
  "upgrade pin kept in manifests",
  "no test files edited",
  "test count did not drop",
  "no newly skipped tests",
  "no errors suppressed",
  "real migration (no compatibility shims)",
];

export const VerifyPanel = memo(function VerifyPanel({ verify, active }: { verify: VerifyEvent | null; active: boolean }) {
  const okCount = verify ? verify.checks.filter((c) => c.ok).length : 0;
  return (
    <Panel
      title="Verification"
      icon="shield"
      className="verify-panel"
      aside={
        verify ? (
          <span className={`verify-score ${verify.passed ? "ok" : "err"}`}>
            {okCount}/{verify.checks.length} {verify.passed ? "passed" : "failed"}
          </span>
        ) : (
          <span className="mono muted-2">anti-cheat</span>
        )
      }
    >
      <ul className="checks">
        {verify
          ? verify.checks.map((c) => {
              const state = c.ok ? "ok" : c.severity === "warn" ? "warn" : "err";
              return (
                <li key={c.name} className={`check check-${state}`}>
                  <span className="check-icon">
                    <Icon name={c.ok ? "check" : state === "warn" ? "alert" : "x"} size={12} stroke={2.6} />
                  </span>
                  <span className="check-name">{c.name}</span>
                  <span className="check-detail mono" title={c.detail}>{c.detail}</span>
                </li>
              );
            })
          : EXPECTED.map((name) => (
              <li key={name} className={`check check-pending${active ? " is-active" : ""}`}>
                <span className="check-icon" />
                <span className="check-name">{name}</span>
                <span className="check-detail mono">{active ? "checking…" : "pending"}</span>
              </li>
            ))}
      </ul>
    </Panel>
  );
});
