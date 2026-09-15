"""Bluesky-poster (gratis API, app-password). Alleen actief als BSKY_HANDLE + BSKY_APP_PASSWORD
gezet zijn; anders stil overslaan. Post = tekst + link-card met OG-beeld."""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

PDS = "https://bsky.social"


def _req(path, data=None, token=None, content_type="application/json"):
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = data if isinstance(data, (bytes, bytearray)) else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(f"{PDS}/xrpc/{path}", data=body, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def enabled() -> bool:
    return bool(os.getenv("BSKY_HANDLE") and os.getenv("BSKY_APP_PASSWORD"))


def post(text: str, url: str, title: str, description: str, image_path: str | None = None) -> str | None:
    if not enabled():
        return None
    sess = _req("com.atproto.server.createSession", {"identifier": os.environ["BSKY_HANDLE"], "password": os.environ["BSKY_APP_PASSWORD"]})
    tok, did = sess["accessJwt"], sess["did"]
    embed = {"$type": "app.bsky.embed.external", "external": {"uri": url, "title": title[:200], "description": description[:300]}}
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as fh:
            blob = _req("com.atproto.repo.uploadBlob", fh.read(), tok, "image/png")
        embed["external"]["thumb"] = blob["blob"]
    # facets voor de link in de tekst (optioneel; card volstaat)
    record = {
        "$type": "app.bsky.feed.post",
        "text": text[:300],
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "langs": ["nl"],
        "embed": embed,
    }
    out = _req("com.atproto.repo.createRecord", {"repo": did, "collection": "app.bsky.feed.post", "record": record}, tok)
    return out.get("uri")
