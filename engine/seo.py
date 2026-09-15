"""Wekelijkse SEO-lus op Search Console-data (read-only).

1. Pagina's met vertoningen maar een CTR ver onder wat bij hun positie hoort, of die net buiten de top 10
   staan: nieuwe title-tag + meta description rond de zoektermen waarop ze echt vertoond worden,
   plus een FAQ-vraag voor de belangrijkste zoekterm als het artikel die al beantwoordt.
   Kop (H1) en URL blijven gelijk; max 1 wijziging per pagina per 21 dagen.
2. Zoektermen met vertoningen waarvoor we geen passend artikel hebben: vooraan in de uitleg-wachtrij.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

from . import gate
from .config import ARTICLES, CONTENT, SEEDS
from .fetch import jaccard, tokens
from .llm import ask_json

LOG = CONTENT / "seo_log.json"
GSC_SITE = "sc-domain:chatgpthelp.nl"
# verwachte CTR per (afgeronde) positie; ver daaronder = titel/meta trekt niet
EXPECTED = {1: .28, 2: .15, 3: .10, 4: .07, 5: .05}


def enabled() -> bool:
    return all(os.getenv(k) for k in ("GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN"))


def _token() -> str:
    data = urllib.parse.urlencode({"client_id": os.getenv("GSC_CLIENT_ID"), "client_secret": os.getenv("GSC_CLIENT_SECRET"),
                                   "refresh_token": os.getenv("GSC_REFRESH_TOKEN"), "grant_type": "refresh_token"}).encode()
    return json.loads(urllib.request.urlopen("https://oauth2.googleapis.com/token", data, timeout=30).read())["access_token"]


def fetch_rows(days: int = 28) -> list[dict]:
    end = datetime.now().date() - timedelta(days=3)  # GSC-data loopt 2-3 dagen achter
    body = {"startDate": str(end - timedelta(days=days)), "endDate": str(end), "dimensions": ["page", "query"],
            "rowLimit": 5000, "dataState": "all"}
    site = urllib.parse.quote(GSC_SITE, safe="")
    req = urllib.request.Request(f"https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query",
                                 json.dumps(body).encode(), {"Authorization": "Bearer " + _token(), "Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return [{"page": r["keys"][0], "query": r["keys"][1], "clicks": r["clicks"], "imp": r["impressions"], "pos": r["position"]}
            for r in out.get("rows", [])]


def expected_ctr(pos: float) -> float:
    p = round(pos)
    return EXPECTED.get(p, .03 if p <= 10 else .01 if p <= 20 else .003)


def _pages(rows: list[dict]) -> dict:
    pages = defaultdict(lambda: {"imp": 0, "clicks": 0, "posw": 0.0, "queries": []})
    for r in rows:
        pg = pages[urllib.parse.urlparse(r["page"]).path]
        pg["imp"] += r["imp"]
        pg["clicks"] += r["clicks"]
        pg["posw"] += r["pos"] * r["imp"]
        pg["queries"].append(r)
    for pg in pages.values():
        pg["pos"] = pg["posw"] / max(pg["imp"], 1)
        pg["ctr"] = pg["clicks"] / max(pg["imp"], 1)
        pg["queries"].sort(key=lambda q: -q["imp"])
    return pages


REWRITE = """Je bent SEO-redacteur van een Nederlandse AI-nieuwssite. Je herschrijft alleen de title-tag en meta
description zodat meer zoekers doorklikken. Eerlijk: beloof niets wat het artikel niet waarmaakt, geen clickbait,
geen cijfers die niet in het artikel staan, geen gedachtestreepjes. Antwoord met één JSON-object."""


def rewrite(art: dict, pg: dict) -> dict:
    qs = "\n".join(f'- "{q["query"]}": {q["imp"]} vertoningen, {q["clicks"]} klikken, positie {q["pos"]:.1f}' for q in pg["queries"][:10])
    faq = "\n".join(f"- {f.get('q')}" for f in art.get("faq", []))
    user = f"""Artikel-kop (H1, blijft zo): {art['title']}
Huidige title-tag: {art.get('seo_title') or art['title']}
Huidige meta: {art['meta']}
Bestaande FAQ-vragen:
{faq or '-'}
Tekst: {gate.article_text(art)[:3000]}

Search Console, laatste 28 dagen (gem. positie {pg['pos']:.1f}, CTR {pg['ctr']:.1%}):
{qs}

