"""Redactiestappen: elk type content = één functie die een bestand in content/ schrijft
of None teruggeeft. Poort faalt = niets wegschrijven. Geen netwerk behalve de LLM."""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta

from . import gate, writer
from .config import ARTICLES, CATEGORIES, LIMITS, MEMES, PROMPTS, SEEDS, SITE


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:70].rstrip("-")


def load_articles() -> list[dict]:
    arts = []
    for p in sorted(ARTICLES.glob("*.json")):
        try:
            arts.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            print(f"  kapot artikelbestand {p.name}: {e}")
    arts.sort(key=lambda a: a["published"], reverse=True)
    return arts


def load_memes() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(MEMES.glob("*.json"), reverse=True)]


def load_prompts() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(PROMPTS.glob("*.json"), reverse=True)]


def _save(dirpath, name: str, data: dict) -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _finalize(art: dict, kind: str, sources: list[dict], stamp: datetime) -> dict:
    cat = art.get("category") if art.get("category") in CATEGORIES else ("uitleg" if kind == "evergreen" else "nieuws")
    slug = slugify(art["title"])
    art.update({
        "slug": slug,
        "category": cat,
        "kind": kind,
        "date": stamp.strftime("%Y-%m-%d"),
        "published": stamp.isoformat(timespec="minutes"),
        "sources": [{"name": s["source"], "title": s["title"], "url": s["url"]} for s in sources],
        "path": f"/{cat}/{slug}/",
        "og": f"/img/og/{slug}.png",
    })
    return art


def news_batch(stories: list[dict], ledger: dict, existing: list[dict], stamp: datetime) -> list[dict]:
    """Max ARTICLES_PER_RUN artikelen. Gevoelige verhalen worden overgeslagen (er is geen
    menselijke eindredactie), poort-falers ook. Alles wat bekeken is gaat in het grootboek."""
    today = stamp.strftime("%d-%m-%Y")
    prev_titles = [a["title"] for a in existing[:200]] + ledger.get("published_titles", [])
    done, tried = [], 0
    for st in stories:
        if len(done) >= LIMITS["articles_per_run"] or tried >= LIMITS["articles_per_run"] * 3:
            break
        if st["risk"] == "high":
            print(f"  overslaan (gevoelig): {st['title'][:70]}")
            for it in st["items"]:
                ledger["seen"][it["id"]] = {"at": stamp.isoformat(), "why": "high-risk"}
            continue
        tried += 1
        print(f"  schrijven: {st['title'][:80]}  [{', '.join(st['sources'])}] score={st['score']}")
        try:
            art = writer.write_news(st, today)
        except Exception as e:  # noqa: BLE001
            print(f"    LLM-fout: {e}")
            continue
        src_text = " ".join(f"{i['title']} {i['summary']}" for i in st["items"])
        errs = gate.check_article(art, src_text, prev_titles, "news")
        for it in st["items"]:
            ledger["seen"][it["id"]] = {"at": stamp.isoformat(), "why": "ok" if not errs else "poort"}
        if errs:
            print(f"    POORT: {errs}")
            continue
        art = _finalize(art, "news", st["items"], stamp)
        if (ARTICLES / f"{art['slug']}.json").exists():
            print("    bestaat al (slug)")
            continue
        _save(ARTICLES, art["slug"], art)
        ledger.setdefault("published_titles", []).append(art["title"])
        prev_titles.append(art["title"])
        done.append(art)
        stamp = stamp + timedelta(minutes=1)
    return done


def evergreen(existing: list[dict], stamp: datetime) -> dict | None:
    seeds = json.loads(SEEDS.read_text(encoding="utf-8"))
    used = {a.get("seed") for a in existing if a.get("kind") == "evergreen"}
    todo = [s for s in seeds if s["topic"] not in used]
    if not todo:
        print("  geen evergreen-seeds meer")
        return None
    seed = todo[0]
    print(f"  uitleg schrijven: {seed['topic']}")
    art = writer.write_evergreen(seed, stamp.strftime("%d-%m-%Y"))
    errs = gate.check_article(art, "", [a["title"] for a in existing], "evergreen")
    if errs:
        print(f"    POORT: {errs}")
        return None
    art = _finalize(art, "evergreen", [], stamp)
    art["seed"] = seed["topic"]
    _save(ARTICLES, art["slug"], art)
    return art


