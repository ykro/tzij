"use client";

import { useEffect, useState } from "react";
import { VERDICT_LABEL, VerdictIcon } from "@/components/Verdict";
import { displayTarget, formatCost, formatSeconds, modelName } from "@/lib/kiche";
import type { ContenderName, ContenderResult, Direction, Round, VerdictName } from "@/lib/types";
import { answerSize } from "./sizing";

interface Props {
  name: ContenderName;
  model: string;
  round: Round | null;
  online: boolean;
}

const LABEL: Record<ContenderName, string> = { david: "David", goliath: "Goliath" };

function subtitle(name: ContenderName, model: string): string {
  return name === "david" ? `${modelName(model)} + datos Kʼicheʼ · en esta laptop` : `${modelName(model)} · en la nube`;
}

function Elapsed({ since }: { since: number }) {
  // Counts up while the model works: the latency race is part of the show.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, []);
  return <span className="num">{formatSeconds(Math.max(0, now - since * 1000))}</span>;
}

function Result({ result, direction, compact }: { result: ContenderResult; direction: Direction; compact: boolean }) {
  const text = displayTarget(result.text, direction);
  // A two-line phrase above leaves less room: answers drop one size step.
  const size = Math.round(answerSize(text) * (compact ? 0.8 : 1));
  return (
    <>
      <p className="side__text kiche fade-in" style={{ ["--answer-size" as string]: size }} lang={direction === "es-quc" ? "quc" : "es"}>
        {text || "—"}
      </p>
      <div className="side__meta num fade-in">
        <span>{formatSeconds(result.latency_ms)}</span>
        <span className="side__meta-sep" aria-hidden>·</span>
        <span>{formatCost(result.cost_usd)}</span>
      </div>
    </>
  );
}

export function Side({ name, model, round, online }: Props) {
  const result = round?.results[name];
  const other = round?.results[name === "david" ? "goliath" : "david"];
  const offline = result?.status === "offline" || (name === "goliath" && !online && !result);
  const classes = `side side--${name}${offline ? " side--offline" : ""}`;

  let body: React.ReactNode;
  if (!round) {
    body = name === "david" ? (
      <p className="side__intro">Un modelo pequeño que corre <strong>sin internet</strong>, con diccionarios y ejemplos Kʼicheʼ con licencia.</p>
    ) : (
      <p className="side__intro">Un modelo frontera en la nube, tal como lo usa cualquiera: <strong>sin datos extra</strong>.</p>
    );
  } else if (offline) {
    body = (
      <>
        <p className="side__offline fade-in">Sin conexión</p>
        <p className="side__offline-note fade-in">Goliath necesita internet. David traduce en esta laptop.</p>
      </>
    );
  } else if (!result) {
    body = (
      <p className="side__waiting" aria-live="polite">
        Traduciendo… <Elapsed since={round.created_at} />
      </p>
    );
  } else if (result.status === "error") {
    body = (
      <p className="side__error fade-in">
        No respondió
        {result.error && <small>{result.error}</small>}
      </p>
    );
  } else {
    body = <Result result={result} direction={round.direction} compact={round.source_text.length > 32 || !!round.reference} />;
  }

  return (
    <section className={classes} aria-label={LABEL[name]}>
      <header className="side__head">
        <span className="side__name">{LABEL[name]}</span>
        <span className="side__model">{subtitle(name, model)}</span>
      </header>
      <div className="side__body">{body}</div>
      <footer className="side__foot">{round && result?.status === "ok" && <RoundScore name={name} round={round} result={result} other={other} />}</footer>
    </section>
  );
}

function RoundScore({ name, round, result, other }: { name: ContenderName; round: Round; result: ContenderResult; other?: ContenderResult }) {
  if (round.kind === "evaluacion") {
    if (result.chrf == null) return null;
    // A win needs a rival: if the other side is offline or failed, there is no duel to win.
    const wins = other?.status === "ok" && other.chrf != null && result.chrf > other.chrf;
    return (
      <span className="score fade-in">
        chrF++ <b>{result.chrf.toLocaleString("es-GT", { maximumFractionDigits: 1, minimumFractionDigits: 1 })}</b>
        {wins && round.status === "done" && <span className="score__win">Gana la ronda</span>}
      </span>
    );
  }
  const tally = round.tallies[name];
  const given = (Object.keys(tally) as VerdictName[]).filter((v) => tally[v] > 0);
  if (!given.length) return <span className="side__awaiting">Esperando el veredicto de la validadora…</span>;
  return (
    <>
      {given.map((v) => (
        <span key={v} className={`badge badge--${v} fade-in`}>
          <VerdictIcon verdict={v} />
          {VERDICT_LABEL[v]}
          {tally[v] > 1 && <span className="badge__count">× {tally[v]}</span>}
        </span>
      ))}
    </>
  );
}
