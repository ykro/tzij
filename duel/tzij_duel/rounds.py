"""Rounds, verdicts and the scoreboard — the state of a talk.

Two kinds of round:
  evaluation  a test-set phrase with a reference translation: scored by chrF++
  live        any phrase from the stage: scored by the native speaker's verdicts
The validator sees both translations in a random order per round, without
names, so the verdict is about the translation, not about the brand.

State is a small JSON file: `make reset` deletes it and the talk starts clean.
"""

from __future__ import annotations

import json
import random
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

CONTENDERS = ("david", "goliath")
VERDICTS = ("correcta", "aceptable", "incorrecta")
EVALUATION, LIVE = "evaluacion", "en_vivo"


@dataclass
class Round:
    id: str
    number: int
    kind: str
    direction: str
    source_text: str
    reference: str | None = None
    reference_meta: dict[str, Any] | None = None
    status: str = "translating"  # translating -> done
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Blind order for the validator: slot 0/1 -> contender name.
    blind_order: list[str] = field(default_factory=list)
    # verdicts[contender][voter_id] = verdict
    verdicts: dict[str, dict[str, str]] = field(default_factory=lambda: {c: {} for c in CONTENDERS})
    created_at: float = field(default_factory=time.time)

    def tallies(self) -> dict[str, dict[str, int]]:
        return {c: {v: sum(1 for x in self.verdicts.get(c, {}).values() if x == v) for v in VERDICTS}
                for c in CONTENDERS}

    def public(self) -> dict[str, Any]:
        """What the presenter screen gets (names visible)."""
        data = asdict(self)
        data.pop("verdicts")
        data["tallies"] = self.tallies()
        return data

    def blind(self) -> dict[str, Any]:
        """What the phone gets: no model names, no latency, no cost, no reference."""
        slots = []
        for slot, name in enumerate(self.blind_order):
            result = self.results.get(name, {})
            slots.append({"slot": slot, "status": result.get("status", "translating"), "text": result.get("text", "")})
        return {"id": self.id, "number": self.number, "kind": self.kind, "direction": self.direction,
                "source_text": self.source_text, "status": self.status, "translations": slots}


class RoundStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.rounds: list[Round] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.rounds = [Round(**r) for r in raw.get("rounds", [])]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"rounds": [asdict(r) for r in self.rounds]}, ensure_ascii=False))
        tmp.replace(self.path)

    def create(self, *, kind: str, direction: str, source_text: str, reference: str | None = None,
               reference_meta: dict | None = None, rng: random.Random | None = None) -> Round:
        with self._lock:
            order = list(CONTENDERS)
            (rng or random).shuffle(order)
            round_ = Round(id=uuid.uuid4().hex[:10], number=len(self.rounds) + 1, kind=kind, direction=direction,
                           source_text=source_text, reference=reference, reference_meta=reference_meta,
                           blind_order=order)
            self.rounds.append(round_)
            self.save()
            return round_

    def get(self, round_id: str) -> Round | None:
        return next((r for r in self.rounds if r.id == round_id), None)

    @property
    def current(self) -> Round | None:
        return self.rounds[-1] if self.rounds else None

    def set_results(self, round_id: str, results: dict[str, dict]) -> Round | None:
        with self._lock:
            round_ = self.get(round_id)
            if round_ is None:  # reset while the round was translating: nothing to store
                return None
            round_.results = results
            round_.status = "done"
            self.save()
            return round_

    def vote(self, round_id: str, slot: int, verdict: str, voter: str) -> Round:
        if verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}")
        with self._lock:
            round_ = self.get(round_id)
            if round_ is None:
                raise KeyError(round_id)
            # The verdict endpoint is open on the LAN, so it only accepts what the validator can
            # legitimately do: judge the round on screen, once per translation.
            if round_ is not self.current:
                raise ValueError("Esa ronda ya terminó.")
            if round_.kind != LIVE:
                raise ValueError("Las rondas de evaluación se califican con chrF++, no con votos.")
            if round_.status != "done":
                raise ValueError("La ronda todavía se está traduciendo.")
            contender = round_.blind_order[slot]
            if round_.results.get(contender, {}).get("status") != "ok":
                raise ValueError("No hay traducción que calificar.")
            if round_.verdicts.get(contender):
                raise ValueError("Esta traducción ya tiene veredicto.")
            round_.verdicts.setdefault(contender, {})[voter] = verdict
            self.save()
            return round_

    def reset(self) -> None:
        with self._lock:
            self.rounds = []
            if self.path.exists():
                self.path.unlink()

    def scoreboard(self) -> dict[str, Any]:
        """chrF++ over evaluation rounds, verdict counts over live rounds."""
        board: dict[str, Any] = {}
        for name in CONTENDERS:
            chrfs = [r.results[name]["chrf"] for r in self.rounds
                     if r.kind == EVALUATION and r.status == "done"
                     and r.results.get(name, {}).get("chrf") is not None]
            counts = {v: 0 for v in VERDICTS}
            for r in self.rounds:
                if r.kind == LIVE:
                    for v, n in r.tallies()[name].items():
                        counts[v] += n
            cost = sum(r.results.get(name, {}).get("cost_usd") or 0.0 for r in self.rounds)
            board[name] = {
                "cost_usd": round(cost, 6),
                "chrf_mean": round(sum(chrfs) / len(chrfs), 2) if chrfs else None,
                "evaluation_rounds": len(chrfs),
                "verdicts": counts,
            }
        board["evaluation_wins"] = _wins(self.rounds)
        return board


def _wins(rounds: list[Round]) -> dict[str, int]:
    wins = {c: 0 for c in CONTENDERS} | {"empate": 0}
    for r in rounds:
        if r.kind != EVALUATION or r.status != "done":
            continue
        d, g = (r.results.get(c, {}).get("chrf") for c in CONTENDERS)
        if d is None or g is None:
            continue  # no rival (offline, error): nobody wins that round
        wins["david" if d > g else "goliath" if g > d else "empate"] += 1
    return wins
