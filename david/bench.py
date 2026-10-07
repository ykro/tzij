"""Measure what the README's projections are built on: time, cost and throughput of both sides.

  uv run python david/bench.py [--page URL] [--rounds 3] [--concurrency 1,2,4,8,16]

1. Time and cost as the page shows them: every example phrase, ROUNDS times, through the public
   page's /api/translate (each side on its own, as the page asks). David's cost there is the
   seconds he worked × his GPU instance's price per second; Goliath's, his tokens × Gemini's price.
   With --david-service (a copy of David's service that nothing else uses, so other traffic such
   as `make eval` doesn't slow him down), David's side is asked to it directly and timed by it.
2. David's throughput: how many translations per hour one L4 instance finishes when C phrases
   arrive at once (C = 1, 2, 4, 8, 16), calling David's private service with your gcloud identity.

Writes david/bench-results.json. Needs David awake (open the page first) and `gcloud auth login`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "duel")]
OUT = Path(__file__).with_name("bench-results.json")


PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "ai-experiments-487722")


def gcloud(*args: str) -> str:
    project = ["--project", PROJECT] if args[:1] == ("run",) else []
    return subprocess.run(["gcloud", *args, *project], capture_output=True, text=True, check=True).stdout.strip()


def pct(values: list[float], q: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, round(q * (len(values) - 1)))]


async def direct_david(http: httpx.AsyncClient, ex: dict) -> dict:
    """David's side as the page computes it, but asked straight to a David service (its own time)."""
    from duel_core import chrf_pp
    from tzij_duel.settings import david_usd_per_s, get_settings

    r = (await http.post("/translate", json={"text": ex["text"], "direction": ex["direction"]})).json()
    gpu_s = round((r.get("latency_ms") or 0) / 1000, 2)
    return {"status": r["status"], "latency_ms": r.get("latency_ms"), "closeness": chrf_pp(r.get("text", ""), ex["reference"]),
            "cost": {"usd": gpu_s * david_usd_per_s(get_settings()), "gpu_seconds": gpu_s}}


async def page_rounds(page: str, rounds: int, david: httpx.AsyncClient | None = None) -> dict:
    async with httpx.AsyncClient(base_url=page, timeout=300) as http:
        examples = (await http.get("/api/examples")).json()
        rows = []
        for r in range(rounds):
            for ex in examples:
                for side in ("david", "goliath"):
                    if side == "david" and david is not None:
                        res = await direct_david(david, ex)
                    else:
                        body = {"text": ex["text"], "direction": ex["direction"], "example": ex["pair_id"], "side": side}
                        res = (await http.post("/api/translate", json=body)).json()[side]
                    if res["status"] == "ok":
                        rows.append({"round": r, "pair_id": ex["pair_id"], "side": side, "ms": res["latency_ms"],
                                     "usd": res["cost"]["usd"], "tokens": res["cost"].get("tokens"),
                                     "gpu_s": res["cost"].get("gpu_seconds"), "closeness": res["closeness"]})
    out = {"translations": rows}
    for side in ("david", "goliath"):
        ms = [x["ms"] for x in rows if x["side"] == side]
        usd = [x["usd"] for x in rows if x["side"] == side]
        out[side] = {"n": len(ms), "p50_ms": statistics.median(ms), "p95_ms": pct(ms, 0.95),
                     "mean_usd": statistics.mean(usd)}
        if side == "goliath":
            out[side]["mean_tokens"] = statistics.mean(x["tokens"] for x in rows if x["side"] == side)
    pairs = {}
    for x in rows:
        pairs.setdefault((x["round"], x["pair_id"]), {})[x["side"]] = x["ms"]
    out["david_faster"] = sum(1 for p in pairs.values() if len(p) == 2 and p["david"] < p["goliath"])
    out["pairs"] = sum(1 for p in pairs.values() if len(p) == 2)
    return out


async def throughput(david_url: str, levels: list[int], phrases: list[str]) -> list[dict]:
    token = gcloud("auth", "print-identity-token")
    headers = {"Authorization": f"Bearer {token}"}
    out = []
    async with httpx.AsyncClient(base_url=david_url, timeout=600, headers=headers) as http:
        for c in levels:
            n = max(4 * c, 16)
            queue = [phrases[i % len(phrases)] for i in range(n)]
            latencies: list[float] = []

            async def worker() -> None:
                while queue:
                    text = queue.pop()
                    t = time.perf_counter()
                    res = await http.post("/translate", json={"text": text, "direction": "es-quc"})
                    if res.status_code == 200 and res.json()["status"] == "ok":
                        latencies.append((time.perf_counter() - t) * 1000)

            t0 = time.perf_counter()
            await asyncio.gather(*(worker() for _ in range(c)))
            wall = time.perf_counter() - t0
            row = {"concurrency": c, "translations": len(latencies), "seconds": round(wall, 1),
                   "per_hour": round(len(latencies) / wall * 3600), "p50_ms": round(statistics.median(latencies)),
                   "p95_ms": round(pct(latencies, 0.95))}
            print("throughput", row, flush=True)
            out.append(row)
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--concurrency", default="1,2,4,8,16")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--david-service", default="tzij-david", help="another service with David's image, to measure without traffic")
    args = ap.parse_args()
    region = "europe-west4"
    page = args.page or gcloud("run", "services", "describe", "tzij", "--region", region, "--format=value(status.url)")
    david = gcloud("run", "services", "describe", args.david_service, "--region", region, "--format=value(status.url)")
    async with httpx.AsyncClient(base_url=page, timeout=30) as http:
        info = (await http.get("/api/info")).json()
        while args.rounds and not (await http.get("/api/david")).json().get("ready"):
            print("waiting for David to wake up…", flush=True)
            await asyncio.sleep(5)
        examples = (await http.get("/api/examples")).json()
    if args.david_service != "tzij-david":  # wake it and let its warm-up finish
        token = gcloud("auth", "print-identity-token")
        async with httpx.AsyncClient(base_url=david, timeout=600, headers={"Authorization": f"Bearer {token}"}) as http:
            while not (await http.get("/health")).json().get("ready"):
                await asyncio.sleep(5)
    direct = None
    if args.david_service != "tzij-david":
        direct = httpx.AsyncClient(base_url=david, timeout=600,
                                   headers={"Authorization": f"Bearer {gcloud('auth', 'print-identity-token')}"})
    timed = await page_rounds(page, args.rounds, direct) if args.rounds else {}
    print({k: v for k, v in timed.items() if k != "translations"}, flush=True)
    rates = await throughput(david, [int(x) for x in args.concurrency.split(",")], [e["text"] for e in examples])
    Path(args.out).write_text(json.dumps({"measured": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "date": date.today().isoformat(), "info": info, "page": timed,
                               "throughput": rates}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
