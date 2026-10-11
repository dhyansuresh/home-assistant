// HomePilot reads its answers aloud with a friendly ElevenLabs voice (via /api/tts), falling back to the
// browser's built-in voices when ElevenLabs can't be reached. While it speaks, and briefly after,
// wake-word listening ignores what the microphone hears.

import type { ResultEnvelope } from "./api";

const PREFERENCE_KEY = "homepilot.voice"; // "off" after the user mutes spoken answers
const PREFERRED_VOICES = ["Samantha", "Google US English", "Microsoft Aria", "Ava", "Allison", "Karen", "Daniel"];

const GRACE_MS = 800; // keep ignoring the microphone briefly so the answer's tail isn't transcribed

let speaking = false;
// The answer being spoken now. Stopping an answer fires its end event later; only the current
// answer's end may switch `speaking` off, or the microphone would come back mid-answer.
let current: object | null = null;
let audio: HTMLAudioElement | null = null;

export function speechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function isSpeaking(): boolean {
  return speaking;
}

export function voiceEnabled(): boolean {
  try { return localStorage.getItem(PREFERENCE_KEY) !== "off"; } catch { return true; }
}

export function setVoiceEnabled(on: boolean) {
  try { localStorage.setItem(PREFERENCE_KEY, on ? "on" : "off"); } catch { /* storage unavailable */ }
  if (!on) stopSpeaking();
}

function pickVoice(): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices().filter((voice) => voice.lang.toLowerCase().startsWith("en"));
  for (const name of PREFERRED_VOICES) {
    const match = voices.find((voice) => voice.name.includes(name));
    if (match) return match;
  }
  return voices.find((voice) => voice.lang === "en-US") ?? voices[0];
}

// Turn the on-screen text into something that sounds natural: "• Milk × 3" → "Milk, 3".
export function spokenText(result: ResultEnvelope): string {
  switch (result.view) {
    case "message":
      // "Milk × 3" → "3 Milk"; list lines become a comma-separated sentence.
      return result.text
        .replace(/^•\s*/gm, "")
        .replace(/([^\n,:]+?)\s*×\s*(\d+)/g, (_, name: string, count: string) => {
          const lead = name.match(/^(.*\b(?:Added|and)\s+)(.+)$/);
          return lead ? `${lead[1]}${count} ${lead[2]}` : `${count} ${name.trim()}`;
        })
        .replace(/:\s*\n/g, ": ")
        .replace(/\n+/g, ", ");
    case "grocery_list":
    case "inventory":
      return result.items.length
        ? `${result.title}: ${result.items.map((item) => `${item.name}${item.quantity ? `, ${item.quantity}` : ""}`).join(". ")}.`
        : `${result.title} is empty.`;
    case "recognition": {
      const top = result.recognition.candidates[0];
      return result.recognition.unknown || !top
        ? "I don't recognize this one. What is it?"
        : `This looks like ${[top.brand, top.name].filter(Boolean).join(" ")}.`;
    }
  }
}

export function stopSpeaking() {
  current = null;
  speaking = false;
  audio?.pause();
  audio = null;
  if (speechSupported()) window.speechSynthesis.cancel();
}

// Play one answer with ElevenLabs; resolves when it has finished (false if it couldn't play).
async function speakWithElevenLabs(text: string, token: object): Promise<boolean> {
  try {
    const response = await fetch("/api/tts", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
    });
    if (!response.ok || current !== token) return false;
    const url = URL.createObjectURL(await response.blob());
    if (current !== token) { URL.revokeObjectURL(url); return true; }
    const player = new Audio(url);
    audio = player;
    await new Promise<void>((resolve, reject) => {
      player.onended = () => resolve();
      player.onpause = () => resolve(); // stopSpeaking() pauses it: count that as finished
      player.onerror = () => reject(new Error("audio failed"));
      player.play().catch(reject); // Chrome may block audio before the first tap or click
    });
    URL.revokeObjectURL(url);
    return true;
  } catch {
    return false;
  }
}

function speakWithBrowser(text: string, token: object): Promise<void> {
  if (!speechSupported() || current !== token) return Promise.resolve();
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = pickVoice();
    if (voice) utterance.voice = voice;
    utterance.rate = 1.05;
    utterance.onend = utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}

/** Speak an answer. Resolves after it has finished (plus a short grace), or at once when muted. */
export async function speak(text: string): Promise<void> {
  if (!voiceEnabled() || !text.trim()) return;
  stopSpeaking(); // never talk over a previous answer
  const token = {};
  current = token;
  speaking = true;
  if (!(await speakWithElevenLabs(text, token))) await speakWithBrowser(text, token);
  await new Promise((resolve) => setTimeout(resolve, GRACE_MS));
  if (current !== token) return; // a newer answer is playing (or speech was stopped)
  current = null;
  audio = null;
  speaking = false;
}
