import { memo } from "react";
import type { Meter, TestPoint } from "../../run/derive";
import { Panel } from "../ui";

const R = 74;
const C = 2 * Math.PI * R;

const STATE_TEXT: Record<Meter["state"], string> = {
  idle: "waiting for baseline",
  green: "all passing",
  red: "failing",
  partial: "climbing back",
  "import-error": "import error",
};

const LABEL_TEXT: Record<string, string> = {
  baseline: "Baseline",
  "after bump": "After bump",
  fix: "Fix run",
  selected: "Selected",
};

function Ring({ meter }: { meter: Meter }) {
  const ratio = meter.total > 0 ? meter.passed / meter.total : 0;
  const greenLen = meter.state === "idle" ? 0 : ratio * C;
  const redLen = meter.state === "idle" ? 0 : C - greenLen;
  return (
    <div className={`ring ring-${meter.state}`}>
      <svg viewBox="0 0 180 180" className="ring-svg">
        <defs>
          <linearGradient id="ring-green" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#7cf5b0" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
          <pattern id="ring-stripes" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" fill="#f04a4a" />
            <rect width="3.5" height="8" fill="#b92a2a" />
          </pattern>
        </defs>
        <circle cx="90" cy="90" r={R} className="ring-track" />
        <circle
          cx="90" cy="90" r={R}
          className="ring-red"
          stroke={meter.state === "import-error" ? "url(#ring-stripes)" : undefined}
          strokeDasharray={`${redLen} ${C}`}
          strokeDashoffset={-greenLen}
          transform="rotate(-90 90 90)"
        />
        <circle
          cx="90" cy="90" r={R}
          className="ring-green"
          strokeDasharray={`${greenLen} ${C}`}
          transform="rotate(-90 90 90)"
        />
      </svg>
      <div className="ring-center">
        {meter.state === "idle" ? (
          <span className="ring-idle">—</span>
        ) : (
          <>
            <span className="ring-num mono">
              {meter.passed}
              <span className="ring-den">/{meter.total}</span>
            </span>
            <span className="ring-cap">{meter.state === "import-error" ? "import error" : "tests pass"}</span>
          </>
        )}
      </div>
    </div>
  );
}

function Sparkline({ points }: { points: TestPoint[] }) {
  const W = 260;
  const H = 64;
  const pad = 7;
  if (points.length === 0) return <div className="spark spark-empty">test runs appear here</div>;
  const n = points.length;
  const xs = (i: number) => (n === 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (n - 1));
  const ys = (p: TestPoint) => {
    const r = p.total > 0 ? p.passed / p.total : 0;
    return H - pad - r * (H - 2 * pad);
  };
  const line = points.map((p, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(p).toFixed(1)}`).join(" ");
  const area = `${line} L${xs(n - 1).toFixed(1)},${H - pad} L${xs(0).toFixed(1)},${H - pad} Z`;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="passed tests per run">
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(61,220,132,0.28)" />
          <stop offset="100%" stopColor="rgba(61,220,132,0)" />
        </linearGradient>
      </defs>
      <line x1={pad} x2={W - pad} y1={pad} y2={pad} className="spark-grid" />
      <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="spark-grid" />
      {n > 1 && <path d={area} fill="url(#spark-fill)" />}
      {n > 1 && <path d={line} className="spark-line" vectorEffect="non-scaling-stroke" />}
      {points.map((p, i) => (
        <circle key={p.seq} cx={xs(i)} cy={ys(p)} r={3.2} className={`spark-dot dot-${p.state}`} vectorEffect="non-scaling-stroke">
          <title>{`${p.label}: ${p.summary}`}</title>
        </circle>
      ))}
    </svg>
  );
}

function Cells({ meter }: { meter: Meter }) {
  const total = meter.state === "idle" ? 0 : meter.total;
  const shown = Math.min(total, 120);
  const scale = total > 0 ? shown / total : 1;
  const greenCells = Math.round(meter.passed * scale);
  return (
    <div className="cells" aria-hidden="true">
      {Array.from({ length: shown }, (_, i) => (
        <span
          key={i}
          className={`cell ${i < greenCells ? "cell-ok" : "cell-bad"}${meter.state === "import-error" ? " cell-import" : ""}`}
          style={{ transitionDelay: `${i * 14}ms` }}
        />
      ))}
    </div>
  );
}

export const TestMeter = memo(function TestMeter({ meter, history, baselineTotal }: { meter: Meter; history: TestPoint[]; baselineTotal: number | null }) {
  const last = history[history.length - 1];
  return (
    <Panel
      title="Test suite"
      icon="flask"
      className={`meter-panel meter-${meter.state}`}
      aside={meter.state !== "idle" && <span className={`meter-tag tag-${meter.state}`}>{LABEL_TEXT[meter.label] ?? meter.label}</span>}
    >
      <div className="meter">
        <Ring meter={meter} />
        <div className="meter-side">
          <div className={`meter-state st-${meter.state}`}>{STATE_TEXT[meter.state]}</div>
          <div className="meter-summary mono">{last ? last.summary : baselineTotal == null ? "cloning and installing…" : ""}</div>
          <Cells meter={meter} />
          <div className="meter-spark-head">
            <span>History</span>
            <span className="mono">{history.length} {history.length === 1 ? "run" : "runs"}</span>
          </div>
          <Sparkline points={history} />
        </div>
      </div>
    </Panel>
  );
});
