"use client";

import { useEffect, useId, useRef, useState } from "react";

export type Mood = "sleepy" | "idle" | "alert" | "listening" | "thinking" | "happy" | "confused";

type Look = { lx: number; ly: number; rx: number; ry: number }; // pupil offsets per eye, -1..1

const CENTER: Look = { lx: 0, ly: 0, rx: 0, ry: 0 };
const FIXED: Partial<Record<Mood, Look>> = {
  alert: { lx: 0, ly: 0.05, rx: 0, ry: 0.05 },
  listening: CENTER,
  thinking: { lx: 0.55, ly: -0.75, rx: 0.55, ry: -0.75 },
  confused: { lx: -0.35, ly: 0.25, rx: -0.2, ry: 0.1 },
  happy: CENTER,
};

const rand = (min: number, max: number) => min + Math.random() * (max - min);
const same = (x: number, y: number): Look => ({ lx: x, ly: y, rx: x, ry: y });

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

type Gaze = { x: number; y: number };

// `gaze` overrides wandering, e.g. the walking buddy looks where it is heading.
export default function Eyes({ mood, size = "large", gaze }: { mood: Mood; size?: "large" | "small"; gaze?: Gaze }) {
  const reduced = usePrefersReducedMotion();
  const [look, setLook] = useState<Look>(CENTER);
  const [blink, setBlink] = useState(false);
  const previousMood = useRef<Mood>(mood);
  const clip = `eyes${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`; // unique per instance (face + buddy)

  // Wander while idle or sleepy; otherwise hold the mood's gaze.
  const gazeX = gaze?.x;
  const gazeY = gaze?.y;
  useEffect(() => {
    if (gazeX !== undefined && gazeY !== undefined) {
      setLook(same(gazeX, gazeY));
      return;
    }
    if (FIXED[mood]) {
      setLook(FIXED[mood]!);
      return;
    }
    if (reduced) {
      setLook(CENTER);
      return;
    }
    let timer: ReturnType<typeof setTimeout>;
    const slow = mood === "sleepy";
    const step = () => {
      const roll = Math.random();
      if (!slow && roll < 0.08) {
        setLook({ lx: 0.75, ly: 0.15, rx: -0.75, ry: 0.15 }); // cross-eyed, briefly
        timer = setTimeout(() => { setLook(same(0, 0)); timer = setTimeout(step, rand(900, 1600)); }, 700);
        return;
      }
      if (!slow && roll < 0.16) {
        const side = Math.random() < 0.5 ? -1 : 1; // double take: glance away, snap back, glance again
        setLook(same(side * 0.95, 0));
        timer = setTimeout(() => setLook(same(0, 0)), 260);
        timer = setTimeout(() => { setLook(same(side * 0.95, -0.1)); timer = setTimeout(step, rand(1200, 2000)); }, 520);
        return;
      }
      const angle = rand(0, Math.PI * 2);
      const reach = slow ? rand(0.1, 0.45) : rand(0.25, 0.95);
      setLook(same(Math.cos(angle) * reach, Math.sin(angle) * reach * 0.8));
      timer = setTimeout(step, slow ? rand(2600, 4200) : rand(1300, 3200));
    };
    step();
    return () => clearTimeout(timer);
  }, [mood, reduced, gazeX, gazeY]);

  // Natural blinking, plus a double blink when HomePilot becomes alert.
  useEffect(() => {
    if (reduced || mood === "happy") return;
    let timer: ReturnType<typeof setTimeout>;
    const doBlink = (then: () => void) => {
      setBlink(true);
      timer = setTimeout(() => { setBlink(false); then(); }, 130);
    };
    const loop = () => { timer = setTimeout(() => doBlink(loop), rand(2400, 5600)); };
    if (mood === "alert" && previousMood.current !== "alert") {
      doBlink(() => { timer = setTimeout(() => doBlink(loop), 160); });
    } else {
      loop();
    }
    previousMood.current = mood;
    return () => clearTimeout(timer);
  }, [mood, reduced]);

  const pupil = (x: number, y: number) => ({ transform: `translate(${x * 26}px, ${y * 30}px)` });

  return (
    <svg className={`eyes eyes-${size} mood-${mood}${blink ? " blinking" : ""}`} viewBox="0 0 360 210" role="img"
      aria-label={`HomePilot is ${mood === "idle" ? "looking around" : mood}`}>
      <defs>
        <clipPath id={`${clip}-left`}><ellipse cx="110" cy="115" rx="62" ry="72" /></clipPath>
        <clipPath id={`${clip}-right`}><ellipse cx="250" cy="115" rx="62" ry="72" /></clipPath>
      </defs>
      <rect className="brow brow-left" x="72" y="14" width="76" height="13" rx="6.5" />
      <rect className="brow brow-right" x="212" y="14" width="76" height="13" rx="6.5" />
      {(["left", "right"] as const).map((side) => {
        const cx = side === "left" ? 110 : 250;
        const offset = side === "left" ? pupil(look.lx, look.ly) : pupil(look.rx, look.ry);
        return (
          <g key={side} className="eye">
            {mood === "happy" ? (
              <path className="happy-arc" d={`M ${cx - 46} 128 Q ${cx} 62 ${cx + 46} 128`} />
            ) : (
              <g className="eyeball">
                <ellipse className="sclera" cx={cx} cy="115" rx="62" ry="72" />
                <g clipPath={`url(#${clip}-${side})`}>
                  <g className="pupil" style={offset}>
                    <circle cx={cx} cy="118" r="29" className="iris" />
                    <circle cx={cx - 10} cy="106" r="9" className="shine" />
                  </g>
                  <path className="lid" d={`M ${cx - 66} 30 H ${cx + 66} V 112 Q ${cx} 136 ${cx - 66} 112 Z`} />
                </g>
              </g>
            )}
          </g>
        );
      })}
    </svg>
  );
}
