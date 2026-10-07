"""Which use cases does David win as a set? Measured against the cloud David, like the page.

Each use case is a fixed, seeded sample of licensed pairs (never picked by result). For each pair,
David (his GPU service, retrieval + MBR-4, exactly as the page calls him), Goliath (Gemini alone)
and Goliath with David's same retrieved context translate it. The report gives corpus chrF++ with
a 95 % bootstrap interval of David − Goliath and, for single terms, how often the translation is
exactly the dictionary's (ignoring case and punctuation).

  make david-proxy                                   # other terminal: retrieval embeddings
  uv run python evals/usecases.py                    # -> evals/usecases_results.md + evals/runs/usecases/

Use cases measured here (the translation-memory case is evals/niche_results.md and tm_new):
  terminos_gatitos   everyday vocabulary from GATITOS (Google Research, CC BY 4.0): words of the
                     dictionary David consults; Goliath has no such dictionary.
  emoji_cldr         emoji names from Unicode CLDR (Unicode License V3): the same, with a
                     terminology a general audience recognizes.
Both are in David's retrieval index: what's measured is "an organization with its own glossary",
not translating unseen text. General translation (unseen sentences) is in evals/report.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sqlite3
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "duel")]

from sacrebleu.metrics import CHRF  # noqa: E402

from data.normalize import match_key  # noqa: E402

RUN = ROOT / "evals" / "runs" / "usecases"
REPORT = ROOT / "evals" / "usecases_results.md"
USE_CASES = {
    "terminos_gatitos": ("gatitos", "Vocabulario cotidiano del diccionario GATITOS (Google Research, CC BY 4.0)", 150),
    "emoji_cldr": ("cldr_quc", "Nombres de emoji de Unicode CLDR (Unicode License V3)", 100),
}
SEED = 2027


def sample(index: Path, source: str, n: int) -> list[dict]:
    db = sqlite3.connect(index)
    rows = db.execute("SELECT record_id, source_text, target_text, license, url FROM entries "
                      "WHERE source_name = ? AND direction = 'es-quc' ORDER BY record_id", (source,)).fetchall()
    seen, out = set(), []
    for rid, src, tgt, lic, url in rows:  # one translation per Spanish term: the first in the dictionary
        if match_key(src) in seen:
            continue
        seen.add(match_key(src))
        out.append({"id": rid, "source_text": src, "reference": tgt, "license": lic, "url": url})
    random.Random(SEED).shuffle(out)
    return out[:n]


def bootstrap(d: list[str], g: list[str], refs: list[str], reps: int = 1000) -> tuple[float, float]:
    chrf = CHRF(word_order=2)
    rng = random.Random(SEED)
    idx = list(range(len(refs)))
    deltas = []
    for _ in range(reps):
        s = [rng.choice(idx) for _ in idx]
        deltas.append(chrf.corpus_score([d[i] for i in s], [[refs[i] for i in s]]).score
                      - chrf.corpus_score([g[i] for i in s], [[refs[i] for i in s]]).score)
    deltas.sort()
    return deltas[int(0.025 * reps)], deltas[int(0.975 * reps)]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--david-service", default="tzij-david")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    from tzij_duel.settings import get_settings
    from tzij_duel.variants import Variant, gemini_price, goliath_variant, load_retriever, translate

    s = get_settings()
    gcloud = ["gcloud", "--project", s.project]
    url = subprocess.run([*gcloud, "run", "services", "describe", args.david_service, "--region", "europe-west4",
                          "--format=value(status.url)"], capture_output=True, text=True, check=True).stdout.strip()
    token = subprocess.run(["gcloud", "auth", "print-identity-token"], capture_output=True, text=True, check=True).stdout.strip()
    goliath = goliath_variant(s)
    retriever = load_retriever(s)
    with_glossary = Variant("goliath+glosario", "Goliath + glosario", goliath.client, goliath.model,
                            gemini_price(s), True, True, retrieval=s.rag_mode, k=s.rag_k)
    RUN.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)
    results = {}
    async with httpx.AsyncClient(base_url=url, timeout=300, headers={"Authorization": f"Bearer {token}"}) as david:
        for name, (source, label, n) in USE_CASES.items():
            path = RUN / f"{name}.jsonl"
            done = {json.loads(line)["id"]: json.loads(line) for line in path.read_text().splitlines()} if path.exists() else {}
            items = sample(s.rag_index, source, n)

            async def one(item: dict) -> dict:
                if item["id"] in done:
                    return done[item["id"]]
                async with sem:
                    d = (await david.post("/translate", json={"text": item["source_text"], "direction": "es-quc"})).json()
                    g = await translate(goliath, item["source_text"], "es-quc", retriever=None, online=True)
                    gg = await translate(with_glossary, item["source_text"], "es-quc", retriever=retriever, online=True)
                row = {**item, "david": d.get("text", ""), "goliath": g.text, "goliath_glossary": gg.text}
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                return row

            rows = await asyncio.gather(*(one(it) for it in items))
            refs = [r["reference"] for r in rows]
            chrf = CHRF(word_order=2)
            score = {k: round(chrf.corpus_score([r[k] for r in rows], [refs]).score, 1) for k in ("david", "goliath", "goliath_glossary")}
            exact = {k: round(100 * sum(match_key(r[k]) == match_key(r["reference"]) for r in rows) / len(rows))
                     for k in ("david", "goliath", "goliath_glossary")}
            lo, hi = bootstrap([r["david"] for r in rows], [r["goliath"] for r in rows], refs)
            results[name] = {"label": label, "n": len(rows), "chrf": score, "exact": exact, "ci": (round(lo, 1), round(hi, 1))}
            print(name, results[name], flush=True)

    lines = ["# Casos de uso medidos como conjunto", "",
             "Generado por `evals/usecases.py` contra el David de la nube (recuperación híbrida + MBR-4, como la página), "
             "Goliath (`" + s.gemini_model + "` solo) y Goliath con el mismo contexto recuperado de David. Muestra fija con semilla "
             f"{SEED}, español → Kʼicheʼ. Los términos están en el índice de David: se mide una organización con su propio "
             "glosario, no traducir texto nuevo.", "",
             "| Caso de uso | n | David chrF++ | Goliath chrF++ | David − Goliath [IC 95 %] | Exacta: David | Goliath | Goliath + glosario |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, r in results.items():
        lines.append(f"| {r['label']} | {r['n']} | **{r['chrf']['david']}** | {r['chrf']['goliath']} | "
                     f"{r['chrf']['david'] - r['chrf']['goliath']:+.1f} [{r['ci'][0]:+.1f}, {r['ci'][1]:+.1f}] | "
                     f"{r['exact']['david']} % | {r['exact']['goliath']} % | {r['exact']['goliath_glossary']} % |")
    lines += ["", "chrF++ de Goliath + glosario: " + ", ".join(f"{r['label'].split(' (')[0]} {r['chrf']['goliath_glossary']}"
                                                               for r in results.values()) + ".", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    (RUN / "summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    asyncio.run(main())
