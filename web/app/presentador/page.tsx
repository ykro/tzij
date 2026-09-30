"use client";

import { useCallback, useEffect, useState } from "react";
import { Wordmark } from "@/components/Brand";
import { QrCode } from "@/components/QrCode";
import { CommandBar } from "@/components/presenter/CommandBar";
import { ModelCardPanel, ModelCardStrip } from "@/components/presenter/ModelCardPanel";
import { Scoreboard } from "@/components/presenter/Scoreboard";
import { Side } from "@/components/presenter/Side";
import { phraseSize } from "@/components/presenter/sizing";
import { directionLabel, displayKiche, displaySource } from "@/lib/kiche";
import type { Direction, PresenterState } from "@/lib/types";
import { postJSON, useEventState } from "@/lib/useEventState";

export default function Presenter() {
  const { data: state, connection } = useEventState<PresenterState>("presenter", "state");
  const [commandOpen, setCommandOpen] = useState(false);
  const [cardOpen, setCardOpen] = useState(false);
  const [direction, setDirection] = useState<Direction>("es-quc");

  const round = state?.round ?? null;
  const busy = round?.status === "translating";

  const evaluationRound = useCallback(() => {
    postJSON("/api/rounds", { kind: "evaluacion", direction }).catch(() => setCommandOpen(true));
  }, [direction]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const typing = (e.target as HTMLElement)?.closest("input, textarea");
      if (typing) return;
      if (e.key === "/") {
        e.preventDefault();
        setCommandOpen(true);
      } else if (e.key === "Escape") {
        setCommandOpen(false);
        setCardOpen(false);
      } else if (e.key.toLowerCase() === "e" && !busy) {
        evaluationRound();
      } else if (e.key.toLowerCase() === "d") {
        setDirection((d) => (d === "es-quc" ? "quc-es" : "es-quc"));
      } else if (e.key.toLowerCase() === "m") {
        setCardOpen((o) => !o);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, evaluationRound]);

  if (!state) {
    return (
      <main className="stage" aria-busy={connection !== "lost"}>
        <header className="stage__bar"><Wordmark /></header>
        <section className="phrase phrase--empty">
          <p className="eyebrow">{connection === "lost" ? "Sin servicio" : "Conectando"}</p>
          <p className="phrase__text" style={{ ["--phrase-size" as string]: 88 }}>
            {connection === "lost" ? "No hay conexión con el servicio del duelo." : "Preparando el duelo…"}
          </p>
          {connection === "lost" && <p className="phrase__hint">Arráncalo con <kbd>make up</kbd>; esta pantalla se reconecta sola.</p>}
        </section>
      </main>
    );
  }

  const source = round ? displaySource(round.source_text, round.direction) : "";
  const reference = round?.kind === "evaluacion" && round.reference ? round.reference : null;

  return (
    <main className="stage">
      <header className="stage__bar">
        <Wordmark />
        <div className="stage__status">
          <button type="button" className="stage__new" onClick={() => setCommandOpen((o) => !o)} aria-expanded={commandOpen}>
            Nueva ronda<kbd>/</kbd>
          </button>
          {state.online ? (
            <span className="pill pill--online"><span className="pill__dot" aria-hidden />En línea</span>
          ) : (
            <span className="pill pill--offline" role="status"><span className="pill__dot" aria-hidden />Sin conexión</span>
          )}
          <div className="stage__qr">
            <QrCode value={state.validator_url} />
            <span>Valida desde<br />tu teléfono</span>
          </div>
        </div>
      </header>

      {connection === "lost" && <div className="banner" role="alert">Se perdió la conexión con el servicio del duelo · reintentando…</div>}

      {round ? (
        <section className="phrase" aria-live="polite">
          <p className="eyebrow">
            <span>{directionLabel(round.direction)}</span>
            <span className="eyebrow__sep" aria-hidden>·</span>
            <span className="num">Ronda {round.number}</span>
            <span className="eyebrow__sep" aria-hidden>·</span>
            <span className={round.kind === "en_vivo" ? "eyebrow__kind--live" : undefined}>
              {round.kind === "en_vivo" ? "En vivo" : "Evaluación"}
            </span>
          </p>
          <p className={`phrase__text${round.direction === "quc-es" ? " kiche" : ""}`} style={{ ["--phrase-size" as string]: phraseSize(source) }}
            lang={round.direction === "quc-es" ? "quc" : "es"}>
            {source}
          </p>
          {reference && (
            <p className="phrase__reference">
              <b>Referencia</b> ({round.reference_meta?.source_name === "bloom_kiche" ? "Bloom Library, MINEDUC" : round.reference_meta?.source_name}):{" "}
              <span className={round.direction === "es-quc" ? "kiche" : undefined}>
                {round.direction === "es-quc" ? displayKiche(reference) : reference}
              </span>
            </p>
          )}
        </section>
      ) : (
        <section className="phrase phrase--empty">
          <p className="eyebrow">David contra Goliath</p>
          <p className="phrase__text" style={{ ["--phrase-size" as string]: 96 }}>Listo para la primera ronda.</p>
          <p className="phrase__hint">
            <kbd>/</kbd> escribir una frase · <kbd>E</kbd> frase de evaluación · <kbd>D</kbd> cambiar dirección · <kbd>M</kbd> ficha del modelo
          </p>
        </section>
      )}

      <div className="duel">
        <Side name="david" model={state.contenders.david.model} round={round} online={state.online} />
        <Side name="goliath" model={state.contenders.goliath.model} round={round} online={state.online} />
      </div>

      <footer className="stage__foot">
        <ModelCardStrip card={state.model_card} open={cardOpen} onToggle={() => setCardOpen((o) => !o)} />
        <Scoreboard state={state} />
      </footer>

      {cardOpen && <ModelCardPanel card={state.model_card} />}
      {commandOpen && (
        <CommandBar direction={direction} onDirection={setDirection} busy={busy} forceOffline={state.force_offline}
          onClose={() => setCommandOpen(false)} />
      )}
    </main>
  );
}
