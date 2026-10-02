"""The BITÁCORA chart: David's chrF++ at each iteration, on the whole test sample and on the
pre-registered niche, against Goliath. Reads the predictions eval runs already produced.

    uv run python docs/diagrams/bitacora.py      -> bitacora.svg, bitacora.html, bitacora.json
    (then render the PNG: cd web && node tests/render-diagram.mjs bitacora)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from evals.niche_report import compare, load_rows, variant_file  # noqa: E402
from pipeline.niche import load_members  # noqa: E402

GOLIATH = ("final-20261002", "gemini-3.8-flash")
# (label line 1, label line 2, run, variant). Same 600 test sentences in every run.
STEPS = [
    ("E4B base", "sin datos", "final-20261002", "gemma4:e4b"),
    ("+ recuperación", "vectores", "final-20261002", "gemma4:e4b+rag"),
    ("+ híbrida", "BM25 + vectores", "final-20261002", "gemma4:e4b+hybrid"),
    ("+ RAFT", "+ retrotraducción", "final-20261002", "tzij-2026-10-raft-bt-s3+hybrid"),
    ("+ MBR", "4 muestras", "final-20261002", "tzij-2026-10-raft-bt-s3+hybrid+mbr4"),
]
EXTRA = HERE / "bitacora_steps.json"  # later rounds append here: [[l1, l2, run, variant], ...]


def numbers() -> dict:
    steps = STEPS + [tuple(x) for x in (json.loads(EXTRA.read_text()) if EXTRA.exists() else [])]
    test = ROOT / "data" / "processed"
    test = test / (test / "LATEST").read_text().strip() / "test.jsonl"
    records = {r["id"]: r for r in map(json.loads, test.read_text(encoding="utf-8").splitlines())}
    members = load_members()
    gol = load_rows(variant_file(ROOT / "evals" / "runs" / GOLIATH[0], GOLIATH[1]))
    out = {"goliath": GOLIATH[1], "steps": []}
    for l1, l2, run, variant in steps:
        dav = load_rows(variant_file(ROOT / "evals" / "runs" / run, variant))
        ids = sorted(set(dav) & set(gol) & set(records))
        niche = [i for i in ids if (records[i]["pair_id"], records[i]["direction"]) in members]
        a, n = compare(ids, dav, gol), compare(niche, dav, gol)
        out["steps"].append({"label": [l1, l2], "run": run, "variant": variant,
                             "all": round(a["david"], 1), "niche": round(n["david"], 1),
                             "goliath_all": round(a["goliath"], 1), "goliath_niche": round(n["goliath"], 1),
                             "niche_delta_ci": [round(x, 1) for x in n["ci"]], "niche_verdict": n["verdict"]})
    return out


def svg(data: dict) -> str:
    W, H, left, right, top, bottom = 1000, 520, 80, 960, 40, 400
    steps = data["steps"]
    pitch = (right - left) / len(steps)
    y = lambda v: bottom - (bottom - top) * v / 45  # noqa: E731
    xs = [left + pitch * (i + 0.5) for i in range(len(steps))]
    mono, sans = "'Geist Mono', monospace", "'Geist', sans-serif"
    g_all, g_niche = steps[-1]["goliath_all"], steps[-1]["goliath_niche"]
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="t d">',
             '<title id="t">Bitácora de David: chrF++ por iteración</title>',
             '<desc id="d">' + "; ".join(f"{s['label'][0]} {s['label'][1]}: {s['all']} en la prueba, {s['niche']} en el nicho"
                                         for s in steps) + f"; Goliath {g_all} y {g_niche} en el nicho.</desc>",
             f'<rect width="100%" height="100%" fill="#f5f5f5"/>']
    for v in (10, 20, 30, 40):
        parts.append(f'<line x1="{left}" y1="{y(v):.1f}" x2="{right}" y2="{y(v):.1f}" stroke="rgba(45,49,66,0.08)"/>')
        parts.append(f'<text x="{left - 8}" y="{y(v) + 4:.1f}" fill="#4f5d75" font-size="8" font-family="{mono}" text-anchor="end">{v}</text>')
    parts.append(f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="rgba(45,49,66,0.25)"/>')
    parts.append(f'<text transform="rotate(-90 24 220)" x="24" y="220" fill="#4f5d75" font-size="7" font-family="{mono}" '
                 f'letter-spacing="0.14em" text-anchor="middle">CHRF++ · 600 FRASES DE PRUEBA</text>')
    # Goliath reference lines
    for val, dash, label in ((g_all, "6,4", f"Goliath {g_all}"), (g_niche, "2,3", f"Goliath en el nicho {g_niche}")):
        parts.append(f'<line x1="{left}" y1="{y(val):.1f}" x2="{right}" y2="{y(val):.1f}" stroke="rgba(45,49,66,0.45)" stroke-dasharray="{dash}"/>')
    parts.append(f'<text x="{right}" y="{y(max(g_all, g_niche)) - 8:.1f}" fill="#2d3142" font-size="9" font-family="{sans}" text-anchor="end">'
                 f'Goliath (Gemini 3.8 Flash, nube): {g_all} · nicho {g_niche}</text>')
    for key, color, width in (("niche", "#3e5c76", 1.5), ("all", "#8c2f39", 2.2)):
        pts = " ".join(f"{x:.1f},{y(s[key]):.1f}" for x, s in zip(xs, steps))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"/>')
        for x, s in zip(xs, steps):
            parts.append(f'<circle cx="{x:.1f}" cy="{y(s[key]):.1f}" r="3.5" fill="#f5f5f5" stroke="{color}" stroke-width="{width}"/>')
            dy = -10 if key == "all" else 16
            parts.append(f'<text x="{x:.1f}" y="{y(s[key]) + dy:.1f}" fill="{color}" font-size="8.5" font-family="{mono}" '
                         f'text-anchor="middle"{" font-weight=\"600\"" if key == "all" else ""}>{s[key]}</text>')
    for x, s in zip(xs, steps):
        parts.append(f'<text x="{x:.1f}" y="{bottom + 20}" fill="#2d3142" font-size="10" font-weight="600" font-family="{sans}" text-anchor="middle">{s["label"][0]}</text>')
        parts.append(f'<text x="{x:.1f}" y="{bottom + 33}" fill="#4f5d75" font-size="8" font-family="{mono}" text-anchor="middle">{s["label"][1]}</text>')
    ly = H - 30
    parts += [f'<line x1="40" y1="{ly - 16}" x2="960" y2="{ly - 16}" stroke="rgba(45,49,66,0.10)"/>',
              f'<line x1="40" y1="{ly}" x2="62" y2="{ly}" stroke="#8c2f39" stroke-width="2.2"/>',
              f'<text x="68" y="{ly + 3}" fill="#4f5d75" font-size="8.5" font-family="{sans}">David, toda la prueba</text>',
              f'<line x1="210" y1="{ly}" x2="232" y2="{ly}" stroke="#3e5c76" stroke-width="1.5"/>',
              f'<text x="238" y="{ly + 3}" fill="#4f5d75" font-size="8.5" font-family="{sans}">David en el nicho pre-registrado (vocabulario de nuestros diccionarios)</text>',
              f'<text x="960" y="{ly + 3}" fill="#7a8399" font-size="8" font-family="{mono}" text-anchor="end">docs/BITACORA.md · evals/niche.md</text>',
              "</svg>"]
    return "\n".join(parts)


HTML = """<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bitácora de David</title>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;600&family=Geist+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>body{{margin:0;background:#f5f5f5;display:flex;justify-content:center;padding:2rem}} svg{{width:100%;max-width:1200px}}</style>
</head><body>
{svg}
</body></html>
"""


def main() -> None:
    data = numbers()
    (HERE / "bitacora.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    s = svg(data)
    (HERE / "bitacora.svg").write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + s + "\n", encoding="utf-8")
    (HERE / "bitacora.html").write_text(HTML.format(svg=s), encoding="utf-8")
    for st in data["steps"]:
        print(st["label"], st["all"], st["niche"], st["niche_verdict"], st["niche_delta_ci"])


if __name__ == "__main__":
    main()
