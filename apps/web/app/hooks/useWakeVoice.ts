"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CommitStrategy, useScribe } from "@elevenlabs/react";
import { isSpeaking } from "../lib/speech";

// off → connecting → armed (wake-only: speech is ignored and nothing reaches HomePilot)
//   → collecting (after "Hey HomePilot" or a tap: the next finished sentence is the command) → armed
export type VoiceState = "off" | "connecting" | "armed" | "collecting";

const WAKE = /\b(?:(?:hey|hi|okay|ok)[\s,]+)?home[\s-]?pilot\b[\s,.!?]*/i;
const COLLECT_TIMEOUT_MS = 60_000;
const REPLY_TIMEOUT_MS = 10_000; // listening for a yes/no after HomePilot asks a question
const LISTEN_PREFERENCE_KEY = "homepilot.listening"; // "off" after the user turns listening off

function rememberListening(on: boolean) {
  try { localStorage.setItem(LISTEN_PREFERENCE_KEY, on ? "on" : "off"); } catch { /* storage unavailable */ }
}

function userTurnedListeningOff(): boolean {
  try { return localStorage.getItem(LISTEN_PREFERENCE_KEY) === "off"; } catch { return false; }
}

// False only when the user has blocked the microphone. "prompt" is fine: the browser asks on start-up.
async function microphoneNotBlocked(): Promise<boolean> {
  try {
    const status = await navigator.permissions.query({ name: "microphone" as PermissionName });
    return status.state !== "denied";
  } catch {
    return true; // browsers without microphone permission queries simply ask when listening starts
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

  // `wake` is false when HomePilot itself asked a question and waits for the reply: no wake-up
  // (the question stays on screen) and a silent, shorter timeout.
  const startCollecting = useCallback((wake = true) => {
    clearTimer();
    setVoiceState("collecting");
    if (wake) callbacks.current.onWake();
    timer.current = setTimeout(() => {
      if (stateRef.current !== "collecting") return;
      setVoiceState("armed");
      if (wake) callbacks.current.onTimeout();
    }, wake ? COLLECT_TIMEOUT_MS : REPLY_TIMEOUT_MS);
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
    vadSilenceThresholdSecs: 0.7, // shorter pause before a sentence counts as finished
    keyterms: ["HomePilot", "Hey HomePilot"],
    onPartialTranscript: ({ text }) => {
      if (isSpeaking()) return; // HomePilot's own spoken answer, not the user
      if (stateRef.current === "armed" && WAKE.test(text)) startCollecting(); // react fast; command comes on commit
    },
    onCommittedTranscript: ({ text }) => {
      if (isSpeaking()) return;
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

  // After HomePilot asks a question, take the next sentence as the answer without "Hey HomePilot".
  const listenForReply = useCallback((): boolean => {
    if (stateRef.current !== "armed") return false;
    startCollecting(false);
    return true;
  }, [startCollecting]);

  // Start listening for the wake phrase on page load (and when the tab becomes visible again) unless
  // the user blocked the microphone or turned listening off. After a failed or refused start, wait
  // for the Listen button instead of asking again on every tab switch.
  const autoStartFailed = useRef(false);
  const enableRef = useRef(enable);
  enableRef.current = enable;
  const pauseRef = useRef(pause);
  pauseRef.current = pause;
  useEffect(() => {
    const autoStart = async () => {
      if (document.hidden || stateRef.current !== "off" || userTurnedListeningOff() || autoStartFailed.current) return;
      if (!(await microphoneNotBlocked())) return;
      await enableRef.current();
      if (stateRef.current === "off") autoStartFailed.current = true;
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

  return { state, error, heard: state === "collecting" ? scribe.partialTranscript : "", enable, disable, activate, listenForReply, cancel: backToIdle };
}
