"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Buddy from "./components/Buddy";
import Eyes, { type Mood } from "./components/Eyes";
import ResultView from "./components/ResultView";
import { useCamera } from "./hooks/useCamera";
import { useWakeVoice } from "./hooks/useWakeVoice";
import { demoResult, runOrchestrator, type ResultEnvelope } from "./lib/api";
import { playAlert, playClick } from "./lib/sounds";
import { setVoiceEnabled, speak, speechSupported, spokenText, stopSpeaking, voiceEnabled } from "./lib/speech";

type Phase = "idle" | "listening" | "thinking" | "result";
const DEFAULT_PHOTO_PROMPT = "What is this product?";

export default function Home() {
  const camera = useCamera();
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<ResultEnvelope | null>(null);
  const [glow, setGlow] = useState(false);
  const [justWoke, setJustWoke] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [demo, setDemo] = useState(false);
  const [talk, setTalk] = useState(true); // read answers aloud
  const [canTalk, setCanTalk] = useState(false);
  const glowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const busy = useRef(false);
  const [awaitingReply, setAwaitingReply] = useState(false); // listening for an answer to HomePilot's question
  const replyHandler = useRef<(asked: boolean) => void>(() => {});
  const trayRef = useRef<HTMLElement>(null);
  const [trayHeight, setTrayHeight] = useState(120);

  // The buddy walks just above the tray, whose height changes when it wraps on phones.
  useEffect(() => {
    const tray = trayRef.current;
    if (!tray) return;
    const observer = new ResizeObserver(() => setTrayHeight(tray.offsetHeight));
    observer.observe(tray);
    return () => observer.disconnect();
  }, []);

  useEffect(() => setDemo(new URLSearchParams(window.location.search).get("demo") === "1"), []);
  useEffect(() => { setCanTalk(speechSupported()); setTalk(voiceEnabled()); }, []);

  const pulseGlow = useCallback((ms = 1200) => {
    setGlow(true);
    if (glowTimer.current) clearTimeout(glowTimer.current);
    glowTimer.current = setTimeout(() => setGlow(false), ms);
  }, []);

  // One command → one request. Capture stops before the request runs (VOICE_CAPTURE.md: stop, then execute).
  const send = useCallback(async (prompt: string, image: Blob | null) => {
    if (busy.current) return;
    busy.current = true;
    camera.stop();
    setNotice(null);
    setAwaitingReply(false);
    setPhase("thinking");
    const outcome = demo ? demoResult(prompt, Boolean(image)) : await runOrchestrator(prompt, image);
    setResult(outcome);
    setPhase("result");
    const asked = outcome.view === "message" && outcome.tone === "ok"
      && (/\?\s*$/.test(outcome.text) || /say yes/i.test(outcome.text));
    // Once the answer has been spoken, a question is followed by listening for the reply.
    void speak(spokenText(outcome)).then(() => replyHandler.current(asked));
    busy.current = false;
  }, [camera, demo]);

  const startListening = useCallback(() => {
    stopSpeaking(); // waking HomePilot interrupts an answer
    playAlert();
    setResult(null);
    setPhase("listening");
    setJustWoke(true);
    setTimeout(() => setJustWoke(false), 1100);
    pulseGlow(1600);
    void camera.start();
  }, [camera, pulseGlow]);

  replyHandler.current = (asked: boolean) => {
    if (!asked || phase === "thinking") return;
    if (voice.listenForReply()) {
      setAwaitingReply(true);
      pulseGlow(1200);
      setTimeout(() => setAwaitingReply(false), 10_000);
    }
  };

  const voice = useWakeVoice({
    onWake: startListening,
    onCommand: (text) => { void (async () => send(text, await camera.grabFrame()))(); },
    onTimeout: () => {
      camera.stop();
      setPhase("idle");
      setNotice("I didn't catch a command. Say “Hey HomePilot” again whenever you're ready.");
    },
  });

  // Tap or press: glow, and wake up the same way the voice phrase does.
  function onStagePress() {
    playClick();
    pulseGlow();
    if (phase !== "idle") return;
    if (voice.state === "armed") voice.activate();
    else startListening();
  }

  function stopListening() {
    voice.cancel();
    camera.stop();
    setPhase("idle");
  }

  async function onTypedSubmit(event: FormEvent) {
    event.preventDefault();
    const text = typed.trim();
    if (!text) return;
    setTyped("");
    voice.cancel();
    await send(text, camera.active ? await camera.grabFrame() : null);
  }

  async function onCapture() {
    const frame = await camera.grabFrame();
    if (!frame) { setNotice("The camera isn't ready yet. Give it a second."); return; }
    voice.cancel();
    await send(typed.trim() || DEFAULT_PHOTO_PROMPT, frame);
    setTyped("");
  }

  async function onChoosePhoto(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) { setNotice("Please choose an image file."); return; }
    voice.cancel();
    await send(typed.trim() || DEFAULT_PHOTO_PROMPT, file);
    setTyped("");
  }

  function backToAssistant() {
    setResult(null);
    setPhase("idle");
  }

  const mood: Mood =
    phase === "thinking" ? "thinking"
    : phase === "listening" ? (justWoke ? "alert" : "listening")
    : phase === "result" && result ? (
      (result.view === "message" && result.tone !== "ok") || (result.view === "recognition" && result.recognition.unknown)
        ? "confused" : "happy")
    : voice.state === "off" ? "sleepy" : "idle";

  const status =
    phase === "thinking" ? "Thinking…"
    : phase === "listening" ? (voice.heard ? `“${voice.heard}”` : voice.state === "collecting" ? "I'm listening…" : "I'm awake! Type, take a photo, or turn on listening.")
    : phase === "result" ? (awaitingReply && voice.state === "collecting" ? (voice.heard ? `“${voice.heard}”` : "I'm listening for your answer…") : "")
    : voice.state === "armed" ? "Say “Hey HomePilot”, or tap me."
    : voice.state === "connecting" ? "Waking up my ears…"
    : "Tap me, or turn on listening.";

  return (
    <main className={`stage phase-${phase}${glow || phase === "listening" ? " glowing" : ""}`}
      style={{ ["--tray-h" as string]: `${trayHeight}px` }}>
      {demo && <p className="demo-banner">Demo mode: sample answers, nothing is sent or saved</p>}

      {phase === "result" ? (
        // Showing something: HomePilot turns into a little two-legged buddy along the bottom.
        <Buddy mood={mood} onPress={() => { playClick(); pulseGlow(); }} />
      ) : (
        <button type="button" className="face face-large" onPointerDown={onStagePress}
          aria-label={phase === "idle" ? "Wake HomePilot" : "HomePilot"}>
          <Eyes mood={mood} />
        </button>
      )}

      <p className="status" role="status" aria-live="polite">{status}</p>
      {phase === "thinking" && <div className="dots" aria-hidden="true"><span /><span /><span /></div>}

      {phase === "result" && result && <ResultView result={result} onDone={backToAssistant} />}

      <video ref={camera.videoRef} className="pip" hidden={!camera.active} autoPlay muted playsInline aria-label="Camera preview" />

      {(notice || camera.error || voice.error) && (
        <p className="notice" role="alert">{notice ?? camera.error ?? voice.error}</p>
      )}

      <footer className="tray" ref={trayRef}>
        <form onSubmit={onTypedSubmit} className="ask">
          <input value={typed} onChange={(event) => setTyped(event.target.value)} placeholder="Or type: “show my grocery list”"
            aria-label="Type a request" maxLength={2000} disabled={phase === "thinking"} />
          <button type="submit" disabled={!typed.trim() || phase === "thinking"}>Send</button>
        </form>
        <div className="tools">
          <button type="button" className={voice.state === "off" ? "" : "on"} disabled={voice.state === "connecting"}
            onClick={() => (voice.state === "off" ? void voice.enable() : voice.disable())}>
            {voice.state === "off" ? "🎙 Listen" : voice.state === "connecting" ? "Connecting…" : "🎙 Listening"}
          </button>
          {canTalk && (
            <button type="button" className={talk ? "on" : ""} aria-pressed={talk}
              onClick={() => { setVoiceEnabled(!talk); setTalk(!talk); }}>
              {talk ? "🔊 Voice" : "🔇 Voice off"}
            </button>
          )}
          {camera.active && <button type="button" onClick={() => void onCapture()} disabled={phase === "thinking"}>📸 Send photo</button>}
          <label className={`file${phase === "thinking" ? " disabled" : ""}`}>
            🖼 Choose photo
            <input type="file" accept="image/*" disabled={phase === "thinking"}
              onChange={(event) => { void onChoosePhoto(event.target.files); event.target.value = ""; }} />
          </label>
          {phase === "listening" && <button type="button" className="stop" onClick={stopListening}>Stop</button>}
        </div>
      </footer>
    </main>
  );
}
