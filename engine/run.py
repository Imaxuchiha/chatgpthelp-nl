"""CLI van de redactie.

  python -m engine.run run      # editie schrijven (ochtend: + meme + prompt; wo: uitleg; zo: week)
  python -m engine.run dry      # alleen bronnen scannen en tonen
  python -m engine.run build    # site renderen naar dist/
  python -m engine.run status   # overzicht content/
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from . import editorial, fetch, notify
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
    existing = editorial.load_articles()
    extra = {}
    if stamp.hour < 11 or os.getenv("FORCE_MORNING"):  # ochtendeditie
        steps = [("meme", lambda: editorial.meme(existing, stamp)), ("prompt", lambda: editorial.prompt_of_day(stamp))]
        if stamp.weekday() == 2:
            steps.append(("uitleg", lambda: editorial.evergreen(existing, stamp)))
        if stamp.weekday() == 6:
            steps.append(("weekoverzicht", lambda: editorial.weekoverzicht(existing, stamp)))
        for label, fn in steps:
            try:
                extra[label] = fn()
            except Exception as e:  # noqa: BLE001
                print(f"  {label}-fout: {e}")
    fetch.save_ledger(ledger)
    cost = (USAGE["prompt"] * 0.30 + USAGE["completion"] * 1.20) / 1e6
    parts = [f"{len(new)} nieuws"] + [k for k, v in extra.items() if v]
    line = (f"chatgpthelp.nl {stamp:%d-%m %H:%M}: {', '.join(parts)} · {len(stories)} verhalen gezien · "
            f"{USAGE['calls']} LLM-calls ≈ ${cost:.3f}")
    if new:
        line += "\n" + "\n".join(f"• {a['title']} — {SITE['url']}{a['path']}" for a in new)
    print(line)
    notify.slack(line)
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
    fn = {"run": cmd_run, "dry": cmd_dry, "build": cmd_build, "status": cmd_status}.get(cmd)
    if not fn:
        print(__doc__)
        return 2
    return fn()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
