// Client for FastAPI's orchestrator, reached through the same-origin /api/hp proxy (next.config.ts).

export type Candidate = { name: string; brand?: string | null; size_label?: string | null; rank: number; score?: number | null };
export type Recognition = { unknown: boolean; candidates: Candidate[]; model_id?: string; requires_confirmation?: boolean };
export type ListItem = { name: string; quantity?: number; brand?: string | null };

// What the screen should show after a command. Only "message" is backed by today's API response;
// the other views need the proposed `view`/data fields from the orchestrator (see WEB_CAPTURE_ISSUES.md).
export type AssistantResult =
  | { view: "message"; title: string; text: string; tone: "ok" | "rejected" | "error" }
  | { view: "grocery_list" | "inventory"; title: string; items: ListItem[] }
  | { view: "recognition"; title: string; recognition: Recognition; prompt: string };

export type ResultEnvelope = AssistantResult & { demo?: boolean };

const TIMEOUT_MS = 60_000;

function errorMessage(body: unknown, status: number): string {
  const message = (body as { error?: { message?: unknown } } | null)?.error?.message;
  if (typeof message === "string") return message;
  // The Next proxy answers 500/502 with no JSON body when FastAPI is down or unreachable.
  if ([404, 500, 502, 503, 504].includes(status)) return "HomePilot's server isn't reachable. Is FastAPI running on port 8000?";
  return `Request failed (${status})`;
}

export async function runOrchestrator(prompt: string, image: Blob | null): Promise<ResultEnvelope> {
  const form = new FormData();
  form.append("prompt", prompt);
  if (image) form.append("image", image, "frame.jpg");
  let response: Response;
  try {
    response = await fetch("/api/hp/orchestrator/run", { method: "POST", body: form, signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (cause) {
    const timedOut = cause instanceof DOMException && cause.name === "TimeoutError";
    return { view: "message", tone: "error", title: timedOut ? "That took too long" : "Can't reach HomePilot",
      text: timedOut ? "The server didn't answer within a minute. Try again." : "Check that the web app and FastAPI are both running." };
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) return { view: "message", tone: "error", title: "Something went wrong", text: errorMessage(body, response.status) };
  return interpret(body, prompt);
}

// Accepts today's {status, valid, reason} and, when present, the proposed {reply, view, items, recognition}.
export function interpret(body: unknown, prompt: string): ResultEnvelope {
  const data = (body ?? {}) as Record<string, unknown>;
  if (data.valid === false) {
    return { view: "message", tone: "rejected", title: "I can't help with that one",
      text: typeof data.reason === "string" ? data.reason : "That request is outside what HomePilot does." };
  }
  // main's OrchestratorRunResult: {status: rejected|in_progress|completed, valid, reason, response}.
  // `response` is the assistant's answer or clarifying question; `reply` is kept for the proposed shape.
  const reply = typeof data.response === "string" && data.response.trim() ? data.response
    : typeof data.reply === "string" ? data.reply : null;
  const title = data.status === "completed" ? "Done!" : data.status === "in_progress" && reply ? "One more thing" : "Got it";
  if ((data.view === "grocery_list" || data.view === "inventory") && Array.isArray(data.items)) {
    return { view: data.view, title: data.view === "grocery_list" ? "Grocery list" : "Inventory", items: data.items as ListItem[] };
  }
  const recognition = data.recognition as Recognition | undefined;
  if (recognition && typeof recognition.unknown === "boolean" && Array.isArray(recognition.candidates)) {
    return { view: "recognition", title: recognition.unknown ? "I don't recognize this one" : "Is this it?", recognition, prompt };
  }
  return { view: "message", tone: "ok", title, text: reply ?? "HomePilot understood your request. The next steps aren't connected yet." };
}

// Clearly labelled sample results for ?demo=1, used until the backend returns views. Never saved anywhere.
export function demoResult(prompt: string, hasImage: boolean): ResultEnvelope {
  const text = prompt.toLowerCase();
  if (text.includes("list")) {
    return { demo: true, view: "grocery_list", title: "Grocery list",
      items: [{ name: "Oat milk", quantity: 1 }, { name: "Bananas", quantity: 6 }, { name: "Rice", quantity: 1 }, { name: "Barilla pesto", quantity: 2 }] };
  }
  if (hasImage || /\bthis\b/.test(text)) { // "add this…" refers to the product in view
    return { demo: true, view: "recognition", title: "Is this it?", prompt, recognition: { unknown: false, model_id: "demo-not-a-real-model",
      candidates: [{ name: "Energy Drink", brand: "Red Bull", rank: 1, score: 3.4 }, { name: "Energy Drink", brand: "Monster", rank: 2, score: 2.5 }] } };
  }
  if (text.includes("inventory") || text.includes("pantry") || text.includes("what do we have")) {
    return { demo: true, view: "inventory", title: "Inventory",
      items: [{ name: "Heinz ketchup", quantity: 1 }, { name: "Red Bull", quantity: 4 }, { name: "Pringles", quantity: 2 }] };
  }
  return { demo: true, view: "message", tone: "ok", title: "Got it", text: `You said: “${prompt}”` };
}