Geef:
{{"keyword": "belangrijkste zoekterm uit de lijst die bij dit artikel past",
 "seo_title": "40-58 tekens, die zoekterm vooraan of zo letterlijk mogelijk erin, concreet",
 "meta": "130-155 tekens, bevat de zoekterm, zegt wat de lezer hier leert of krijgt",
 "faq": {{"q": "de zoekterm als natuurlijke vraag", "a": "antwoord in 1-3 zinnen, alleen met info uit de tekst"}} (of null als de tekst dat niet beantwoordt of er al een vergelijkbare FAQ is),
 "reden": "1 zin"}}"""
    return ask_json(REWRITE, user, temperature=0.3, max_tokens=600)


def _load_log() -> dict:
    return json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"changes": [], "seeded": []}


def _improve_pages(arts, pages, log, now, max_pages) -> list[str]:
    recent = {c["path"] for c in log["changes"] if now - datetime.fromisoformat(c["at"]) < timedelta(days=21)}
    by_path = {a["path"]: a for a in arts}
    cands = []
    for path, pg in pages.items():
        art = by_path.get(path)
        if not art or path in recent or pg["imp"] < 30 or pg["pos"] > 20:
            continue
        low_ctr = pg["ctr"] < expected_ctr(pg["pos"]) * 0.7
        striking = 8 <= pg["pos"] <= 20 and pg["imp"] >= 50  # net buiten/onderaan pagina 1
        if low_ctr or striking:
            cands.append(((expected_ctr(pg["pos"]) - pg["ctr"]) * pg["imp"], path, pg, art))
    changed = []
    for _, path, pg, art in sorted(cands, key=lambda c: -c[0])[:max_pages]:
        try:
            out = rewrite(art, pg)
        except Exception as e:  # noqa: BLE001
            print(f"  seo-fout {path}: {e}")
            continue
        body = f"{gate.article_text(art)} {art['title']} {art['meta']}"
        known = gate.numbers_in(body)
        new = dict(art, seo_title=out.get("seo_title") or art.get("seo_title"), keyword=out.get("keyword") or art.get("keyword"))
        meta = (out.get("meta") or "").strip()
        if 110 <= len(meta) <= 158 and not (gate.numbers_in(meta) - known) and not gate.foreign_script(meta):
            new["meta"] = meta
        gate.fix_seo(new)
        gate.fix_meta(new, 155)
        if gate.foreign_script(new["seo_title"]) or (gate.numbers_in(new["seo_title"]) - known):
            continue
        f = out.get("faq")
        if (isinstance(f, dict) and f.get("q") and f.get("a") and not (gate.numbers_in(f["a"]) - known)
                and not gate.foreign_script(f["q"] + f["a"]) and len(new.get("faq", [])) < 6):
            new["faq"] = new.get("faq", []) + [{"q": f["q"].strip(), "a": f["a"].strip()}]
        if (new.get("seo_title"), new["meta"], len(new.get("faq", []))) == (art.get("seo_title"), art["meta"], len(art.get("faq", []))):
            continue
        new["seo_updated"] = now.strftime("%Y-%m-%d")
        (ARTICLES / f"{art['slug']}.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
        log["changes"].append({
            "at": now.isoformat(timespec="minutes"), "path": path, "imp": pg["imp"], "clicks": pg["clicks"], "pos": round(pg["pos"], 1),
            "old_title": art.get("seo_title") or art["title"], "new_title": new["seo_title"], "old_meta": art["meta"],
            "new_meta": new["meta"], "faq_added": len(new.get("faq", [])) > len(art.get("faq", [])), "reden": out.get("reden", "")})
        changed.append(f"{new['seo_title']} ({pg['imp']} vert., pos {pg['pos']:.0f})")
    return changed


SKIP_QUERY = re.compile(r"\b(inloggen|login|download|app|nl\.chatgpt|chat\.openai|sex|porn)\b", re.I)


def _seed_gaps(arts, rows, log, max_seeds) -> list[str]:
    seeds = json.loads(SEEDS.read_text(encoding="utf-8"))
    qagg = defaultdict(lambda: {"imp": 0, "posw": 0.0, "pages": set()})
    for r in rows:
        q = qagg[r["query"]]
        q["imp"] += r["imp"]
        q["posw"] += r["pos"] * r["imp"]
        q["pages"].add(urllib.parse.urlparse(r["page"]).path)
    known = [tokens(f"{a['title']} {a.get('keyword', '')}") for a in arts] + [tokens(s["topic"]) for s in seeds]
    added = []
    for query, q in sorted(qagg.items(), key=lambda kv: -kv[1]["imp"]):
        if len(added) >= max_seeds:
            break
        if q["imp"] < 20 or query in log["seeded"] or len(query.split()) < 2 or SKIP_QUERY.search(query):
            continue
        pos = q["posw"] / q["imp"]
        only_hubs = all(p.count("/") <= 2 for p in q["pages"])  # alleen voorpagina/rubriek wordt vertoond
        # een artikel dat al in de top 20 staat optimaliseren we (stap 1) i.p.v. een dubbel artikel te schrijven
        if (pos <= 20 and not only_hubs) or any(jaccard(tokens(query), k) >= 0.5 for k in known):
            continue
        topic = re.sub(r"\bchatgpt\b", "ChatGPT", query[0].upper() + query[1:], flags=re.I)
        seeds.insert(0, {"topic": topic, "intent": "zoekterm uit Search Console: beantwoord precies deze zoekvraag",
                         "audience": "Nederlandse zoekers", "from_gsc": True})
        log["seeded"].append(query)
        added.append(f"{query} ({q['imp']} vert.)")
    if added:
        SEEDS.write_text(json.dumps(seeds, ensure_ascii=False, indent=1), encoding="utf-8")
    return added


def run(arts: list[dict], max_pages: int = 5, max_seeds: int = 3) -> str:
    if not enabled():
        return ""
    rows = fetch_rows()
    if not rows:
        return "seo: nog geen Search Console-data"
    log = _load_log()
    now = datetime.now()
    pages = _pages(rows)
    changed = _improve_pages(arts, pages, log, now, max_pages)
    added = _seed_gaps(arts, rows, log, max_seeds)
    log["changes"] = log["changes"][-300:]
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    imp = sum(p["imp"] for p in pages.values())
    clicks = sum(p["clicks"] for p in pages.values())
    line = f"seo: {imp} vertoningen, {clicks} klikken (28d) · {len(changed)} titels/meta bijgewerkt · {len(added)} nieuwe onderwerpen"
    if changed:
        line += "\n" + "\n".join("• " + c for c in changed)
    if added:
        line += "\n" + "\n".join("+ " + a for a in added)
    return line
