"""RSS ophalen, filteren op AI-relevantie, dedupliceren, clusteren tot 'verhalen'.

Een verhaal = 1..n bronitems over hetzelfde nieuws. Meer onafhankelijke bronnen = hogere
prioriteit. Het grootboek (ledger.json) voorkomt dat een bron-URL twee keer geld kost.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import datetime, timedelta, timezone

import feedparser

from .config import AI_TERMS, HIGH_RISK_TERMS, LEDGER, LIMITS, NOISE_TERMS, SOURCES

UA = "Mozilla/5.0 (compatible; chatgpthelp-bot/1.0; +https://chatgpthelp.nl/over/)"
STOP = set("""de het een en of van in op voor met is zijn wordt worden aan bij door om te dat die dit
naar uit als ook nog maar niet wel er over tot na the a an and of to in on for with is are be by at
from as it its this that new how why what says will has have was were you your ai""".split())


def _clean(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _sid(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def _norm_url(u: str) -> str:
    u = re.sub(r"[?#].*$", "", u or "")
    return u.rstrip("/").lower()


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ü0-9][a-zà-ü0-9\-]+", (text or "").lower()) if w not in STOP and len(w) > 2}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {"seen": {}, "published_titles": []}


def save_ledger(ledger: dict) -> None:
    # bewaar maximaal 90 dagen aan gezien-items
    cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    ledger["seen"] = {k: v for k, v in ledger["seen"].items() if v.get("at", "") >= cutoff}
    ledger["published_titles"] = ledger.get("published_titles", [])[-600:]
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")


def is_ai(text: str) -> bool:
    t = f" {text.lower()} "
    for n in NOISE_TERMS:
        t = t.replace(n, " ")
    return any(term in t for term in AI_TERMS)


def risk(text: str) -> str:
    t = f" {text.lower()} "
    hits = [h for h in HIGH_RISK_TERMS if h in t]
    return "high" if hits else "low"


def fetch_all(max_age_hours: int | None = None) -> list[dict]:
    max_age = timedelta(hours=max_age_hours or LIMITS["max_item_age_hours"])
    now = datetime.now(timezone.utc)
    items = []
    for src in SOURCES:
        try:
            feed = feedparser.parse(src["url"], agent=UA)
        except Exception as e:  # noqa: BLE001
            print(f"  bron {src['name']}: FOUT {e}")
            continue
        n = 0
        for e in feed.entries[:60]:
            link = e.get("link") or ""
            title = _clean(e.get("title", ""))
            if not link or not title:
                continue
            ts = e.get("published_parsed") or e.get("updated_parsed")
            if ts:
                published = datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc)
            else:
                published = now
            if now - published > max_age:
                continue
            summary = _clean(e.get("summary", "") or (e.get("content", [{}])[0].get("value", "") if e.get("content") else ""))
            blob = f"{title} {summary}"
            if not is_ai(blob):
                continue
            items.append({
                "id": _sid(_norm_url(link)),
                "url": link,
                "title": title,
                "summary": summary[:1500],
                "source": src["name"],
                "lang": src["lang"],
                "weight": src["weight"],
                "primary": src["primary"],
                "published": published.isoformat(),
                "age_h": round((now - published).total_seconds() / 3600, 1),
                "risk": risk(blob),
            })
            n += 1
        print(f"  bron {src['name']}: {n} relevante items")
    return items


def cluster(items: list[dict], ledger: dict) -> list[dict]:
    """Groepeer items die over hetzelfde verhaal gaan; sla al-gebruikte over."""
    seen = ledger.get("seen", {})
    fresh = [i for i in items if i["id"] not in seen]
    fresh.sort(key=lambda i: i["age_h"])
    stories: list[dict] = []
    for it in fresh:
        tk = tokens(it["title"]) | set(list(tokens(it["summary"]))[:40])
        placed = False
        for st in stories:
            if jaccard(tokens(it["title"]), st["_tk_title"]) >= 0.35 or jaccard(tk, st["_tk"]) >= 0.30:
                st["items"].append(it)
                st["_tk"] |= tk
                placed = True
                break
        if not placed:
            stories.append({"items": [it], "_tk": set(tk), "_tk_title": tokens(it["title"])})
    for st in stories:
        its = st["items"]
        sources = {i["source"] for i in its}
        score = sum(i["weight"] for i in its) * (1 + 0.35 * (len(sources) - 1))
        newest = min(i["age_h"] for i in its)
        score *= max(0.35, 1 - newest / 96)
        if any(i["lang"] == "nl" for i in its):
            score *= 1.15
        st["score"] = round(score, 3)
        st["risk"] = "high" if any(i["risk"] == "high" for i in its) else "low"
        st["title"] = its[0]["title"]
        st["sources"] = sorted(sources)
        del st["_tk"], st["_tk_title"]
    stories.sort(key=lambda s: -s["score"])
    return stories
