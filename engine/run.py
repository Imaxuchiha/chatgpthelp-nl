"""CLI van de redactie.

  python -m engine.run run      # editie schrijven (+ de dag- en weekstappen die nog openstaan, zie STEPS)
  python -m engine.run dry      # alleen bronnen scannen en tonen
  python -m engine.run build    # site renderen naar dist/
  python -m engine.run status   # overzicht content/ + planner
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from . import editorial, fetch, notify, seo
from .config import CONTENT, DIST, MEMES, PROMPTS, SITE

# Planner. Een stap draait in de EERSTE run van de dag die hem nog niet gedaan heeft, ongeacht het uur.
# Vroeger was het `hour < 11`, maar GitHub start geplande runs 3-5 uur te laat: de 07:20-run draaide rond
# 12:00, waardoor meme, prompt, Bluesky, uitleg, column, review en de SEO-lus van 16 t/m 29-09 geen enkele
# keer draaiden en niemand het zag. Nu telt de status in content/schedule.json, niet de klok.
# (naam, weekdagen of None = dagelijks, inhalen als hij >= 8 dagen niet gelukt is)
STEPS = [
    ("seo", {0}, True),             # maandag: Search Console-lus (titels/meta + onderwerpen voor de uitleg)
    ("meme", None, False),
    ("prompt", None, False),
    ("column", {1}, True),          # dinsdag: Maxims mening over het nieuws
    ("uitleg", {2, 4}, True),       # woensdag + vrijdag: evergreen uitleg, de SEO-motor
    ("praktijk", {3}, True),        # donderdag: uit de praktijk
    ("review", {5}, True),          # zaterdag
    ("weekoverzicht", {6}, False),  # zondag; midweeks inhalen heeft geen zin
]
SCHEDULE = CONTENT / "schedule.json"
MAX_TRIES = 3     # pogingen per stap per dag; daarna wachten tot de volgende beurt
CATCHUP_DAYS = 8  # een weekstap die zo lang niet gelukt is, haalt de eerstvolgende run in (max 1 per run)
# waakhond: zo veel dagen mag de laatste geslaagde keer oud zijn; daarna gaat er een waarschuwing mee naar Slack
MAX_AGE = {"nieuws": 1, "meme": 1, "prompt": 1, "bluesky": 1, "seo": 8, "column": 8, "uitleg": 5,
           "praktijk": 8, "review": 8, "weekoverzicht": 8}
KIND_OF = {"column": "column", "uitleg": "evergreen", "praktijk": "practice", "review": "review", "weekoverzicht": "week"}


def scan():
    ledger = fetch.load_ledger()
    print("bronnen scannen…")
    items = fetch.fetch_all()
    stories = fetch.cluster(items, ledger)
    print(f"{len(items)} items → {len(stories)} nieuwe verhalen")
    for st in stories[:12]:
        print(f"  {st['score']:>6}  {st['risk']:<4} {st['title'][:70]}  [{', '.join(st['sources'])}]")
    return ledger, stories


def cmd_dry() -> int:
    scan()
    return 0


def cmd_run() -> int:
    from .llm import USAGE

    stamp = datetime.now()
    print(f"== redactie {stamp:%Y-%m-%d %H:%M} ==")
    existing = editorial.load_articles()
    ledger, stories = scan()
    new = editorial.news_batch(stories, ledger, existing, stamp)
    takes = editorial.add_takes(new) if new else 0
    existing = editorial.load_articles()
    state = load_schedule(existing)
    today = stamp.date()
    if new:
        _mark(state, "nieuws", True, today)
    fns = {
        "seo": lambda: seo.run(existing),
        "meme": lambda: editorial.meme(existing, stamp) or (MEMES / f"{today}.json").exists(),
        "prompt": lambda: editorial.prompt_of_day(stamp) or (PROMPTS / f"{today}.json").exists(),
        "column": lambda: editorial.column(existing, stamp),
        "uitleg": lambda: editorial.evergreen(existing, stamp),
        "praktijk": lambda: editorial.practice(existing, stamp),
        "review": lambda: editorial.review(existing, stamp),
        "weekoverzicht": lambda: editorial.weekoverzicht(existing, stamp),
    }
    extra = {}
    for label in due_steps(state, stamp):
        try:
            extra[label] = fns[label]()
        except Exception as e:  # noqa: BLE001
            print(f"  {label}-fout: {e}")
            extra[label] = None
        _mark(state, label, bool(extra[label]), today)
    fetch.save_ledger(ledger)
    bsky = post_memes()
    m = editorial.load_memes()
    if m and m[0]["date"] == str(today) and m[0].get("bsky_nl") and m[0].get("bsky_en"):
        _mark(state, "bluesky", True, today)
    for label in ("column", "praktijk", "review"):
        art = extra.get(label)
        if art:
            bsky += post_persona(art)
    save_schedule(state)
    cost = (USAGE["prompt"] * 0.30 + USAGE["completion"] * 1.20) / 1e6
    done = [k for k, v in extra.items() if v and k != "seo"]
    failed = [k for k, v in extra.items() if not v]
    parts = [f"{len(new)} nieuws"] + ([f"{takes} takes"] if takes else []) + done + ([f"bluesky {bsky}"] if bsky else [])
    line = (f"chatgpthelp.nl {stamp:%d-%m %H:%M}: {', '.join(parts)} · {len(stories)} verhalen gezien · "
            f"{USAGE['calls']} LLM-calls ≈ ${cost:.3f}")
    if failed:
        line += f"\nniet gelukt (volgende run opnieuw, max {MAX_TRIES}x per dag): {', '.join(failed)}"
    if new:
        line += "\n" + "\n".join(f"• {a['title']} — {SITE['url']}{a['path']}" for a in new)
    if isinstance(extra.get("seo"), str):
        line += "\n" + extra["seo"]
    alarms = watchdog(state, today)
    if alarms:
        line += "\n:warning: waakhond: " + "; ".join(alarms)
    print(line)
    notify.slack(line)
    return 0


# ---------------------------------------------------------------------------- planner ----
def _last(items, kind=None) -> str | None:
    ds = [x["date"] for x in items if kind is None or x.get("kind") == kind]
    return max(ds) if ds else None


def load_schedule(arts: list[dict]) -> dict:
    """Status per stap: {"ok": laatste geslaagde dag, "try": dag van de laatste poging, "n": pogingen die dag}.
    Bestaat het bestand nog niet, dan wordt 'ok' afgeleid uit wat er echt in content/ staat."""
    if SCHEDULE.exists():
        return json.loads(SCHEDULE.read_text(encoding="utf-8"))
    memes = editorial.load_memes()
    seo_log = json.loads(seo.LOG.read_text(encoding="utf-8")) if seo.LOG.exists() else {"changes": []}
    ok = {"nieuws": _last(arts, "news"), "meme": _last(memes), "prompt": _last(editorial.load_prompts()),
          "bluesky": _last([m for m in memes if m.get("bsky_nl")]),
          "seo": max((c["at"][:10] for c in seo_log["changes"]), default=None)}
    ok.update({step: _last(arts, kind) for step, kind in KIND_OF.items()})
    return {k: {"ok": v} for k, v in ok.items()}


def save_schedule(state: dict) -> None:
    SCHEDULE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def _age(state: dict, name: str, today: date) -> int | None:
    ok = state.get(name, {}).get("ok")
    return (today - date.fromisoformat(ok)).days if ok else None


def _mark(state: dict, name: str, ok: bool, today: date) -> None:
    s = state.setdefault(name, {})
    if ok:
        s["ok"] = str(today)
    if s.get("try") != str(today):
        s["try"], s["n"] = str(today), 0
    s["n"] = s.get("n", 0) + 1


def due_steps(state: dict, now: datetime) -> list[str]:
    """Wat deze run moet doen: alles van vandaag dat nog niet gelukt is, plus hooguit één achterstallige weekstap.
    FORCE_STEPS=meme,prompt forceert stappen (handmatige run), FORCE_WEEKDAY=2 doet alsof het woensdag is."""
    if os.getenv("FORCE_STEPS"):
        return [s.strip() for s in os.environ["FORCE_STEPS"].split(",") if s.strip()]
    today = now.date()
    wd = int(os.getenv("FORCE_WEEKDAY", today.weekday()))
    due, catchup = [], []
    for name, days, can_catch_up in STEPS:
        if name == "seo" and not seo.enabled():
            continue
        s = state.get(name, {})
        if s.get("ok") == str(today) or (s.get("try") == str(today) and s.get("n", 0) >= MAX_TRIES):
            continue
        if days is None or wd in days:
            due.append(name)
        elif can_catch_up:
            age = _age(state, name, today)
            if age is None or age >= CATCHUP_DAYS:
                catchup.append(name)
    return due + catchup[:1]


def watchdog(state: dict, today: date) -> list[str]:
    """Stappen waarvan de laatste geslaagde keer te lang geleden is. Stilte is geen bewijs dat alles draait."""
    out = []
    for name, max_age in MAX_AGE.items():
        if name in ("seo",) and not seo.enabled():
            continue
        if name == "bluesky" and not _bsky_enabled():
            continue
        age = _age(state, name, today)
        if age is None:
            out.append(f"{name} nog nooit gelukt")
        elif age > max_age:
            out.append(f"{name} {age} dagen niet gelukt (laatst {state[name]['ok']})")
    return out


def _bsky_enabled() -> bool:
    from . import social

    return social.enabled()


def post_memes() -> int:
    """Plaatst de meme van vandaag op Bluesky: NL én EN, elk één keer (vlag in het JSON-bestand).
    Stil overslaan als Bluesky niet geconfigureerd is."""
    from . import images, social

    if not social.enabled():
        return 0
    memes = editorial.load_memes()
    if not memes:
        return 0
    m = memes[0]
    if m["date"] != datetime.now().strftime("%Y-%m-%d"):
        return 0  # alleen de meme van vandaag, nooit een achterstand inhalen
    tmp = DIST.parent / ".tmp"
    tmp.mkdir(exist_ok=True)
    n = 0
    for key, lang, label, top, bottom, alt, tags in (
        ("bsky_nl", "nl", "AI-MEME VAN DE DAG", m["top"], m["bottom"], m.get("alt", ""), m.get("hashtags", [])),
        ("bsky_en", "en", "AI MEME OF THE DAY", m.get("top_en"), m.get("bottom_en"), m.get("alt_en", ""), m.get("hashtags_en", [])),
    ):
        if not top or m.get(key):
            continue
        path = images.meme_card(top, bottom, tmp / f"{m['date']}-{lang}.png", m["date"] + lang, label)
        hashtags = " ".join("#" + re.sub(r"\W", "", t) for t in (tags or [])[:3]) or ("#AI #ChatGPT #meme" if lang == "nl" else "#AI #ChatGPT #meme")
        text = f"{top}\n{bottom}\n\n{hashtags}\n{SITE['url']}/memes/{m['date']}/"
        try:
            uri = social.post_image(text, str(path), f"{top} — {bottom}. {alt}", lang)
        except Exception as e:  # noqa: BLE001
            print(f"  bluesky-fout ({lang}): {e}")
            continue
        if uri:
            m[key] = uri
            (MEMES / f"{m['date']}.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
            print(f"  bluesky {lang}: {uri}")
    return n


def post_persona(art: dict) -> int:
    """Maxim-stuk als linkkaart op Bluesky (NL)."""
    from . import images, social

    if not social.enabled():
        return 0
    tmp = DIST.parent / ".tmp"
    tmp.mkdir(exist_ok=True)
    kind = {"column": "Column", "practice": "Uit de praktijk", "review": "Review"}.get(art.get("kind"), "Mening")
    og = images.og_card(art["title"], f"{kind} · Maxim", tmp / f"{art['slug']}.png", art["slug"])
    text = f"{kind} van Maxim: {art['title']}\n\n{art['meta']}"
    try:
        uri = social.post(text[:290], SITE["url"] + art["path"], art["title"], art["meta"], str(og))
    except Exception as e:  # noqa: BLE001
        print(f"  bluesky-fout (persona): {e}")
        return 0
    return 1 if uri else 0


def cmd_seo() -> int:
    print(seo.run(editorial.load_articles()) or "seo: GSC_CLIENT_ID/GSC_CLIENT_SECRET/GSC_REFRESH_TOKEN ontbreken")
    return 0


def cmd_build() -> int:
    from .render import build

    n = build()
    print(f"site gebouwd: {n} pagina's → {DIST}")
    return 0


def cmd_status() -> int:
    arts = editorial.load_articles()
    print(f"{len(arts)} artikelen, {len(list(MEMES.glob('*.json')))} memes, {len(list(PROMPTS.glob('*.json')))} prompts")
    for a in arts[:10]:
        print(f"  {a['date']} [{a['category']}] {a['title']}")
    state, now = load_schedule(arts), datetime.now()
    print(f"\nplanner ({'content/schedule.json' if SCHEDULE.exists() else 'nog geen schedule.json, afgeleid uit content/'}):")
    for name in MAX_AGE:
        s = state.get(name, {})
        print(f"  {name:<14} laatst gelukt {s.get('ok') or '-':<10}  pogingen {s.get('try', '-')} x{s.get('n', 0)}")
    print(f"volgende run doet: {', '.join(due_steps(state, now)) or '(alleen nieuws)'}")
    alarms = watchdog(state, now.date())
    print("waakhond: " + ("; ".join(alarms) if alarms else "alles binnen de termijn"))
    return 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "run"
    fn = {"seo": cmd_seo, "run": cmd_run, "dry": cmd_dry, "build": cmd_build, "status": cmd_status}.get(cmd)
    if not fn:
        print(__doc__)
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
