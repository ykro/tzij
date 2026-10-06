"use client";

import { useEffect, useRef, useState } from "react";
import { Wordmark } from "@/components/Brand";
import { displaySource } from "@/lib/kiche";
import {
  cleanInput,
  displayOutput,
  errorMessage,
  type Example,
  formatLatency,
  languages,
  MAX_CHARS,
  swapDirection,
  type TranslationResult,
} from "@/lib/translator";
import type { Direction } from "@/lib/types";
import { postJSON } from "@/lib/useEventState";

export default function Translator() {
  const [direction, setDirection] = useState<Direction>("es-quc");
  const [text, setText] = useState("");
  const [examples, setExamples] = useState<Example[]>([]);
  const [result, setResult] = useState<TranslationResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const request = useRef(0);

  useEffect(() => {
    fetch("/api/examples")
      .then((res) => (res.ok ? res.json() : []))
      .then((list: Example[]) => setExamples(list))
      .catch(() => setExamples([]));
  }, []);

  async function translate(phrase: string, dir: Direction) {
    const clean = cleanInput(phrase);
    if (!clean || busy) return;
    const id = ++request.current;
    setBusy(true);
    setFailure(null);
    setResult(null);
    try {
      const res = await postJSON<TranslationResult>("/api/translate", { text: clean, direction: dir });
      if (id === request.current) setResult(res);
    } catch (e) {
      if (id === request.current) setFailure(e instanceof Error ? e.message : "No hay conexión con el servicio de Tzij.");
    } finally {
      if (id === request.current) setBusy(false);
    }
  }

  function pickExample(example: Example) {
    setDirection(example.direction);
    setText(example.text);
    translate(example.text, example.direction);
  }

  const { from, to } = languages(direction);
  const message = failure ?? (result ? errorMessage(result) : null);
  const kicheOut = direction === "es-quc";

  return (
    <main className="tr">
      <header className="tr__bar">
        <Wordmark />
        <p className="tr__tag">Traductor español ↔ Kʼicheʼ · corre en esta laptop, sin internet</p>
      </header>

      <section className="tr__panel" aria-label="Traductor">
        <div className="tr__dir">
          <span className="tr__lang">{from}</span>
          <button type="button" className="tr__swap" disabled={busy}
            onClick={() => { setDirection(swapDirection(direction)); setResult(null); setFailure(null); }}
            aria-label={`Cambiar dirección: ahora ${from} a ${to}`}>⇄</button>
          <span className="tr__lang">{to}</span>
        </div>

        <form className="tr__grid" onSubmit={(e) => { e.preventDefault(); translate(text, direction); }}>
          <label className="tr__box">
            <span className="visually-hidden">Texto en {from}</span>
            <textarea value={text} maxLength={MAX_CHARS} rows={4} lang={direction === "es-quc" ? "es" : "quc"}
              className={direction === "quc-es" ? "kiche" : undefined}
              placeholder={direction === "es-quc" ? "Escribe en español…" : "Escribe en Kʼicheʼ…"}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); translate(text, direction); } }} />
            <span className="tr__count num">{text.length}/{MAX_CHARS}</span>
          </label>

          <div className={`tr__out${busy ? " tr__out--busy" : ""}`} aria-live="polite" aria-busy={busy}>
            {busy ? (
              <p className="tr__wait">David está traduciendo…</p>
            ) : message ? (
              <p className="tr__error" role="alert">{message}</p>
            ) : result ? (
              <>
                <p className={`tr__result${kicheOut ? " kiche" : ""}`} lang={kicheOut ? "quc" : "es"}>{displayOutput(result)}</p>
                <p className="tr__meta num">{formatLatency(result.latency_ms)} · en la laptop</p>
              </>
            ) : (
              <p className="tr__empty">La traducción aparece aquí.</p>
            )}
          </div>

          <div className="tr__actions">
            <button type="submit" className="tr__go" disabled={busy || !cleanInput(text)}>Traducir</button>
          </div>
        </form>
      </section>

      {examples.length > 0 && (
        <section className="tr__examples" aria-label="Ejemplos">
          <h2>Ejemplos de la memoria de traducción de Firefox Focus</h2>
          <div className="tr__chips">
            {examples.map((ex) => (
              <button key={ex.pair_id} type="button" className="tr__chip" disabled={busy} onClick={() => pickExample(ex)}>
                {displaySource(ex.text, ex.direction)}
              </button>
            ))}
          </div>
          <p className="tr__note">Frases de {examples[0].source}, licencia {examples[0].license}. David nunca las vio al entrenar.</p>
        </section>
      )}
    </main>
  );
}
