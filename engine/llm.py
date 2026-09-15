"""DeepSeek-client (OpenAI-compatibel), stdlib-only. Geeft JSON terug of gooit."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

from .config import DEEPSEEK_MODEL

API_URL = "https://api.deepseek.com/v1/chat/completions"
USAGE = {"prompt": 0, "completion": 0, "calls": 0}


def chat(messages, temperature=0.6, max_tokens=3000, json_mode=True, retries=3, model=None):
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY ontbreekt")
    body = {
        "model": model or DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # deepseek-flash is een redeneermodel; zonder dit zit max_tokens vol met denkwerk en is content leeg
        "thinking": {"type": "disabled"},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    data = json.dumps(body).encode()
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(
            API_URL, data=data,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                out = json.loads(r.read())
            u = out.get("usage", {})
            USAGE["prompt"] += u.get("prompt_tokens", 0)
            USAGE["completion"] += u.get("completion_tokens", 0)
            USAGE["calls"] += 1
            return out["choices"][0]["message"]["content"]
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"DeepSeek faalde na {retries} pogingen: {last}")


def _repair(raw: str) -> str:
    """Letterlijke regeleindes en tabs binnen JSON-strings escapen (veelgemaakte LLM-fout)."""
    out, in_str, esc = [], False, False
    for ch in raw:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            elif ch == "\n":
                out.append("\\n")
                continue
            elif ch == "\t":
                out.append("\\t")
                continue
        elif ch == '"':
            in_str = True
        out.append(ch)
    return "".join(out)


def extract_json(raw: str):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S)
    m = re.search(r"\{.*\}", raw, re.S)
    cand = m.group(0) if m else raw
    for attempt in (cand, _repair(cand)):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    raise ValueError("geen geldige JSON: " + raw[:200])


def ask_json(system: str, user: str, temperature=0.6, max_tokens=3000, model=None):
    raw = chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature, max_tokens=max_tokens, json_mode=True, model=model,
    )
    return extract_json(raw)
