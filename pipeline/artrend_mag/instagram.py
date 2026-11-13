"""Post one of today's ARTREND shorts to Instagram (@artrend.official) as a Reel, through the official
Instagram Graph API (content publishing, resumable upload) — no browser automation, no unofficial endpoints.

Needs, in the environment or the project `.env` (never stored anywhere else):
  IG_USER_ID        the Instagram professional account id linked to a Facebook Page
  IG_ACCESS_TOKEN   a long-lived token with instagram_basic + instagram_content_publish
  ARTREND_IG_PUBLISH=1   explicit go-live switch. The shorts use institutions' official images, which were cleared
                         for internal viewing only; set this only once posting them publicly is allowed.
Without all three the run is a dry run: it picks the video, writes the caption and logs what it would post.

Choice: the Korean edition's short first (the account's audience), then JP, EUROPE, AMERICAS; a subject already
posted in the last POST_GAP_DAYS days is skipped so the feed does not repeat itself.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests

from .config import WORK_ROOT

GRAPH = "https://graph.facebook.com/v21.0"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload/v21.0"
SHORTS = WORK_ROOT / "outputs" / "shorts"
LOG = WORK_ROOT / "work" / "auto" / "instagram_posted.json"
ORDER = ("KR", "JP", "EUROPE", "AMERICAS")
POST_GAP_DAYS = 14
MAX_CAPTION = 2200
MAX_TAGS = 30
POLL_EVERY, POLL_MAX = 10, 60  # up to 10 minutes for Instagram to process the video


def settings(env=os.environ, dotenv: Path = WORK_ROOT / ".env") -> dict:
    vals = {}
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    get = lambda k: env.get(k) or vals.get(k)
    return dict(user_id=get("IG_USER_ID"), token=get("IG_ACCESS_TOKEN"), live=get("ARTREND_IG_PUBLISH") == "1")


def history() -> list:
    return json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []


def choose(asof: dt.date, log: Optional[list] = None) -> Optional[dict]:
    log = history() if log is None else log
    recent = {e.get("subject") for e in log if e.get("status") == "posted"
              and (asof - dt.date.fromisoformat(e["date"])).days < POST_GAP_DAYS}
    metas = []
    for ed in ORDER:
        f = SHORTS / asof.isoformat() / f"{ed}.json"
        if f.exists() and (SHORTS / asof.isoformat() / f"{ed}.mp4").exists():
            metas.append(json.loads(f.read_text(encoding="utf-8")))
    fresh = [m for m in metas if m.get("subject") not in recent]
    return (fresh or [None])[0]


def caption_of(meta: dict) -> str:
    text = meta.get("caption") or meta.get("title") or ""
    if meta.get("image_credit"):
        text += f"\n\n이미지: {meta['image_credit']}"
    tags = re.findall(r"#\S+", text)
    for extra in tags[MAX_TAGS:]:  # Instagram rejects captions with more than 30 hashtags
        text = text.replace(extra, "", 1)
    return text[:MAX_CAPTION].rstrip()


class PostError(RuntimeError):
    pass


def _check(r: requests.Response) -> dict:
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:300]}
    if r.status_code >= 400 or "error" in body:
        err = body.get("error") or body
        raise PostError(f"HTTP {r.status_code}: {err.get('message') if isinstance(err, dict) else err}")
    return body


def post_reel(video: Path, caption: str, user_id: str, token: str, s: Optional[requests.Session] = None,
              sleep=time.sleep) -> dict:
    """Create a REELS container, upload the file (resumable), wait until processed, publish. Returns ids + permalink."""
    s = s or requests.Session()
    c = _check(s.post(f"{GRAPH}/{user_id}/media", data=dict(media_type="REELS", upload_type="resumable", caption=caption,
                                                               share_to_feed="true", access_token=token), timeout=60))
    cid = c["id"]
    data = video.read_bytes()
    up = _check(s.post(f"{RUPLOAD}/{cid}", data=data, timeout=600,
                       headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))}))
    if not up.get("success", True):
        raise PostError(f"upload refused: {up}")
    for _ in range(POLL_MAX):
        st = _check(s.get(f"{GRAPH}/{cid}", params=dict(fields="status_code,status", access_token=token), timeout=60))
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise PostError(f"processing failed: {st.get('status')}")
        sleep(POLL_EVERY)
    else:
        raise PostError("processing timed out")
    pub = _check(s.post(f"{GRAPH}/{user_id}/media_publish", data=dict(creation_id=cid, access_token=token), timeout=60))
    link = _check(s.get(f"{GRAPH}/{pub['id']}", params=dict(fields="permalink", access_token=token), timeout=60)).get("permalink")
    return dict(container_id=cid, media_id=pub["id"], permalink=link)


def run(asof: dt.date, dry: bool = False) -> dict:
    cfg = settings()
    meta = choose(asof)
    entry = dict(date=asof.isoformat(), at=dt.datetime.now().isoformat(timespec="seconds"))
    if not meta:
        entry.update(status="skipped", reason="no new short today")
    else:
        video = SHORTS / asof.isoformat() / meta["file"]
        cap = caption_of(meta)
        entry.update(edition=meta["edition"], subject=meta.get("subject"), file=str(video), caption=cap)
        missing = [k for k, v in (("IG_USER_ID", cfg["user_id"]), ("IG_ACCESS_TOKEN", cfg["token"])) if not v]
        if not cfg["live"]:
            missing.append("ARTREND_IG_PUBLISH=1")
        if dry or missing:
            entry.update(status="dry_run", reason="requested" if dry else "not set: " + ", ".join(missing))
        else:
            try:
                entry.update(status="posted", **post_reel(video, cap, cfg["user_id"], cfg["token"]))
            except (PostError, requests.RequestException) as e:
                entry.update(status="failed", reason=str(e)[:300])
    log = history()
    log.append(entry)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log[-200:], ensure_ascii=False, indent=1), encoding="utf-8")
    return entry


def check() -> dict:
    """Token and account check without posting."""
    cfg = settings()
    if not (cfg["user_id"] and cfg["token"]):
        return dict(ok=False, reason="IG_USER_ID / IG_ACCESS_TOKEN not set")
    try:
        me = _check(requests.get(f"{GRAPH}/{cfg['user_id']}", params=dict(fields="username,account_type", access_token=cfg["token"]), timeout=30))
        return dict(ok=True, username=me.get("username"), live=cfg["live"])
    except (PostError, requests.RequestException) as e:
        return dict(ok=False, reason=str(e)[:300])


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="post today's ARTREND short to Instagram as a Reel")
    ap.add_argument("--asof", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="only verify the token/account")
    a = ap.parse_args(argv)
    out = check() if a.check else run(a.asof, a.dry_run)
    print(json.dumps({k: v for k, v in out.items() if k != "caption"}, ensure_ascii=False))
    if out.get("status") == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
