"use client";

import { useState } from "react";
import type { ResultEnvelope } from "../lib/api";

function label(brand?: string | null, name?: string, size?: string | null) {
  return [brand, name, size].filter(Boolean).join(" ");
}

export default function ResultView({ result, onDone }: { result: ResultEnvelope; onDone: () => void }) {
  const [confirmed, setConfirmed] = useState<string | null>(null);

  return (
    <section className={`result result-${result.view}`} aria-live="polite">
      {result.demo && <p className="demo-badge">Demo data — not from your household</p>}
      <h2>{result.title}</h2>

      {result.view === "message" && <p className={`message tone-${result.tone}`}>{result.text}</p>}

      {(result.view === "grocery_list" || result.view === "inventory") && (
        result.items.length ? (
          <ul className="items">
            {result.items.map((item, index) => (
              <li key={`${item.name}-${index}`}>
                <span>{label(item.brand, item.name)}</span>
                {item.quantity != null && <span className="qty">× {item.quantity}</span>}
              </li>
            ))}
          </ul>
        ) : <p className="message">Nothing here yet.</p>
      )}

      {result.view === "recognition" && (
        result.recognition.unknown ? (
          <p className="message">I couldn't match this to a product I know. What is it? Type the name below, or try another angle.</p>
        ) : (
          <>
            <p className="hint">Tap the right one to confirm. Nothing is saved until you do.</p>
            <ol className="candidates">
              {result.recognition.candidates.map((candidate) => {
                const name = label(candidate.brand, candidate.name, candidate.size_label);
                return (
                  <li key={candidate.rank}>
                    <button type="button" className={confirmed === name ? "picked" : ""} onClick={() => setConfirmed(name)}>
                      <span className="rank">{candidate.rank}</span>{name}
                    </button>
                  </li>
                );
              })}
            </ol>
            {confirmed && (
              // No inventory write route exists yet; say so instead of pretending it was saved.
              <p className="message tone-rejected" role="status">You picked {confirmed}. Saving to inventory isn't connected yet, so nothing was saved.</p>
            )}
          </>
        )
      )}

      <button type="button" className="done" onClick={onDone}>Back to HomePilot</button>
    </section>
  );
}