def weekoverzicht(existing: list[dict], stamp: datetime) -> dict | None:
    week_ago = (stamp - timedelta(days=7)).strftime("%Y-%m-%d")
    week = [a for a in existing if a["date"] >= week_ago and a.get("kind") == "news"]
    if len(week) < 4:
        print("  te weinig artikelen voor een weekoverzicht")
        return None
    label = f"AI-week {stamp.isocalendar()[1]}"
    art = writer.write_week(week[:14], label, stamp.strftime("%d-%m-%Y"))
    src_text = " ".join(f"{a['title']} {a['meta']} {gate.article_text(a)}" for a in week)
    errs = gate.check_article(art, src_text, [], "news")
    if errs:
        print(f"    POORT: {errs}")
        return None
    if label.lower() not in art["title"].lower():
        art["title"] = f"{label}: {art['title']}"[:75]
    art = _finalize(art, "week", [], stamp)
    art["sources"] = [{"name": SITE["name"], "title": a["title"], "url": SITE["url"] + a["path"]} for a in week[:14]]
    _save(ARTICLES, art["slug"], art)
    return art


def meme(existing: list[dict], stamp: datetime) -> dict | None:
    date = stamp.strftime("%Y-%m-%d")
    if (MEMES / f"{date}.json").exists():
        return None
    prev = [m.get("bottom", "") for m in load_memes()]
    m = writer.write_meme([a["title"] for a in existing[:8]], stamp.strftime("%d-%m-%Y"), prev)
    for a, b in (("top", "bottom"), ("top_en", "bottom_en")):
        if not (m.get(a) and m.get(b)) or len(m[a]) > 90 or len(m[b]) > 100:
            print(f"  meme afgekeurd ({a}): {m}")
            return None
    m.update({"date": date, "img": f"/img/memes/{date}.png", "img_en": f"/img/memes/{date}-en.png"})
    _save(MEMES, date, m)
    return m


def prompt_of_day(stamp: datetime) -> dict | None:
    date = stamp.strftime("%Y-%m-%d")
    if (PROMPTS / f"{date}.json").exists():
        return None
    prev = [p.get("title", "") for p in load_prompts()]
    p = writer.write_prompt_of_day(stamp.strftime("%d-%m-%Y"), prev)
    if not (p.get("title") and p.get("prompt")) or gate.word_count(p["prompt"]) < 30:
        print(f"  prompt afgekeurd: {p}")
        return None
    p.update({"date": date, "slug": slugify(p["title"]), "path": f"/prompts/{date}-{slugify(p['title'])}/"})
    _save(PROMPTS, date, p)
    return p


# ---------------------------------------------------------------------- Maxim (persona) ----
def _persona_article(art: dict, kind: str, stamp: datetime, source_text: str, existing: list[dict], extra: dict) -> dict | None:
    """Poort + opslaan voor columns/reviews. Cijfers moeten uit lessen of nieuws komen."""
    from . import persona

    art["category"] = "mening"
    titles = [a["title"] for a in existing[:200]]
    errs = gate.check_article(art, source_text, titles, "column")
    if errs:
        print(f"    POORT ({kind}): {errs}")
        return None
    # feitencheck: persoonlijke claims moeten uit profiel of lessen komen
    p = persona.load()
    allowed = persona.brief(p) + "\n\nPRAKTIJKLESSEN EN NIEUWS:\n" + source_text
    for rnd in range(2):
        fake = writer.verify_persona(gate.article_text(art), allowed)
        if not fake:
            break
        print(f"    feitencheck ronde {rnd + 1}: {len(fake)} verzonnen claim(s): {[f[:60] for f in fake[:3]]}")
        if rnd == 1:
            print(f"    AFGEKEURD ({kind}): blijft verzinnen")
            return None
        art = writer.revise_persona(art, fake)
        art["category"] = "mening"
        errs = gate.check_article(art, source_text, titles, "column")
        if errs:
            print(f"    POORT na herschrijven ({kind}): {errs}")
            return None
    art = _finalize(art, kind, [], stamp)
    art.update(extra)
    art["author"] = "Maxim"
    if (ARTICLES / f"{art['slug']}.json").exists():
        print("    bestaat al (slug)")
        return None
    _save(ARTICLES, art["slug"], art)
    return art


def column(existing: list[dict], stamp: datetime) -> dict | None:
    from . import persona

    p = persona.load()
    recent = [a for a in existing if a.get("kind") == "news"][:8]
    if len(recent) < 2:
        print("  te weinig nieuws voor een column")
        return None
    news_block = "\n\n".join(f"- {a['title']} ({a['date']}): {a['meta']}\n  {a.get('intro', '')}" for a in recent)
    u = persona.used()
    ls = persona.relevant_lessons(news_block, 5, exclude=u["lessen"][-10:])
    print(f"  column schrijven (lessen: {[l['id'] for l in ls]})")
    art = writer.write_column(persona.brief(p), persona.lessons_block(ls), news_block, stamp.strftime("%d-%m-%Y"))
    src = news_block + " " + " ".join(l["text"] for l in ls)
    out = _persona_article(art, "column", stamp, src, existing,
                           {"sources": [{"name": SITE["name"], "title": a["title"], "url": SITE["url"] + a["path"]} for a in recent[:5]]})
    if out:
        u["lessen"] += [i for i in art.get("lessons_used", []) if isinstance(i, str)]
        u["columns"].append(out["slug"])
        persona.save_used(u)
    return out


