"""Kwaliteitspoort: een artikel dat hier faalt wordt NIET gepubliceerd (vol-automatisch is niet
onvoorwaardelijk). Regels: lengte, titel/meta, Nederlands, geen hype-clichés, geen kopieerrun uit
bronnen, geen verzonnen getallen, dedup tegen eerdere titels."""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from . import config
from . import seo_stijl as St
from .config import ENGLISH_MARKERS, FORBIDDEN_PHRASES, LIMITS
from .fetch import jaccard, tokens

STIJL_LOG = Path(__file__).resolve().parents[1] / "content" / "stijl_log.json"
STIJL_LOG_MAX = 500


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
    return {n.rstrip(".,") for n in re.findall(r"\d[\d.,]*", text)}


def fix_meta(art: dict, limit: int = 155) -> None:
    """Te lange meta netjes inkorten op een woordgrens (geen poortfout voor iets cosmetisch)."""
    m = (art.get("meta") or "").strip()
    if len(m) <= limit:
        return
    cut = m[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:- ")
    art["meta"] = cut + "…"


def fix_seo(art: dict, limit: int = 60) -> None:
    """seo_title (title-tag) netjes houden: fallback op de kop, inkorten op woordgrens, geen sitenaam."""
    t = (art.get("seo_title") or art.get("title") or "").strip()
    t = re.sub(r"\s*[|·\-–—]\s*ChatGPT ?Help(\.nl)?\s*$", "", t, flags=re.I)
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0].rstrip(",;:-–— ")
        while re.search(r"\s(en|of|van|de|het|een|voor|met|in|op|te|om|:)$", t, re.I):
            t = t.rsplit(" ", 1)[0].rstrip(",;:-–— ")
    art["seo_title"] = t
    art["keyword"] = (art.get("keyword") or "").strip().lower()


FOREIGN = re.compile(r"[Ѐ-ӿ֐-ۿ฀-๿぀-ヿ㐀-鿿가-힯]")


def foreign_script(text: str) -> bool:
    """True bij Chinese/Japanse/Koreaanse/Cyrillische e.d. tekens (DeepSeek-glitch)."""
    return bool(FOREIGN.search(text or ""))


def shared_ngram(a: str, b: str, n: int = 5) -> str | None:
    wa = re.findall(r"\w+", a.lower())
    wb = " ".join(re.findall(r"\w+", b.lower()))
    for i in range(max(0, len(wa) - n + 1)):
        g = " ".join(wa[i:i + n])
        if g in wb:
            return g
    return None


ANTITHESIS = re.compile(r"\b(dat|dit|het) is geen [^.,;:!?]{1,40}[,:;] (dat|dit|het) is\b", re.I)


def antithesis(text: str) -> str | None:
    m = ANTITHESIS.search(text or "")
    return m.group(0) if m else None


def check_article(art: dict, sources_text: str, previous_titles: list[str], kind: str = "news") -> list[str]:
    errs = []
    fix_meta(art, LIMITS["meta_max"] - 3)
    fix_seo(art)
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
    if foreign_script(body + title + meta):
        errs.append("vreemd schrift (glitch)")
    if kind == "column" and antithesis(body):
        errs.append(f"AI-tic: {antithesis(body)}")
    low = body.lower()
    for ph in FORBIDDEN_PHRASES:
        if ph in low:
            errs.append(f"verboden frase: {ph}")
    en = sum(low.count(m) for m in ENGLISH_MARKERS)
    if en > max(6, wc * 0.012):
        errs.append(f"engelse lekkage ({en})")
    # columns citeren Maxims eigen praktijklessen; kopieerrun alleen tegen externe bronnen toetsen
    if sources_text and kind != "column" and copied_run(body, sources_text, LIMITS["max_copied_run"]):
        errs.append("kopieerrun uit bron")
    if sources_text:
        src_nums = numbers_in(sources_text)
        bad = [n for n in numbers_in(body) if n not in src_nums and len(n.strip(".,")) >= 3 and not re.fullmatch(r"20\d\d", n)]
        # jaartallen en kleine getallen mogen (die komen uit algemene kennis); grote getallen niet
        if len(bad) > (0 if kind == "column" else 2):
            errs.append(f"onbekende getallen: {bad[:4]}")
    tt = tokens(title)
    for pt in previous_titles:
        if jaccard(tt, tokens(pt)) >= LIMITS["dedupe_jaccard"]:
            errs.append(f"dubbel met eerder: {pt[:50]}")
            break
    if not art.get("category"):
        errs.append("geen categorie")
    rood = stijl_check(art)
    andere = len(errs)
    if config.STIJLPOORT == "blokkeren":
        errs += [f"stijlpoort {c}: {m}" for c, m in rood]
    _log_stijl(art, kind, rood, andere)
    return errs


def stijl_check(art: dict) -> list[tuple[str, str]]:
    """De stijlpoort van de SEO-motor (engine/seo_stijl.py, een kopie van adsvantage-fleet/scripts/seo_stijl.py die
    een test daar gelijk houdt): de algemene regels S1 tot S14, zoals geen gedachtestreepjes, geen holle woorden, geen
    'niet X maar Y' en afwisselende zinnen. De eisen voor eigen blogs (een ik- of wij-zin, geen dubbele punt in de
    titel) gelden niet voor nieuws. Geeft de rode bevindingen als (code, melding)."""
    alineas = [art.get("intro", "")] + [s.get("body", "") for s in art.get("sections") or []] \
        + [art.get("nl_angle", "")] + [f.get("a", "") for f in art.get("faq") or []]
    koppen = [s.get("heading", "") for s in art.get("sections") or []]
    r = St.toets([a for a in alineas if isinstance(a, str) and a.strip()], "sectie", title=art.get("title", ""),
                 h1=art.get("title", ""), koppen=koppen)
    return [(c, m) for e, c, m in r["bevindingen"] if e == St.ROOD]


def _log_stijl(art: dict, kind: str, rood: list, andere_fouten: int) -> None:
    """Meting: welke stijlregels breekt dit artikel. Een mislukte meting houdt niets tegen."""
    try:
        try:
            log = json.loads(STIJL_LOG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log = []
        log.append({"at": datetime.datetime.now().isoformat(timespec="seconds"), "slug": art.get("slug") or "",
                    "title": (art.get("title") or "")[:90], "kind": kind, "rood": sorted({c for c, _m in rood}),
                    "andere_fouten": andere_fouten, "stand": config.STIJLPOORT})
        STIJL_LOG.write_text(json.dumps(log[-STIJL_LOG_MAX:], ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
