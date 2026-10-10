// Replay engine + live stream in one hook.
//
// Replay: fetch the recorded events, then advance a playhead clock with requestAnimationFrame and
// expose the events whose `t` is behind it. Seeking/instant just move the clock.
// Live: subscribe to the SSE stream and append events as they arrive (deduped by seq, because
// EventSource reconnects and the server replays from the start).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, isEvent } from "../api";
import type { RunEvent } from "../types";

export type RunSource = { kind: "replay"; id: string } | { kind: "live"; runId: string };
export type Speed = 1 | 4 | 8 | 16 | "instant";
export const SPEEDS: Speed[] = [1, 4, 8, 16, "instant"];

export type LoadState = "loading" | "ready" | "error";

export interface RunPlayback {
  source: RunSource;
  events: RunEvent[];
  total: number;
  loadState: LoadState;
  error: string | null;
  playing: boolean;
  ended: boolean;
  speed: Speed;
  clock: number;
  duration: number;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  restart: () => void;
  seek: (t: number) => void;
  setSpeed: (s: Speed) => void;
}

/** Number of events with t <= clock (events are sorted by seq; t is non-decreasing). */
function countUpTo(events: RunEvent[], clock: number): number {
  let lo = 0;
  let hi = events.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (events[mid].t <= clock) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

export function parseSpeed(v: string | null | undefined): Speed | null {
  if (!v) return null;
  if (v === "instant" || v === "max") return "instant";
  const n = Number(v.replace(/x$/i, ""));
  return (SPEEDS as (number | string)[]).includes(n) ? (n as Speed) : null;
}

export function useRunEvents(source: RunSource, initialSpeed: Speed = 8): RunPlayback {
  const [all, setAll] = useState<RunEvent[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);
  const [speed, setSpeedState] = useState<Speed>(initialSpeed);
  const [playing, setPlaying] = useState(true);
  const [clock, setClock] = useState(0);
  const clockRef = useRef(0);
  const liveAnchor = useRef<{ t: number; at: number } | null>(null);
  const isReplay = source.kind === "replay";
  const key = source.kind === "replay" ? `r:${source.id}` : `l:${source.runId}`;

  const duration = useMemo(() => (all.length ? all[all.length - 1].t : 0), [all]);
  const liveDone = !isReplay && all.length > 0 && all[all.length - 1].type === "result";

  // ---------- load ----------
  useEffect(() => {
    let cancelled = false;
    setAll([]);
    setError(null);
    setLoadState("loading");
    clockRef.current = 0;
    setClock(0);
    liveAnchor.current = null;

    if (source.kind === "replay") {
      api
        .replay(source.id)
        .then((events) => {
          if (cancelled) return;
          if (!events.length) throw new Error("This replay has no events.");
          setAll(events);
          setLoadState("ready");
          if (initialSpeed === "instant") {
            const end = events[events.length - 1].t;
            clockRef.current = end;
            setClock(end);
            setPlaying(false);
          } else {
            setPlaying(true);
          }
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : String(err));
          setLoadState("error");
        });
      return () => {
        cancelled = true;
      };
    }

    const es = new EventSource(api.streamUrl(source.runId));
    let gotResult = false;
    let gotAny = false;
    es.onmessage = (msg) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(msg.data);
      } catch {
        return;
      }
      if (!isEvent(parsed)) return;
      const ev = parsed;
      gotAny = true;
      setLoadState("ready");
      liveAnchor.current = { t: ev.t, at: performance.now() };
      setAll((prev) => {
        if (prev.length && prev[prev.length - 1].seq >= ev.seq) {
          if (prev.some((p) => p.seq === ev.seq)) return prev;
          return [...prev, ev].sort((a, b) => a.seq - b.seq);
        }
        return [...prev, ev];
      });
      if (ev.type === "result") {
        gotResult = true;
        es.close();
      }
    };
    es.onerror = () => {
      if (gotResult) return;
      if (es.readyState === EventSource.CLOSED) {
        setError(gotAny ? "The live stream was interrupted." : "No such live run, or the server is unreachable.");
        setLoadState("error");
      }
    };
    return () => {
      cancelled = true;
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // ---------- replay clock ----------
  useEffect(() => {
    if (!isReplay || loadState !== "ready" || !playing || speed === "instant") return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.25, (now - last) / 1000);
      last = now;
      const next = Math.min(duration, clockRef.current + dt * speed);
      clockRef.current = next;
      setClock(next);
      if (next >= duration) {
        setPlaying(false);
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [isReplay, loadState, playing, speed, duration]);

  // ---------- live clock (elapsed keeps ticking between events) ----------
  useEffect(() => {
    if (isReplay || liveDone) return;
    const id = window.setInterval(() => {
      const a = liveAnchor.current;
      if (a) setClock(a.t + (performance.now() - a.at) / 1000);
    }, 250);
    return () => window.clearInterval(id);
  }, [isReplay, liveDone]);

  useEffect(() => {
    if (liveDone) setClock(duration);
  }, [liveDone, duration]);

  // ---------- visible slice ----------
  const count = useMemo(() => (isReplay ? countUpTo(all, clock) : all.length), [isReplay, all, clock]);
  const events = useMemo(() => all.slice(0, count), [all, count]);

  const seek = useCallback(
    (t: number) => {
      const v = Math.max(0, Math.min(duration, t));
      clockRef.current = v;
      setClock(v);
    },
    [duration],
  );

  const play = useCallback(() => {
    if (!isReplay) return;
    if (clockRef.current >= duration) {
      clockRef.current = 0;
      setClock(0);
    }
    setSpeedState((s) => (s === "instant" ? 8 : s));
    setPlaying(true);
  }, [isReplay, duration]);

  const pause = useCallback(() => setPlaying(false), []);

  const restart = useCallback(() => {
    clockRef.current = 0;
    setClock(0);
    setSpeedState((s) => (s === "instant" ? 8 : s));
    setPlaying(true);
  }, []);

  const setSpeed = useCallback(
    (s: Speed) => {
      setSpeedState(s);
      if (s === "instant") {
        clockRef.current = duration;
        setClock(duration);
        setPlaying(false);
      } else if (clockRef.current < duration) {
        setPlaying(true);
      }
    },
    [duration],
  );

  const ended = isReplay ? loadState === "ready" && clock >= duration : liveDone;
  const toggle = useCallback(() => {
    if (playing) pause();
    else play();
  }, [playing, pause, play]);

  return {
    source, events, total: all.length, loadState, error, playing: isReplay ? playing && !ended : !liveDone,
    ended, speed, clock, duration: isReplay ? duration : Math.max(duration, clock), play, pause, toggle, restart, seek, setSpeed,
  };
}
