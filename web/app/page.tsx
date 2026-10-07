"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Wordmark } from "@/components/Brand";
import { modelName } from "@/lib/kiche";
import {
  activeExample,
  cleanInput,
  closenessPercent,
  costBasis,
  costPerThousand,
  davidStatus,
  type DavidState,
  displayIn,
  type Evidence,
  type Example,
  failureText,
  formatCost,
  formatSeconds,
  languages,
  MAX_CHARS,
  postJSON,
  type Reference,
  referenceOrigin,
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
  id: number;
  text: string;
  direction: Direction;
  example: Example | null;
}

type TranslateResponse = Partial<Record<ContenderName, SideResult>> & { reference: Reference | null };

export default function Translator() {
  const [direction, setDirection] = useState<Direction>("es-quc");
  const [text, setText] = useState("");
  const [examples, setExamples] = useState<Example[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [asked, setAsked] = useState<Asked | null>(null);
  const [sides, setSides] = useState<Sides>(IDLE);
  const [reference, setReference] = useState<Reference | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
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

  // A typed phrase without a correct translation: once both have answered, fetch what helps judge them.
  const davidText = sides.david.phase === "done" && sides.david.result.status === "ok" ? sides.david.result.text : null;
  const goliathText = sides.goliath.phase === "done" && sides.goliath.result.status === "ok" ? sides.goliath.result.text : null;
  const bothSettled = sides.david.phase !== "busy" && sides.goliath.phase !== "busy" && sides.david.phase !== "idle";
  useEffect(() => {
    if (!asked || asked.example || reference || !bothSettled || (!davidText && !goliathText)) return;
    const id = asked.id;
    const outputs: Record<string, string> = {};
    if (davidText) outputs.david = davidText;
    if (goliathText) outputs.goliath = goliathText;
    postJSON<Evidence>("/api/evidence", { text: asked.text, direction: asked.direction, outputs })
      .then((ev) => { if (id === request.current) setEvidence(ev); })
      .catch(() => undefined);
  }, [asked, reference, bothSettled, davidText, goliathText]);

  const busy = sides.david.phase === "busy" || sides.goliath.phase === "busy";
  const locked = busy || !david.ready;
  const status = davidStatus(david);

  function run(phrase: string, dir: Direction, example: Example | null) {
    const clean = cleanInput(phrase);
    if (!clean) return;
    const id = ++request.current;
    setAsked({ id, text: clean, direction: dir, example });
    setReference(null);
    setEvidence(null);
    setSides({ david: { phase: "busy" }, goliath: { phase: "busy" } });
    for (const side of SIDES) {
      postJSON<TranslateResponse>("/api/translate", {
        text: clean, direction: dir, example: example?.pair_id ?? null, side,
      })
        .then((res) => {
          if (id !== request.current) return;
          if (res.reference) setReference(res.reference);
          const result = res[side];
          if (result) setSides((prev) => ({ ...prev, [side]: { phase: "done", result } }));
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

  // Example buttons grouped by where their correct translation comes from.
  const groups = useMemo(() => {
    const by = new Map<string, Example[]>();
    for (const ex of examples) by.set(ex.source, [...(by.get(ex.source) ?? []), ex]);
    return [...by.entries()];
  }, [examples]);

  const { from, to } = languages(direction);
  const shownDir = asked?.direction ?? direction;
  const outLang = targetLang(shownDir);
  const inLang = shownDir === "es-quc" ? "es" : "quc";

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

        {groups.map(([source, items], i) => (
          <div className="tx__examples" key={source}>
            <p className="tx__examples-label" id={`ex-label-${i}`}>Frases de {source.replace(/^Mozilla Pontoon \((.+)\)$/, "$1")}, con su traducción correcta:</p>
            <ul className="tx__chips" aria-labelledby={`ex-label-${i}`}>
              {items.map((ex) => (
                <li key={ex.pair_id}>
                  <button type="button" className="tx__chip" aria-pressed={asked?.example?.pair_id === ex.pair_id} disabled={locked} onClick={() => pick(ex)}>
                    {ex.text}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      {asked && (
        <section className={`tx__ref fade-in${reference || asked.example ? "" : " tx__ref--typed"}`} aria-label="La frase y su traducción correcta">
          <p className="tx__ref-source" lang={inLang}>
            <span className="tx__ref-kicker">Frase en {inLang === "es" ? "español" : "Kʼicheʼ"}</span>
            <span>«{displayIn(asked.text, inLang)}»</span>
          </p>
          {reference ? (
            <p className="tx__ref-line">
              <span className="tx__ref-label">Traducción correcta</span>
              <span className={`tx__ref-text${outLang === "quc" ? " kiche" : ""}`} lang={outLang}>{displayIn(reference.text, outLang)}</span>
              <span className="tx__ref-credit">
                {reference.where === "ejemplo" ? `la hicieron personas para ${reference.source}` : referenceOrigin(reference)}
                {reference.license ? ` · licencia ${reference.license.split(" ")[0]}` : ""}
              </span>
            </p>
          ) : asked.example ? null : (
            <div className="tx__ref-line tx__ref-line--none">
              <p>
                Esta frase no tiene una traducción hecha por personas, así que no se puede medir cuál se acercó más.
                {evidence?.memory.length ? " Para juzgar: abajo, las frases más parecidas de la memoria de traducción, traducidas por personas. En cada columna se marcan las palabras que también usan esas traducciones." : ""}
              </p>
              {evidence && evidence.memory.length > 0 && (
                <ul className="tx__memory" aria-label="Frases parecidas en la memoria de traducción">
                  {evidence.memory.map((m, i) => (
                    <li key={i}>
                      <span lang={inLang}>{displayIn(m.source_text, inLang)}</span>
                      <span aria-hidden className="tx__arrow">→</span>
                      <span className={outLang === "quc" ? "kiche" : undefined} lang={outLang}>{displayIn(m.target_text, outLang)}</span>
                      <small>{m.source}</small>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      <section className="tx__duel" aria-label="Las dos traducciones">
        {SIDES.map((side) => (
          <Column key={side} side={side} state={sides[side]} model={models[side]} outLang={outLang}
            measured={Boolean(reference)} marked={reference ? undefined : evidence?.words[side]}
            started={Boolean(asked)} ready={david.ready} />
        ))}
      </section>

      <footer className="tx__foot">
        <p>
          <b>¿Qué es «se parece a la correcta»?</b> Compara cada traducción con la que hicieron personas, en pedacitos de
          letras y palabras, y dice qué parte comparten: 100 % es idéntica y 0 % no tiene nada en común. Por ejemplo, si la
          correcta es «Chajital tʼiqonem», la traducción «Chajital tʼiqoj» se parece en 66 % (comparte la primera palabra
          y parte de la segunda) y «Jikilik tʼiqoj», en 16 %. Es la medida chrF++, la que se usa para comparar
          traductores automáticos.
        </p>
        <p>
          <b>Tiempo y costo</b> son los de esta traducción. David corre en su propia GPU en la nube, que se cobra por
          segundo mientras está encendida: su costo son los segundos que trabajó. Goliath cobra por tokens (los pedazos de
          texto que lee y escribe), al precio de lista de Gemini del día.
        </p>
        {examples.length > 0 && (
          <p>
            Las frases de ejemplo son de Firefox Focus: David nunca las vio al entrenar, pero tiene la memoria de traducción
            de los demás productos de Mozilla.
          </p>
        )}
      </footer>
    </main>
  );
}

function Column({ side, state, model, outLang, measured, marked, started, ready }: {
  side: ContenderName; state: SideState; model: string; outLang: "es" | "quc"; measured: boolean;
  marked: { word: string; in_memory: boolean }[] | undefined; started: boolean; ready: boolean;
}) {
  const who = WHO[side];
  const result = state.phase === "done" ? state.result : null;
  const failure = state.phase === "failed" ? state.message : result ? failureText(result) : null;
  const percent = result && !failure ? closenessPercent(result.closeness) : null;
  const ok = result && !failure ? result : null;
  const shared = marked?.filter((w) => w.in_memory).length ?? 0;
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
        ) : ok ? (
          <p className={`tx__out${outLang === "quc" ? " kiche" : ""}`} lang={outLang}>
            {marked && marked.length > 0
              ? marked.map((w, i) => (
                <span key={i}>{i > 0 ? " " : ""}<span className={w.in_memory ? "tx__hit" : undefined}>{displayIn(w.word, outLang)}</span></span>
              ))
              : displayIn(ok.text, outLang)}
          </p>
        ) : (
          <p className="tx__idle">{started ? "" : side === "david"
            ? (ready ? "Toca una frase de ejemplo o escribe la tuya." : "David se está encendiendo en su GPU en la nube. Después responde en segundos.")
            : "Aquí sale la traducción de Goliath, para compararla."}</p>
        )}
      </div>

      {marked && ok && (
        <p className="tx__shared">
          {shared > 0
            ? <><b className="num">{shared} de {marked.length}</b> palabras también están en las traducciones de la memoria</>
            : "Ninguna palabra coincide con las traducciones de la memoria"}
        </p>
      )}

      {measured && (
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

      <dl className="tx__facts" data-empty={ok ? undefined : true}>
        <div>
          <dt>Tiempo</dt>
          <dd className="num">{ok ? formatSeconds(ok.latency_ms) : "—"}</dd>
        </div>
        <div>
          <dt>Costo de esta traducción</dt>
          <dd className="num">{ok?.cost ? formatCost(ok.cost.usd) : "—"}</dd>
          {ok?.cost && <dd className="tx__fact-note">{costBasis(ok.cost)} · {costPerThousand(ok.cost.usd)}</dd>}
        </div>
      </dl>
    </article>
  );
}
