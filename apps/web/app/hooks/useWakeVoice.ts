"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CommitStrategy, useScribe } from "@elevenlabs/react";

// off → connecting → armed (wake-only: speech is ignored and nothing reaches HomePilot)
//   → collecting (after "Hey HomePilot" or a tap: the next finished sentence is the command) → armed
export type VoiceState = "off" | "connecting" | "armed" | "collecting";

const WAKE = /\b(?:(?:hey|hi|okay|ok)[\s,]+)?home[\s-]?pilot\b[\s,.!?]*/i;
const COLLECT_TIMEOUT_MS = 60_000;
const LISTEN_PREFERENCE_KEY = "homepilot.listening"; // "off" after the user turns listening off

function rememberListening(on: boolean) {
  try { localStorage.setItem(LISTEN_PREFERENCE_KEY, on ? "on" : "off"); } catch { /* storage unavailable */ }
}

function userTurnedListeningOff(): boolean {
  try { return localStorage.getItem(LISTEN_PREFERENCE_KEY) === "off"; } catch { return false; }
}

// True only when the browser already allows the microphone, so listening can start without a click.
async function microphoneAlreadyAllowed(): Promise<boolean> {
  try {
    const status = await navigator.permissions.query({ name: "microphone" as PermissionName });
    return status.state === "granted";
  } catch {
    return false; // browsers without microphone permission queries keep the Listen button
  }
}

type Options = {
  onWake: () => void; // wake phrase heard (or manual activation)
  onCommand: (text: string) => void; // one finished command
  onTimeout: () => void; // activated but nothing was said in time
};

export function useWakeVoice({ onWake, onCommand, onTimeout }: Options) {
  const [state, setState] = useState<VoiceState>("off");
  const [error, setError] = useState<string | null>(null);
  const stateRef = useRef<VoiceState>("off");
  const callbacks = useRef({ onWake, onCommand, onTimeout });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  callbacks.current = { onWake, onCommand, onTimeout };

  const setVoiceState = useCallback((next: VoiceState) => {
    stateRef.current = next;
    setState(next);
  }, []);

  const clearTimer = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  };

  const backToIdle = useCallback(() => {
    clearTimer();
    if (stateRef.current === "collecting") setVoiceState("armed");
  }, [setVoiceState]);

  const startCollecting = useCallback(() => {
    clearTimer();
    setVoiceState("collecting");
    callbacks.current.onWake();
    timer.current = setTimeout(() => {
      if (stateRef.current !== "collecting") return;
      setVoiceState("armed");
      callbacks.current.onTimeout();
    }, COLLECT_TIMEOUT_MS);
  }, [setVoiceState]);

  const finishCommand = useCallback((text: string) => {
    const command = text.trim();
    if (!command) return; // just the wake phrase: keep listening for the command
    clearTimer();
    setVoiceState("armed"); // later speech is wake-only again until the next "Hey HomePilot"
    callbacks.current.onCommand(command);
  }, [setVoiceState]);

  const scribe = useScribe({
    modelId: "scribe_v2_realtime",
    commitStrategy: CommitStrategy.VAD,
    vadSilenceThresholdSecs: 1.0,
    keyterms: ["HomePilot", "Hey HomePilot"],
    onPartialTranscript: ({ text }) => {
      if (stateRef.current === "armed" && WAKE.test(text)) startCollecting(); // react fast; command comes on commit
    },
    onCommittedTranscript: ({ text }) => {
      const match = text.match(WAKE);
      if (stateRef.current === "armed") {
        if (!match) return; // not addressed to HomePilot: ignore
        startCollecting();
      }
      if (stateRef.current !== "collecting") return;
      // Keep words said right after the wake phrase in the same sentence ("Hey HomePilot, add this").
      finishCommand(match ? text.slice((match.index ?? 0) + match[0].length) : text);
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : "Speech connection failed"),
    onAuthError: ({ error }) => setError(error),
    onQuotaExceededError: ({ error }) => setError(error),
    onDisconnect: () => {
      clearTimer();
      setVoiceState("off");
    },
  });

  const enable = useCallback(async () => {
    if (stateRef.current !== "off") return;
    setError(null);
    setVoiceState("connecting");
    try {
      const response = await fetch("/api/scribe-token", { method: "POST" });
      const body = await response.json().catch(() => null);
      if (!response.ok || typeof body?.token !== "string") throw new Error(body?.error ?? "Couldn't get a speech token");
      await scribe.connect({ token: body.token, microphone: { echoCancellation: true, noiseSuppression: true } });
      setVoiceState("armed");
      rememberListening(true);
    } catch (cause) {
      setVoiceState("off");
      setError(cause instanceof Error ? cause.message : "Couldn't start listening");
    }
  }, [scribe, setVoiceState]);

  // Stops listening without changing the user's preference (tab hidden, page closing).
  const pause = useCallback(() => {
    clearTimer();
    scribe.disconnect();
    setVoiceState("off");
  }, [scribe, setVoiceState]);

  // The user turned listening off: don't start it again automatically.
  const disable = useCallback(() => {
    rememberListening(false);
    pause();
  }, [pause]);

  // Tapping the assistant behaves like saying the wake phrase.
  const activate = useCallback(() => {
    if (stateRef.current === "armed") startCollecting();
  }, [startCollecting]);

  // Start listening for the wake phrase without a click when the microphone is already allowed,
  // unless the user turned listening off. Runs on page load and whenever the tab becomes visible.
  const enableRef = useRef(enable);
  enableRef.current = enable;
  const pauseRef = useRef(pause);
  pauseRef.current = pause;
  useEffect(() => {
    const autoStart = async () => {
      if (document.hidden || stateRef.current !== "off" || userTurnedListeningOff()) return;
      if (await microphoneAlreadyAllowed()) void enableRef.current();
    };
    // VOICE_CAPTURE.md: hiding the tab ends collection; listening resumes when the tab is visible again.
    const onVisibility = () => {
      if (document.hidden) { if (stateRef.current !== "off") pauseRef.current(); }
      else void autoStart();
    };
    void autoStart();
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => clearTimer, []);

  return { state, error, heard: state === "collecting" ? scribe.partialTranscript : "", enable, disable, activate, cancel: backToIdle };
}
