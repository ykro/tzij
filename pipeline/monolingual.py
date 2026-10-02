"""Monolingual K'iche' for back-translation (make monolingual -> data/monolingual/quc.jsonl).

Human-written K'iche' only, from licensed train-side sources. Never from a test source (Bloom,
BOUQuET), and any sentence that also appears in the test set or already has a Spanish pair in train
is dropped. These sentences never enter retrieval or the test set: they become the K'iche' side of
back-translated training pairs (pipeline/back_translate.py).

Sources:
  incubator_quc   Wikipedia in K'iche' (Wikimedia Incubator, Wp/quc), CC BY-SA 4.0
  spacescoop_quc  Space Scoop / UNAWE astronomy news for kids in K'iche', CC BY 4.0
  ud_kiche_iu     UD K'iche'-IU sentences that have no Spanish translation, CC BY-SA 4.0
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from pathlib import Path
from typing import Iterable

import httpx

from data.normalize import match_key, normalize_kiche
from pipeline.clean import OTHER_MAYAN_RE, SPANISH_FUNCTION_WORDS
from pipeline.sources.base import USER_AGENT, download

REPO = Path(__file__).resolve().parent.parent
RAW = REPO / "data" / "raw" / "monolingual"
OUT = REPO / "data" / "monolingual" / "quc.jsonl"
INCUBATOR_API = "https://incubator.wikimedia.org/w/api.php"
UNAWE = "https://www.unawe.org"

LICENSES = {
    "incubator_quc": "CC-BY-SA-4.0 (Wikimedia Incubator, Wp/quc)",
    "spacescoop_quc": "CC-BY-4.0 (Space Scoop, UNAWE; credit SpaceScoop.org)",
    "ud_kiche_iu": "CC-BY-SA-4.0 (UD K'iche'-IU; used with permission of ALMG and T. Can Pixabaj)",
}


def _get(url: str, **params) -> httpx.Response:
    for attempt in range(4):
        try:
            res = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)
            res.raise_for_status()
            return res
        except httpx.HTTPError:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}")


def fetch_incubator(raw: Path) -> Path:
    dest = raw / "incubator_quc.json"
    if dest.exists():
        return dest
    titles, cont = [], {}
    while True:
        data = _get(INCUBATOR_API, action="query", list="allpages", apprefix="Wp/quc/", aplimit=500, format="json", **cont).json()
        titles += [p["title"] for p in data["query"]["allpages"]]
        if "continue" not in data:
            break
        cont = data["continue"]
    pages = []
    for i in range(0, len(titles), 20):
        data = _get(INCUBATOR_API, action="query", prop="extracts", explaintext=1, exlimit=20,
                    titles="|".join(titles[i:i + 20]), format="json").json()
        for page in data["query"]["pages"].values():
            if page.get("extract"):
                pages.append({"title": page["title"], "text": page["extract"],
                              "url": "https://incubator.wikimedia.org/wiki/" + page["title"].replace(" ", "_")})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(pages, ensure_ascii=False))
    return dest


def fetch_spacescoop(raw: Path) -> Path:
    dest = raw / "spacescoop_quc.json"
    if dest.exists():
        return dest
    listing = _get(f"{UNAWE}/kids/archive/lang/quc/viewall/").text
    paths = sorted(set(re.findall(r'href="(/kids/unawe\d+/quc/)"', listing)))
    articles = []
    for path in paths:
        page = _get(UNAWE + path).text
        paragraphs = [html.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in re.findall(r"<p[^>]*>(.*?)</p>", page, re.S)]
        body = [p for p in paragraphs if len(p) > 40 and "UNAWE" not in p and "Inspiring every child" not in p]
        articles.append({"url": UNAWE + path, "text": "\n".join(body)})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(articles, ensure_ascii=False))
    return dest


def ud_monolingual() -> Iterable[tuple[str, str]]:
    conllu = REPO / "data" / "raw" / "ud_kiche_iu" / "quc_iu-ud-test.conllu"
    if not conllu.exists():
        return
    for block in conllu.read_text(encoding="utf-8").split("\n\n"):
        meta = dict(re.findall(r"^# ([^=]+?) = (.*)$", block, flags=re.M))
        origin = meta.get("sent_id", "").split(":")[0]
        if any(k.startswith("text[spa") for k in meta) or origin not in ("wikipedia", "utexas", "cuentos"):
            continue  # skip pairs (already used) and segmented linguistic examples
        text = meta.get("text[orig]") or meta.get("text")
        if text:
            yield text, "https://github.com/UniversalDependencies/UD_Kiche-IU"


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[¿¡\"'A-ZÁÉÍÓÚÑ])")
_REFERENCE = re.compile(r"\[\d+\]")


def sentences(text: str) -> list[str]:
    out = []
    for paragraph in text.split("\n"):
        paragraph = _REFERENCE.sub("", paragraph).strip()
        if not paragraph or paragraph.startswith("="):
            continue
        out += [s.strip() for s in _SENTENCE_SPLIT.split(paragraph) if s.strip()]
    return out


def looks_kiche(sentence: str) -> bool:
    words = [w.strip(".,;:!?¿¡\"()").lower() for w in sentence.split()]
    if not 4 <= len(words) <= 40:
        return False
    if sum(w in SPANISH_FUNCTION_WORDS for w in words) / len(words) >= 0.25:
        return False  # mostly Spanish (common in the Incubator's medical pages)
    if len(OTHER_MAYAN_RE.findall(sentence)) >= 2:
        return False
    return "'" in normalize_kiche(sentence)  # K'iche' prose almost always has glottal stops


def collect(processed: Path) -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    version = (processed / "LATEST").read_text().strip()
    known = set()
    for split in ("train", "dev", "test"):
        for line in (processed / version / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            known.add(match_key(r["target_text"] if r["direction"] == "es-quc" else r["source_text"]))
    candidates: list[tuple[str, str, str]] = []
    for page in json.loads(fetch_incubator(RAW).read_text()):
        candidates += [(s, "incubator_quc", page["url"]) for s in sentences(page["text"])]
    for article in json.loads(fetch_spacescoop(RAW).read_text()):
        candidates += [(s, "spacescoop_quc", article["url"]) for s in sentences(article["text"])]
    candidates += [(s, "ud_kiche_iu", url) for s, url in ud_monolingual()]
    seen, kept, counts = set(), [], {}
    for text, source, url in candidates:
        text = normalize_kiche(text)
        key = match_key(text)
        if key in seen or key in known or not looks_kiche(text):
            continue
        seen.add(key)
        kept.append({"id": f"{source}-{hashlib.sha1(key.encode()).hexdigest()[:12]}", "quc": text,
                     "source_name": source, "license": LICENSES[source], "url": url, "origin": "web"})
        counts[source] = counts.get(source, 0) + 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
    return {"dataset": version, "candidates": len(candidates), "kept": len(kept), "by_source": counts}


if __name__ == "__main__":
    print(collect(REPO / "data" / "processed"))
