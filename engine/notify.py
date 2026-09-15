"""Eén regel per dag naar Slack — ook als alles goed ging. Stilte = de motor zelf ligt eruit."""
from __future__ import annotations

import json
import os
import urllib.request


def slack(text: str) -> bool:
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        print("(geen SLACK_WEBHOOK_URL) " + text)
        return False
    req = urllib.request.Request(url, data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=20).read()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"slack mislukt: {e}")
        return False
