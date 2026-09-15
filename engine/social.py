"""Bluesky-poster (gratis API, app-password). Alleen actief als BSKY_HANDLE + BSKY_APP_PASSWORD
gezet zijn; anders stil overslaan. Twee soorten posts: beeld (meme) en link-card (artikel)."""
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone

PDS = "https://bsky.social"


def _req(path, data=None, token=None, content_type="application/json"):
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = data if isinstance(data, (bytes, bytearray)) else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(f"{PDS}/xrpc/{path}", data=body, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def enabled() -> bool:
    return bool(os.getenv("BSKY_HANDLE") and os.getenv("BSKY_APP_PASSWORD"))


def _session():
    s = _req("com.atproto.server.createSession", {"identifier": os.environ["BSKY_HANDLE"], "password": os.environ["BSKY_APP_PASSWORD"]})
    return s["accessJwt"], s["did"]


def _facets(text: str) -> list[dict]:
    """Hashtags en URL's klikbaar maken (byte-offsets, zoals AT Protocol eist)."""
    facets = []
    b = text.encode("utf-8")
    for m in re.finditer(r"#(\w+)", text):
        start = len(text[: m.start()].encode("utf-8"))
        facets.append({"index": {"byteStart": start, "byteEnd": start + len(m.group(0).encode("utf-8"))},
                       "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    for m in re.finditer(r"https?://\S+", text):
        start = len(text[: m.start()].encode("utf-8"))
        facets.append({"index": {"byteStart": start, "byteEnd": start + len(m.group(0).encode("utf-8"))},
                       "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group(0)}]})
    return facets


def _create(record: dict, tok: str, did: str) -> str | None:
    out = _req("com.atproto.repo.createRecord", {"repo": did, "collection": "app.bsky.feed.post", "record": record}, tok)
    return out.get("uri")


def _base(text: str, lang: str) -> dict:
    return {
        "$type": "app.bsky.feed.post",
        "text": text[:300],
        "facets": _facets(text[:300]),
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "langs": [lang],
    }


def post_image(text: str, image_path: str, alt: str, lang: str = "nl") -> str | None:
    """Beeldpost (meme). Geeft de post-URI terug of None als Bluesky uit staat."""
    if not enabled():
        return None
    tok, did = _session()
    with open(image_path, "rb") as fh:
        blob = _req("com.atproto.repo.uploadBlob", fh.read(), tok, "image/png")["blob"]
    rec = _base(text, lang)
    rec["embed"] = {"$type": "app.bsky.embed.images", "images": [{"image": blob, "alt": alt[:1000], "aspectRatio": {"width": 1, "height": 1}}]}
    return _create(rec, tok, did)


def post(text: str, url: str, title: str, description: str, image_path: str | None = None, lang: str = "nl") -> str | None:
    """Linkpost (artikel) met kaart."""
    if not enabled():
        return None
    tok, did = _session()
    embed = {"$type": "app.bsky.embed.external", "external": {"uri": url, "title": title[:200], "description": description[:300]}}
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as fh:
            embed["external"]["thumb"] = _req("com.atproto.repo.uploadBlob", fh.read(), tok, "image/png")["blob"]
    rec = _base(text, lang)
    rec["embed"] = embed
    return _create(rec, tok, did)


def set_profile(display_name: str, description: str, avatar_path: str | None = None) -> None:
    """Eenmalig: profielnaam, bio en avatar zetten."""
    tok, did = _session()
    rec = {"$type": "app.bsky.actor.profile", "displayName": display_name, "description": description}
    try:
        cur = _req(f"com.atproto.repo.getRecord?repo={did}&collection=app.bsky.actor.profile&rkey=self")
        rec = {**cur.get("value", {}), **rec}
    except Exception:  # noqa: BLE001
        pass
    if avatar_path:
        with open(avatar_path, "rb") as fh:
            rec["avatar"] = _req("com.atproto.repo.uploadBlob", fh.read(), tok, "image/png")["blob"]
    _req("com.atproto.repo.putRecord", {"repo": did, "collection": "app.bsky.actor.profile", "rkey": "self", "record": rec}, tok)


def did() -> str:
    return _session()[1]
