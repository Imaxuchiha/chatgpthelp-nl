"""Kwaliteitspoort: een artikel dat hier faalt wordt NIET gepubliceerd (vol-automatisch is niet
onvoorwaardelijk). Regels: lengte, titel/meta, Nederlands, geen hype-clichés, geen kopieerrun uit
bronnen, geen verzonnen getallen, dedup tegen eerdere titels."""
from __future__ import annotations

import re

from .config import ENGLISH_MARKERS, FORBIDDEN_PHRASES, LIMITS
from .fetch import jaccard, tokens


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def article_text(art: dict) -> str:
    parts = [art.get("intro", "")]
    for s in art.get("sections", []):
        parts.append(s.get("heading", ""))
        parts.append(s.get("body", ""))
    parts += art.get("takeaways", [])
    for f in art.get("faq", []):
        parts.append(f.get("q", "") + " " + f.get("a", ""))
    return "\n".join(p for p in parts if p)


def copied_run(text: str, sources_text: str, n: int) -> bool:
    """True als n aaneengesloten woorden uit een bron letterlijk in de tekst staan."""
    src_words = re.findall(r"\w+", sources_text.lower())
    grams = {" ".join(src_words[i:i + n]) for i in range(max(0, len(src_words) - n + 1))}
    words = re.findall(r"\w+", text.lower())
    for i in range(max(0, len(words) - n + 1)):
        if " ".join(words[i:i + n]) in grams:
            return True
    return False


def numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d[\d.,]*", text))


def check_article(art: dict, sources_text: str, previous_titles: list[str], kind: str = "news") -> list[str]:
    errs = []
    title = (art.get("title") or "").strip()
    meta = (art.get("meta") or "").strip()
    body = article_text(art)
    wc = word_count(body)
    if not (10 <= len(title) <= LIMITS["title_max"]):
        errs.append(f"titel {len(title)} tekens")
    if not (LIMITS["meta_min"] <= len(meta) <= LIMITS["meta_max"]):
        errs.append(f"meta {len(meta)} tekens")
    lo = LIMITS["min_words"] if kind == "news" else 500
    if wc < lo:
        errs.append(f"te kort: {wc} woorden")
    if wc > LIMITS["max_words"] + (600 if kind != "news" else 0):
        errs.append(f"te lang: {wc} woorden")
    secs = art.get("sections") or []
    if not (2 <= len(secs) <= 7):
        errs.append(f"{len(secs)} secties")
    if len(art.get("takeaways") or []) < 2:
        errs.append("te weinig kernpunten")
    low = body.lower()
    for ph in FORBIDDEN_PHRASES:
        if ph in low:
            errs.append(f"verboden frase: {ph}")
    en = sum(low.count(m) for m in ENGLISH_MARKERS)
    if en > max(6, wc * 0.012):
        errs.append(f"engelse lekkage ({en})")
    if sources_text and copied_run(body, sources_text, LIMITS["max_copied_run"]):
        errs.append("kopieerrun uit bron")
    if sources_text:
        src_nums = numbers_in(sources_text)
        bad = [n for n in numbers_in(body) if n not in src_nums and len(n.strip(".,")) >= 3 and not re.fullmatch(r"20\d\d", n)]
        # jaartallen en kleine getallen mogen (die komen uit algemene kennis); grote getallen niet
        if len(bad) > 2:
            errs.append(f"onbekende getallen: {bad[:4]}")
    tt = tokens(title)
    for pt in previous_titles:
        if jaccard(tt, tokens(pt)) >= LIMITS["dedupe_jaccard"]:
            errs.append(f"dubbel met eerder: {pt[:50]}")
            break
    if not art.get("category"):
        errs.append("geen categorie")
    return errs
