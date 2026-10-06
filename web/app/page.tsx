"use client";

import { useEffect, useRef, useState } from "react";
import { Wordmark } from "@/components/Brand";
import { modelName } from "@/lib/kiche";
import {
  activeExample,
  cleanInput,
  closenessPercent,
  davidStatus,
  type DavidState,
  displayIn,
  type Example,
  failureText,
  languages,
  MAX_CHARS,
  postJSON,
  SIDES,
  type SideResult,
  type SideState,
  swapDirection,
  targetLang,
} from "@/lib/translator";
import type { ContenderName, Direction } from "@/lib/types";

const WHO: Record<ContenderName, { name: string; what: string; busy: string }> = {
  david: { name: "David", what: "modelo pequeño", busy: "David está traduciendo…" },
  goliath: { name: "Goliath", what: "modelo frontera", busy: "Goliath está traduciendo…" },
};

// While David's GPU wakes up the page asks every few seconds; once he's ready, once a minute while
// the page is visible, which also keeps him awake during the talk.
const WAKE_POLL_MS = 3000;
const AWAKE_POLL_MS = 60000;

type Sides = Record<ContenderName, SideState>;
const IDLE: Sides = { david: { phase: "idle" }, goliath: { phase: "idle" } };

interface Asked {
  text: string;
  direction: Direction;
  example: Example | null;
}