def practice(existing: list[dict], stamp: datetime) -> dict | None:
    from . import persona

    p = persona.load()
    u = persona.used()
    todo = [l for l in persona.lessons() if l["id"] not in u["lessen"]]
    if not todo:
        u["lessen"] = []  # alle lessen gebruikt: opnieuw beginnen (andere invalshoek)
        todo = persona.lessons()
    if not todo:
        print("  geen praktijklessen")
        return None
    lesson = todo[0]
    extra = [l for l in persona.relevant_lessons(lesson["text"], 3, exclude=[lesson["id"]])]
    print(f"  praktijkcolumn schrijven: {lesson['id']}")
    art = writer.write_practice(persona.brief(p), lesson, persona.lessons_block(extra), stamp.strftime("%d-%m-%Y"))
    src = lesson["text"] + " " + " ".join(l["text"] for l in extra)
    out = _persona_article(art, "practice", stamp, src, existing, {"lesson": lesson["id"]})
    u["lessen"].append(lesson["id"])  # ook bij poort-falen doorschuiven, anders blijft hij hangen
    if out:
        u["columns"].append(out["slug"])
    persona.save_used(u)
    return out


def review(existing: list[dict], stamp: datetime, tries: int = 2) -> dict | None:
    """Review van een tool die Maxim echt gebruikt; bij afkeur direct de volgende tool proberen."""
    from . import persona

    p = persona.load()
    for _ in range(tries):
        u = persona.used()
        tools = [t for t in p["tools_used"] if t["tool"] not in u["tools"]]
        if not tools:
            u["tools"] = []
            tools = p["tools_used"]
        tool = tools[0]
        ls = persona.relevant_lessons(tool["tool"] + " " + tool["use"] + " " + tool["opinion"], 3)
        print(f"  review schrijven: {tool['tool']}")
        art = writer.write_review(persona.brief(p), tool, persona.lessons_block(ls), stamp.strftime("%d-%m-%Y"))
        src = " ".join([tool["tool"], tool["use"], tool["opinion"], tool["status"]] + [l["text"] for l in ls])
        out = _persona_article(art, "review", stamp, src, existing, {"tool": tool["tool"]})
        u["tools"].append(tool["tool"])
        persona.save_used(u)
        if out:
            return out
    return None


def add_takes(arts: list[dict]) -> int:
    """Korte 'Maxims take' onder nieuwe nieuwsartikelen. Poort: max 3 zinnen, geen vreemd schrift,
    geen onbekende cijfers, geen vraag als slot, en geen stopzin die al in een recente take stond."""
    from . import persona

    if not arts:
        return 0
    pdata = persona.load()
    b = persona.brief(pdata)
    beliefs = pdata["beliefs"]
    recent = [a["take"] for a in load_articles()[:40] if a.get("take")]
    n = 0
    for a in arts:
        for attempt in range(3):
            try:
                ls = persona.relevant_lessons(a["title"] + " " + a["meta"] + " " + a.get("intro", ""), 2, min_score=6)
                avoid = "\n".join("- " + r for r in recent[-12:])
                extra = ("\n\nVERMIJD formuleringen en stopzinnen uit deze eerdere takes:\n" + avoid) if avoid else ""
                focus = beliefs[(sum(map(ord, a["slug"])) + attempt) % len(beliefs)]
                take = writer.write_take(b, a, persona.lessons_block(ls) + extra, focus)
            except Exception as e:  # noqa: BLE001
                print(f"    take-fout: {e}")
                take = ""
                break
            allowed = gate.numbers_in(" ".join(l["text"] for l in ls) + " " + gate.article_text(a) + " " + a["title"])
            bad = [x for x in gate.numbers_in(take) if x not in allowed and len(x) >= 2]
            sentences = len(re.findall(r"[.!?](\s|$)", take))
            dup = next((g for r in recent for g in [gate.shared_ngram(take, r)] if g), None)
            why = ("leeg" if not take else "vreemd schrift" if gate.foreign_script(take) else f"cijfers {bad}" if bad
                   else f"{sentences} zinnen" if sentences > 3 or len(take) > 480 else "vraag als slot" if take.rstrip().endswith("?") else f"AI-tic '{gate.antithesis(take)}'" if gate.antithesis(take)
                   else f"herhaalt '{dup}'" if dup else "")
            if not why:
                break
            print(f"    take afgekeurd ({why}), poging {attempt + 1}")
            take = ""
        if not take:
            continue
        a["take"] = take
        recent.append(take)
        _save(ARTICLES, a["slug"], a)
        n += 1
    return n
