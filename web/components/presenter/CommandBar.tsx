"use client";

import { useEffect, useRef, useState } from "react";
import { directionLabel, displaySource } from "@/lib/kiche";
import type { Direction } from "@/lib/types";
import { postJSON } from "@/lib/useEventState";

interface Props {
  indexWarning?: string | null;
  direction: Direction;
  onDirection: (d: Direction) => void;
  busy: boolean;
  forceOffline: boolean;
  onClose: () => void;
}

// Presenter controls. Hidden during the talk until "/" (or the "Nueva ronda" button):
// the audience sees the duel, not a form.
export function CommandBar({ indexWarning, direction, onDirection, busy, forceOffline, onClose }: Props) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [suggestions, setSuggestions] = useState<{ text: string }[]>([]);
  const [confirmReset, setConfirmReset] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => input.current?.focus(), []);
  useEffect(() => {
    fetch(`/api/suggestions?direction=${direction}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, [direction]);

  async function start(kind: "en_vivo" | "evaluacion", phrase?: string) {
    setError(null);
    setSending(true);
    try {
      await postJSON("/api/rounds", { kind, direction, text: kind === "en_vivo" ? phrase ?? text : undefined });
      setText("");
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  async function toggleOffline(value: boolean) {
    try {
      await postJSON("/api/connectivity", { force_offline: value });
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function reset() {
    try {
      await postJSON("/api/reset", {});
      setConfirmReset(false);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const placeholder = direction === "es-quc" ? "Escribe una frase en español…" : "Elige una frase en Kʼicheʼ de los datos, abajo";
  const disabled = busy || sending;

  return (
    <form
      className="command"
      aria-label="Nueva ronda"
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) start("en_vivo");
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
    >
      <div className="command__row">
        <div className="segmented" role="group" aria-label="Dirección">
          {(["es-quc", "quc-es"] as Direction[]).map((d) => (
            <button key={d} type="button" aria-pressed={direction === d} onClick={() => onDirection(d)}>
              {directionLabel(d)}
            </button>
          ))}
        </div>
        <label className="visually-hidden" htmlFor="phrase">Frase</label>
        <input id="phrase" ref={input} className="command__input" value={text} maxLength={280}
          onChange={(e) => setText(e.target.value)} placeholder={placeholder} autoComplete="off" />
        <button type="submit" className="btn btn--primary" disabled={disabled || !text.trim()}>
          Traducir en vivo<kbd>↵</kbd>
        </button>
        <button type="button" className="btn" disabled={disabled} onClick={() => start("evaluacion")}>
          Frase de evaluación
        </button>
      </div>
      {suggestions.length > 0 && (
        <div className="command__chips">
          <span>De los datos:</span>
          {suggestions.slice(0, 6).map((s) => (
            <button key={s.text} type="button" className="chip" disabled={disabled} onClick={() => start("en_vivo", s.text)} title={s.text}>
              {displaySource(s.text, direction)}
            </button>
          ))}
        </div>
      )}
      <div className="command__meta">
        <label className="switch">
          <input type="checkbox" checked={forceOffline} onChange={(e) => toggleOffline(e.target.checked)} />
          Simular sin Wi-Fi (ensayo)
        </label>
        {error && <span className="command__error" role="alert">{error}</span>}
        {!error && indexWarning && <span className="command__error" role="status">Aviso: {indexWarning}</span>}
        <span>
          {confirmReset ? (
            <>
              ¿Borrar rondas y veredictos?{" "}
              <button type="button" className="link-button" onClick={reset}>Sí, reiniciar</button>{" "}
              <button type="button" className="link-button" style={{ color: "var(--muted)" }} onClick={() => setConfirmReset(false)}>Cancelar</button>
            </>
          ) : (
            <button type="button" className="link-button" onClick={() => setConfirmReset(true)}>Reiniciar marcador</button>
          )}
          {"  ·  "}Esc cierra
        </span>
      </div>
    </form>
  );
}
