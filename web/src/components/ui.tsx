import type { ReactNode } from "react";
import { Icon } from "./Icon";
import type { IconName } from "./Icon";

export type PillStatus = "green" | "partial" | "failed" | "error" | "noop" | "running" | "pending" | string;

const PILL_TEXT: Record<string, string> = {
  green: "Green",
  partial: "Partial",
  failed: "Failed",
  error: "Error",
  noop: "No-op",
  running: "Running",
  pending: "Waiting",
};

export function pillTone(status: PillStatus | null | undefined): string {
  switch (status) {
    case "green": return "ok";
    case "partial": return "warn";
    case "failed":
    case "error": return "err";
    case "running": return "run";
    default: return "muted";
  }
}

export function StatusPill({ status, size = "md" }: { status: PillStatus | null | undefined; size?: "sm" | "md" | "lg" }) {
  const s = status ?? "pending";
  const tone = pillTone(s);
  return (
    <span className={`pill pill-${tone} pill-${size}`}>
      <span className="pill-dot" />
      {PILL_TEXT[s] ?? (s.startsWith("precheck") ? "Precheck" : s)}
    </span>
  );
}

export function Panel({
  title, icon, aside, children, className = "", bodyClass = "", id,
}: {
  title: ReactNode;
  icon?: IconName;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
  id?: string;
}) {
  return (
    <section className={`panel ${className}`} id={id}>
      <header className="panel-head">
        <h2 className="panel-title">
          {icon && <Icon name={icon} size={15} />}
          {title}
        </h2>
        {aside && <div className="panel-aside">{aside}</div>}
      </header>
      <div className={`panel-body ${bodyClass}`}>{children}</div>
    </section>
  );
}

export function Empty({ icon = "info", title, children }: { icon?: IconName; title: ReactNode; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon"><Icon name={icon} size={18} /></div>
      <div className="empty-title">{title}</div>
      {children && <div className="empty-text">{children}</div>}
    </div>
  );
}

export function Skeleton({ h = 14, w = "100%", r = 6 }: { h?: number; w?: number | string; r?: number }) {
  return <span className="skeleton" style={{ height: h, width: w, borderRadius: r }} />;
}

export function Chip({ children, tone = "default", mono = false, title }: { children: ReactNode; tone?: string; mono?: boolean; title?: string }) {
  return <span className={`chip chip-${tone}${mono ? " mono" : ""}`} title={title}>{children}</span>;
}

export function ErrorBox({ title, children, action }: { title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="errorbox">
      <div className="errorbox-icon"><Icon name="alert" size={18} /></div>
      <div className="errorbox-main">
        <div className="errorbox-title">{title}</div>
        {children && <div className="errorbox-text">{children}</div>}
        {action && <div className="errorbox-action">{action}</div>}
      </div>
    </div>
  );
}

export function LibVersions({ lib, from, to, toMajor }: { lib: string | null | undefined; from?: string | null; to?: string | null; toMajor?: number | null }) {
  return (
    <span className="libver mono">
      <span className="libver-lib">{lib ?? "?"}</span>
      <span className="libver-from">{from ?? "current"}</span>
      <Icon name="arrowRight" size={13} className="libver-arrow" />
      <span className="libver-to">{to ?? (toMajor != null ? `${toMajor}.x` : "next")}</span>
    </span>
  );
}