export default function Translator() {
  const [direction, setDirection] = useState<Direction>("es-quc");
  const [text, setText] = useState("");
  const [examples, setExamples] = useState<Example[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [asked, setAsked] = useState<Asked | null>(null);
  const [sides, setSides] = useState<Sides>(IDLE);
  const [david, setDavid] = useState<DavidState>({ ready: false, since: Date.now() });
  const [models, setModels] = useState<Record<ContenderName, string>>({ david: "", goliath: "" });
  const request = useRef(0);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    fetch("/api/examples").then((r) => (r.ok ? r.json() : [])).then(setExamples).catch(() => setExamples([]));
    fetch("/api/info").then((r) => r.json()).then((m) => setModels({ david: m.david ?? "", goliath: m.goliath ?? "" }))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let timer = 0;
    let stopped = false;
    const check = () => {
      if (document.visibilityState !== "visible") {
        timer = window.setTimeout(check, AWAKE_POLL_MS);
        return;
      }
      fetch("/api/david").then((r) => r.json()).then((d) => Boolean(d.ready)).catch(() => false).then((ready) => {
        if (stopped) return;
        setDavid((prev) => (prev.ready === ready ? prev : { ready, since: Date.now() }));
        timer = window.setTimeout(check, ready ? AWAKE_POLL_MS : WAKE_POLL_MS);
      });
    };
    check();
    return () => { stopped = true; window.clearTimeout(timer); };
  }, []);

  const busy = sides.david.phase === "busy" || sides.goliath.phase === "busy";
  const locked = busy || !david.ready;
  const status = davidStatus(david);

  function run(phrase: string, dir: Direction, example: Example | null) {
    const clean = cleanInput(phrase);
    if (!clean) return;
    const id = ++request.current;
    setAsked({ text: clean, direction: dir, example });
    setSides({ david: { phase: "busy" }, goliath: { phase: "busy" } });
    for (const side of SIDES) {
      postJSON<Record<ContenderName, SideResult>>("/api/translate", {
        text: clean, direction: dir, example: example?.pair_id ?? null, side,
      })
        .then((res) => {
          if (id !== request.current) return;
          setSides((prev) => ({ ...prev, [side]: { phase: "done", result: res[side] } }));
        })
        .catch((e: unknown) => {
          if (id !== request.current) return;
          // The service's own Spanish messages pass through; network failures get a plain sentence.
          const detail = e instanceof Error ? e.message : "";
          const message = !detail || detail.startsWith("Error") || /fetch|network|load failed/i.test(detail)
            ? "No hay conexión con la página. Revisa el internet y vuelve a intentar."
            : detail;
          setSides((prev) => ({ ...prev, [side]: { phase: "failed", message } }));
        });
    }
  }

  function submit() {
    run(text, direction, activeExample(examples, picked, text, direction));
  }

  function pick(example: Example) {
    setPicked(example.pair_id);
    setDirection(example.direction);
    setText(example.text);
    run(example.text, example.direction, example);
  }

  function swap() {
    setDirection(swapDirection(direction));
    setPicked(null);
    box.current?.focus();
  }

  const { from, to } = languages(direction);
  const shownDir = asked?.direction ?? direction;
  const outLang = targetLang(shownDir);
  const reference = asked?.example ?? null;

  return (
    <main className="tx">
      <header className="tx__bar">
        <Wordmark />
        <h1 className="tx__title">David contra Goliath · traducción español ↔ Kʼicheʼ</h1>
        <span className={`tx__net tx__net--${david.ready ? "on" : "waking"}`} role="status">
          <span aria-hidden className="tx__dot" />{status}
        </span>
      </header>

      <section className="tx__ask" aria-label="Frase para traducir">
        <form className="tx__compose" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <div className="tx__dir" role="group" aria-label="Dirección">
            <span className="tx__from">{from}</span>
            <button type="button" className="tx__swap" onClick={swap} disabled={locked} aria-label={`Cambiar dirección (ahora: ${from} a ${to})`}>
              <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden><path d="M7 7h12l-3.5-3.5M17 17H5l3.5 3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
            <span className="tx__to">{to}</span>
          </div>
          <label className="tx__field">
            <span className="visually-hidden">Frase en {from}</span>
            <textarea ref={box} value={text} maxLength={MAX_CHARS} rows={2} lang={direction === "es-quc" ? "es" : "quc"}
              className={direction === "quc-es" ? "kiche" : undefined}
              placeholder={direction === "es-quc" ? "Escribe una frase en español…" : "Escribe una frase en Kʼicheʼ…"}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
          </label>
          <button type="submit" className="tx__go" disabled={locked || !cleanInput(text)} aria-busy={busy}>
            {busy ? "Traduciendo…" : "Traducir"}
          </button>
        </form>

        {examples.length > 0 && (
          <div className="tx__examples">
            <p className="tx__examples-label" id="ex-label">Frases de Firefox Focus, con su traducción correcta:</p>
            <ul className="tx__chips" aria-labelledby="ex-label">
              {examples.map((ex) => (
                <li key={ex.pair_id}>
                  <button type="button" className="tx__chip" aria-pressed={reference?.pair_id === ex.pair_id} disabled={locked} onClick={() => pick(ex)}>
                    {ex.text}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {asked && (
        <section className="tx__ref fade-in" aria-label={reference ? "Traducción correcta" : "Frase"}>
          <p className="tx__ref-source" lang={shownDir === "es-quc" ? "es" : "quc"}>
            <span className="tx__ref-kicker">Frase en {shownDir === "es-quc" ? "español" : "Kʼicheʼ"}</span>
            <span>«{displayIn(asked.text, shownDir === "es-quc" ? "es" : "quc")}»</span>
          </p>
          {reference ? (
            <p className="tx__ref-line">
              <span className="tx__ref-label">Traducción correcta</span>
              <span className={`tx__ref-text${outLang === "quc" ? " kiche" : ""}`} lang={outLang}>{displayIn(reference.reference, outLang)}</span>
              <span className="tx__ref-credit">la hicieron personas para {reference.source}, licencia {reference.license.split(" ")[0]}</span>
            </p>
          ) : (
            <p className="tx__ref-line tx__ref-line--none">Frase escrita: no hay una traducción correcta con qué comparar. Mira las dos lado a lado.</p>
          )}
        </section>
      )}

      <section className="tx__duel" aria-label="Las dos traducciones">
        {SIDES.map((side) => (
          <Column key={side} side={side} state={sides[side]} model={models[side]} outLang={outLang} hasReference={Boolean(reference)}
            started={Boolean(asked)} ready={david.ready} />
        ))}
      </section>

      <footer className="tx__foot">
        Las frases de ejemplo son de Firefox Focus: David nunca las vio al entrenar, pero tiene la memoria de traducción de
        los demás productos de Mozilla. «Se parece a la correcta» cuenta cuántas letras y palabras comparte cada
        traducción con la que hicieron personas (la medida chrF++): 100 % es idéntica.
      </footer>
    </main>
  );
}

function Column({ side, state, model, outLang, hasReference, started, ready }: {
  side: ContenderName; state: SideState; model: string; outLang: "es" | "quc"; hasReference: boolean; started: boolean; ready: boolean;
}) {
  const who = WHO[side];
  const result = state.phase === "done" ? state.result : null;
  const failure = state.phase === "failed" ? state.message : result ? failureText(result) : null;
  const percent = result && !failure ? closenessPercent(result.closeness) : null;
  return (
    <article className={`tx__col tx__col--${side}`} aria-busy={state.phase === "busy"} aria-live="polite">
      <header className="tx__col-head">
        <h2 className="tx__name">{who.name}</h2>
        <p className="tx__who">{model ? `${modelName(model)} · ` : ""}<b>{who.what}</b></p>
      </header>

      <div className="tx__body">
        {state.phase === "busy" ? (
          <div className="tx__busy">
            <span className="tx__skel" /><span className="tx__skel tx__skel--short" />
            <p>{who.busy}</p>
          </div>
        ) : failure ? (
          <p className="tx__fail">{failure}</p>
        ) : result ? (
          <p className={`tx__out${outLang === "quc" ? " kiche" : ""}`} lang={outLang}>{displayIn(result.text, outLang)}</p>
        ) : (
          <p className="tx__idle">{started ? "" : side === "david"
            ? (ready ? "Toca una frase de ejemplo o escribe la tuya." : "David se está encendiendo en su GPU en la nube: tarda unos 3 minutos. Después responde en segundos.")
            : "Aquí sale la traducción de Goliath, para compararla."}</p>
        )}
      </div>

      {hasReference && (
        <div className="tx__meter" data-empty={percent == null || undefined}>
          <div className="tx__meter-row">
            <span>Se parece a la correcta</span>
            <b className="num">{percent == null ? "" : `${percent} %`}</b>
          </div>
          <div className="tx__track" role="meter" aria-label={`${who.name}: se parece a la correcta`} aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={percent ?? undefined}>
            <div className="tx__fill" style={{ transform: `scaleX(${(percent ?? 0) / 100})` }} />
          </div>
        </div>
      )}

    </article>
  );
}
