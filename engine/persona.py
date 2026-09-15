"""Het personage 'Maxim': columnist met een eigen mening, eigen praktijkcijfers en eigen tools.

Bronnen:
- content/persona/maxim.json  — stem, opvattingen, tools die hij echt gebruikt, harde regels (publiek)
- content/persona/lessen.json — geanonimiseerde praktijklessen met cijfers (optioneel; ontbreekt het
  bestand, dan schrijft Maxim zonder eigen cijfers)

Harde regel: cijfers in een column moeten letterlijk uit de lessen of de nieuwsbronnen komen.
"""
from __future__ import annotations

import json

from .config import CONTENT
from .fetch import tokens

PERSONA_DIR = CONTENT / "persona"
USED = PERSONA_DIR / "gebruikt.json"


def load() -> dict:
    return json.loads((PERSONA_DIR / "maxim.json").read_text(encoding="utf-8"))


def lessons() -> list[dict]:
    p = PERSONA_DIR / "lessen.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def used() -> dict:
    if USED.exists():
        return json.loads(USED.read_text(encoding="utf-8"))
    return {"lessen": [], "tools": [], "columns": []}


def save_used(u: dict) -> None:
    USED.write_text(json.dumps(u, ensure_ascii=False, indent=1), encoding="utf-8")


def relevant_lessons(text: str, k: int = 3, exclude: list[str] | None = None, min_score: int = 1) -> list[dict]:
    """Kies de lessen die inhoudelijk het best bij een tekst passen (woordoverlap + topics)."""
    exclude = set(exclude or [])
    tt = tokens(text.lower())
    scored = []
    for l in lessons():
        if l["id"] in exclude:
            continue
        lt = tokens(l["text"].lower()) | {w for t in l["topics"] for w in t.split()}
        score = len(tt & lt) + 3 * sum(1 for t in l["topics"] if t in text.lower())
        scored.append((score, l))
    scored.sort(key=lambda x: -x[0])
    return [l for s, l in scored[:k] if s >= min_score]


def brief(p: dict) -> str:
    """Compacte persona-omschrijving voor in een prompt."""
    tools = "\n".join(f"- {t['tool']}: {t['status']}; {t['use']}. Mening: {t['opinion']}" for t in p["tools_used"])
    return f"""PERSONAGE: {p['name']} — {p['role']}.
{p['short_bio']}

STEM:
{chr(10).join('- ' + v for v in p['voice'])}

OPVATTINGEN (hier komt zijn mening vandaan):
{chr(10).join('- ' + b for b in p['beliefs'])}

TOOLS DIE HIJ ECHT GEBRUIKT (alleen hierover mag hij eigen ervaring claimen):
{tools}

HARDE REGELS:
{chr(10).join('- ' + r for r in p['rules'])}"""


def lessons_block(ls: list[dict]) -> str:
    if not ls:
        return "(geen eigen praktijkcijfers beschikbaar: gebruik GEEN eigen cijfers)"
    return "\n".join(f"[Les {l['id']}] {l['text']}" for l in ls)
