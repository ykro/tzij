"use client";

import { useEffect, useState } from "react";
import { Wordmark } from "@/components/Brand";
import { VERDICT_LABEL, VerdictIcon } from "@/components/Verdict";
import { directionLabel, displaySource, displayTarget } from "@/lib/kiche";
import type { BlindRound, VerdictName } from "@/lib/types";
import { postJSON, useEventState } from "@/lib/useEventState";

const VERDICTS: VerdictName[] = ["correcta", "aceptable", "incorrecta"];

// A stable anonymous id per phone: one verdict per person and translation; changing
// your mind replaces the previous verdict. (crypto.randomUUID needs HTTPS; the LAN is HTTP.)
function voterId(): string {
  try {
    const saved = localStorage.getItem("tzij-voter");
    if (saved) return saved;
    const id = `v-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem("tzij-voter", id);
    return id;
  } catch {
    return `v-${Math.random().toString(36).slice(2, 12)}`;
  }
}

function loadMine(roundId: string): Record<number, VerdictName> {
  try {
    return JSON.parse(localStorage.getItem(`tzij-verdicts-${roundId}`) ?? "{}");
  } catch {
    return {};
  }
}

export default function Validator() {
  const { data, connection } = useEventState<{ round: BlindRound | null }>("validator", "validator");
  const round = data?.round ?? null;
  const [mine, setMine] = useState<Record<number, VerdictName>>({});
  const [pending, setPending] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    setMine(round ? loadMine(round.id) : {});
    setError(null);
    setSaved(null);
  }, [round?.id]);

  async function vote(slot: number, verdict: VerdictName) {
    if (!round) return;
    const previous = mine;
    const next = { ...mine, [slot]: verdict };
    setMine(next); // optimistic: the button answers instantly
    setPending(slot);
    setError(null);
    try {
      await postJSON(`/api/rounds/${round.id}/verdicts`, { slot, verdict, voter: voterId() });
      localStorage.setItem(`tzij-verdicts-${round.id}`, JSON.stringify(next));
      setSaved(`Traducción ${slot + 1}: ${VERDICT_LABEL[verdict].toLowerCase()}. Ya aparece en la pantalla.`);
    } catch (e) {
      setMine(previous);
      setError(`No se guardó: ${(e as Error).message}. Intenta de nuevo.`);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="phone">
      <header className="phone__bar">
        <Wordmark />
        {round && <span className="phone__round">Ronda {round.number}</span>}
      </header>
      <main className="phone__main">
        {connection === "lost" && <p className="phone__alert" role="alert">Sin conexión con la laptop. Revisa que estés en la misma red; esta página se reconecta sola.</p>}
        {!data && connection !== "lost" && (
          <div className="phone__state" aria-busy="true"><h1>Conectando…</h1><p>Un momento.</p></div>
        )}
        {data && !round && (
          <div className="phone__state">
            <h1>Esperando la primera ronda</h1>
            <p>Cuando empiece, verás la frase y dos traducciones. Califica cada una: correcta, aceptable o incorrecta.</p>
          </div>
        )}
        {round && (
          <>
            <p className="phone__eyebrow">{directionLabel(round.direction)}</p>
            <h1 className="phone__phrase" lang={round.direction === "quc-es" ? "quc" : "es"}>{displaySource(round.source_text, round.direction)}</h1>
            {round.status === "translating" ? (
              [0, 1].map((slot) => (
                <section key={slot} className="tcard" aria-busy="true">
                  <p className="tcard__label">Traducción {slot + 1}</p>
                  <div className="skeleton-line" />
                  <p className="tcard__empty">Traduciendo…</p>
                </section>
              ))
            ) : (
              round.translations.map((t) => (
                <section key={t.slot} className="tcard fade-in" aria-labelledby={`t-${t.slot}`}>
                  <p className="tcard__label" id={`t-${t.slot}`}>Traducción {t.slot + 1}</p>
                  {t.status === "ok" ? (
                    <>
                      <p className="tcard__text" lang={round.direction === "es-quc" ? "quc" : "es"}>{displayTarget(t.text, round.direction)}</p>
                      {round.kind === "en_vivo" ? (
                        <div className="verdicts" role="group" aria-label={`Veredicto para la traducción ${t.slot + 1}`}>
                          {VERDICTS.map((v) => (
                            <button key={v} type="button" className={`verdict verdict--${v}`} aria-pressed={mine[t.slot] === v}
                              disabled={pending === t.slot} onClick={() => vote(t.slot, v)}>
                              <VerdictIcon verdict={v} size={22} />
                              {VERDICT_LABEL[v]}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className="tcard__empty">Ronda de evaluación: se califica sola con chrF++.</p>
                      )}
                    </>
                  ) : (
                    <p className="tcard__empty">{t.status === "offline" ? "Esta traducción no llegó: el modelo no tiene internet." : "Esta traducción falló."}</p>
                  )}
                </section>
              ))
            )}
            <p className="phone__saved" aria-live="polite">{saved}</p>
            {error && <p className="phone__alert" role="alert">{error}</p>}
            <p className="phone__note">No sabrás qué modelo hizo cada una.</p>
          </>
        )}
      </main>
    </div>
  );
}
