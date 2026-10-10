import { memo, useMemo, useRef } from "react";
import type { RunEvent } from "../../types";
import { SPEEDS } from "../../run/useRunEvents";
import type { RunPlayback, Speed } from "../../run/useRunEvents";
import { stageLabel } from "../../run/derive";
import { fmtClock } from "../../format";
import { Icon } from "../Icon";

function speedLabel(s: Speed): string {
  return s === "instant" ? "Instant" : `${s}×`;
}

const Markers = memo(function Markers({ all, duration }: { all: RunEvent[]; duration: number }) {
  const marks = useMemo(() => {
    const out: { t: number; label: string; kind: string }[] = [];
    for (const e of all) {
      if (e.type === "stage" && e.status === "start") {
        out.push({ t: e.t, label: stageLabel(e.name), kind: e.name });
      } else if (e.type === "verify") out.push({ t: e.t, label: "Verify", kind: "verify" });
      else if (e.type === "result") out.push({ t: e.t, label: "Result", kind: "result" });
    }
    return out;
  }, [all]);
  if (!duration) return null;
  return (
    <>
      {marks.map((m, i) => (
        <span
          key={i}
          className={`scrub-mark mk-${m.kind}`}
          style={{ left: `${(m.t / duration) * 100}%` }}
          title={`${m.label} · ${fmtClock(m.t)}`}
        />
      ))}
    </>
  );
});

export function PlaybackBar({ pb }: { pb: RunPlayback }) {
  const barRef = useRef<HTMLDivElement>(null);
  const pct = pb.duration > 0 ? Math.min(100, (pb.clock / pb.duration) * 100) : 0;

  const seekFromPointer = (clientX: number) => {
    const el = barRef.current;
    if (!el || !pb.duration) return;
    const r = el.getBoundingClientRect();
    pb.seek(((clientX - r.left) / r.width) * pb.duration);
  };

  if (pb.source.kind === "live") {
    return (
      <div className="playback is-live">
        <span className={`live-badge${pb.ended ? " is-ended" : ""}`}>
          <span className="live-dot" /> {pb.ended ? "Finished" : "Live"}
        </span>
        <span className="mono muted">{pb.total} events streamed</span>
        <span className="playback-time mono">{fmtClock(pb.clock)}</span>
      </div>
    );
  }

  return (
    <div className="playback">
      <div className="pb-buttons">
        <button
          className="pb-btn pb-main"
          onClick={pb.toggle}
          aria-label={pb.playing ? "Pause" : pb.ended ? "Replay" : "Play"}
          title={pb.playing ? "Pause (space)" : "Play (space)"}
        >
          <Icon name={pb.playing ? "pause" : "play"} size={15} />
        </button>
        <button className="pb-btn" onClick={pb.restart} aria-label="Restart" title="Restart (R)">
          <Icon name="restart" size={15} />
        </button>
      </div>
      <div className="seg" role="radiogroup" aria-label="playback speed">
        {SPEEDS.map((s) => (
          <button
            key={String(s)}
            role="radio"
            aria-checked={pb.speed === s}
            className={`seg-btn${pb.speed === s ? " is-on" : ""}`}
            onClick={() => pb.setSpeed(s)}
          >
            {speedLabel(s)}
          </button>
        ))}
      </div>
      <div
        className="scrub"
        ref={barRef}
        onPointerDown={(e) => {
          (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
          seekFromPointer(e.clientX);
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) seekFromPointer(e.clientX);
        }}
        role="slider"
        aria-label="replay position"
        aria-valuemin={0}
        aria-valuemax={Math.round(pb.duration)}
        aria-valuenow={Math.round(pb.clock)}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") pb.seek(pb.clock + 5);
          if (e.key === "ArrowLeft") pb.seek(pb.clock - 5);
        }}
      >
        <div className="scrub-track">
          <div className="scrub-fill" style={{ width: `${pct}%` }} />
          <Markers all={pb.all} duration={pb.duration} />
        </div>
        <div className="scrub-thumb" style={{ left: `${pct}%` }} />
      </div>
      <span className="playback-time mono">
        {fmtClock(pb.clock)} <span className="muted-2">/ {fmtClock(pb.duration)}</span>
      </span>
    </div>
  );
}
