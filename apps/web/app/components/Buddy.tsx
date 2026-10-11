"use client";

import { useEffect, useRef, useState } from "react";
import Eyes, { type Mood } from "./Eyes";

// While a result is on screen, HomePilot becomes a little two-legged buddy who wanders along the bottom.
const STEP_PX_PER_S = 90;

const rand = (min: number, max: number) => min + Math.random() * (max - min);

export default function Buddy({ mood, onPress }: { mood: Mood; onPress: () => void }) {
  const [x, setX] = useState(0.5); // 0..1 across the usable width
  const [walkMs, setWalkMs] = useState(0);
  const [facing, setFacing] = useState<-1 | 1>(1);
  const [gaze, setGaze] = useState<{ x: number; y: number } | undefined>(undefined);
  const [hop, setHop] = useState(false);
  const [reduced, setReduced] = useState(false);
  const xRef = useRef(0.5);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
  }, []);

  useEffect(() => {
    if (reduced) {
      setX(0.12);
      return;
    }
    let timer: ReturnType<typeof setTimeout>;
    const wander = () => {
      const width = Math.max(320, window.innerWidth - 140);
      const target = Math.min(0.95, Math.max(0.05, xRef.current + rand(-0.5, 0.5)));
      const distancePx = Math.abs(target - xRef.current) * width;
      const duration = Math.max(600, (distancePx / STEP_PX_PER_S) * 1000);
      const direction = target >= xRef.current ? 1 : -1;
      setFacing(direction);
      setGaze({ x: direction * 0.85, y: 0.1 }); // look where it's going
      setWalkMs(duration);
      setX(target);
      xRef.current = target;
      timer = setTimeout(() => {
        setWalkMs(0);
        // Pause: sometimes glance up at the card it's showing, otherwise look around.
        setGaze(Math.random() < 0.45 ? { x: rand(-0.2, 0.2), y: -0.9 } : undefined);
        timer = setTimeout(wander, rand(1600, 3800));
      }, duration);
    };
    timer = setTimeout(wander, 1300); // let the landing animation finish first
    return () => clearTimeout(timer);
  }, [reduced]);

  function press() {
    onPress();
    setHop(true);
    setTimeout(() => setHop(false), 520);
  }

  return (
    <button type="button" className={`buddy${walkMs ? " walking" : ""}${hop ? " hop" : ""}`} onPointerDown={press}
      aria-label="HomePilot buddy"
      style={{ left: `calc(${x} * (100% - 120px))`, transitionDuration: `${walkMs}ms` }}>
      <span className="buddy-inner" style={{ ["--face" as string]: facing }}>
        <span className="buddy-body">
          <Eyes mood={mood} size="small" gaze={mood === "happy" ? undefined : gaze} />
        </span>
        <span className="legs" aria-hidden="true">
          <span className="leg leg-left"><span className="foot" /></span>
          <span className="leg leg-right"><span className="foot" /></span>
        </span>
      </span>
    </button>
  );
}
