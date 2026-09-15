"""CLI van de redactie.

  python -m engine.run run      # editie schrijven (ochtend: + meme + prompt; wo: uitleg; zo: week)
  python -m engine.run dry      # alleen bronnen scannen en tonen
  python -m engine.run build    # site renderen naar dist/
  python -m engine.run status   # overzicht content/
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from . import editorial, fetch, notify, seo
from .config import DIST, MEMES, PROMPTS, SITE


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
    extra = {}
    if stamp.hour < 11 or os.getenv("FORCE_MORNING"):  # ochtendeditie
        steps = [("meme", lambda: editorial.meme(existing, stamp)), ("prompt", lambda: editorial.prompt_of_day(stamp))]
        wd = int(os.getenv("FORCE_WEEKDAY", stamp.weekday()))
        if wd == 0:  # maandag: Search Console-lus (titels/meta + nieuwe onderwerpen voor de uitleg van woensdag)
            steps.insert(0, ("seo", lambda: seo.run(existing)))
        if wd == 1:  # dinsdag: Maxims mening over het nieuws
            steps.append(("column", lambda: editorial.column(existing, stamp)))
        if wd == 2:
            steps.append(("uitleg", lambda: editorial.evergreen(existing, stamp)))
        if wd == 3:  # donderdag: uit de praktijk
            steps.append(("praktijk", lambda: editorial.practice(existing, stamp)))
        if wd == 5:  # zaterdag: review
            steps.append(("review", lambda: editorial.review(existing, stamp)))
        if wd == 6:
            steps.append(("weekoverzicht", lambda: editorial.weekoverzicht(existing, stamp)))
        for label, fn in steps:
            try:
                extra[label] = fn()
            except Exception as e:  # noqa: BLE001
                print(f"  {label}-fout: {e}")
    fetch.save_ledger(ledger)
    bsky = post_memes()
    for label in ("column", "praktijk", "review"):
        art = extra.get(label)
        if art:
            bsky += post_persona(art)
    cost = (USAGE["prompt"] * 0.30 + USAGE["completion"] * 1.20) / 1e6
    parts = [f"{len(new)} nieuws"] + ([f"{takes} takes"] if takes else []) + [k for k, v in extra.items() if v and k != "seo"] + ([f"bluesky {bsky}"] if bsky else [])
    line = (f"chatgpthelp.nl {stamp:%d-%m %H:%M}: {', '.join(parts)} · {len(stories)} verhalen gezien · "
            f"{USAGE['calls']} LLM-calls ≈ ${cost:.3f}")
    if new:
        line += "\n" + "\n".join(f"• {a['title']} — {SITE['url']}{a['path']}" for a in new)
    if extra.get("seo"):
        line += "\n" + extra["seo"]
    print(line)
    notify.slack(line)
    return 0


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
