"""Art criticism outlets from the editor's outlet research (editorial/critique_outlets.json, checked 2026-11-10).

One source per live outlet that is not already covered elsewhere; the collectable listing (the outlet's own RSS/Atom
feed, else a dated review/criticism listing) was found by `work/dev/CritOutlets/discover.py` and is kept in
`crit_outlets_sites.json`. Outlets whose terms forbid automated access, or that were never given permission
(ARTnews, Art in America, Artforum, ArtAsiaPacific), are not here.

Access: robots.txt enforced by Fetcher, one listing request per run (incremental) or up to 3 pages (initial).
Stored: title, URL, date, byline and for feeds the publisher's own summary cut to 300 characters. No article bodies.
Type: a criticism outlet's pieces are 'criticism' unless the feed category says review or interview; a news-focused
outlet's pieces count as criticism only when their category or URL says review/critique.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from .. import db
from ._common import parse_feed
from .inst_news import extract_listing

SITES = Path(__file__).with_name("crit_outlets_sites.json")
PARSER_VERSION = "crit-outlets-1"

REVIEW = re.compile(r"review|reseña|resenha|recensione|recension|rezension|kritik|critique|critica|crítica|비평|리뷰|평론|展評|レビュー|批評|評論", re.I)
INTERVIEW = re.compile(r"interview|conversation|entretien|intervista|entrevista|gespräch|인터뷰|대담|インタビュー|対談|鼎談", re.I)
NOT_CRIT = re.compile(r"sponsored|advert|partner content|광고|협찬|press release|보도자료|event listing|job|구인|募集|お知らせ|open call|ausschreibung|gala", re.I)


def load_sites() -> list:
    return json.loads(SITES.read_text(encoding="utf-8")) if SITES.exists() else []


def piece_type(focus: str, url: str, categories) -> tuple:
    """(article_type, basis) for one listed piece."""
    tags = " ".join(categories or [])
    path = urllib.parse.urlsplit(url or "").path
    if NOT_CRIT.search(tags):
        return "news", "crit outlet: category is not criticism"
    if INTERVIEW.search(tags) or INTERVIEW.search(path):
        return "interview", "crit outlet: interview category/url"
    if REVIEW.search(tags) or REVIEW.search(path):
        return "review", "crit outlet: review category/url"
    if focus == "news":
        return "news", "crit outlet (news-focused): no review marker"
    return "criticism", "crit outlet (criticism-focused, editor research 2026-11-10)"


_SITES = {s["source_id"]: s for s in load_sites()}
SOURCES = [dict(
    source_id=s["source_id"], blueprint_data_id=None, blueprint_org_id=None,
    name=f"{s['name']} — criticism", owner_group=s["name"], source_kind="media", region_scope=s["edition"],
    country_codes=s.get("region"), access_method="rss" if s["method"] == "feed" else "html", base_url=s["home"],
    entry_url=s["url"], terms_url=None, text_storage_policy="raw_internal", priority="P1",
    st_official_doc="n/a(outlet's public listing)",
    st_collection_terms="outlet's own public feed/listing; metadata only (title, date, URL, byline, <=300-char summary), robots enforced",
    st_image_terms="images not stored",
    max_requests=10, notes=f"editor critique-outlet research 2026-11-10 ({s['focus']}); work/dev/CritOutlets",
) for s in _SITES.values()]


def collect(ctx):
    site = _SITES[ctx.source_id]
    url, pages = site["url"], 1 if ctx.mode == "incremental" else 3
    tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    for _ in range(pages):
        resp = ctx.fetch(url)
        if site["method"] == "feed":
            items = [dict(title=i["title"], url=i["link"], date=(i.get("published") or i.get("updated") or "")[:10] or None,
                          author=i.get("author") or None, categories=i.get("categories") or [], excerpt=(i.get("summary") or "")[:300] or None)
                     for i in parse_feed(resp.content) if i.get("title") and i.get("link")]
        else:
            items = [dict(it, author=None, categories=[], excerpt=None) for it in extract_listing(resp.text, resp.url) if it["date"]]
        ctx.count("fetched", len(items))
        for it in items:
            if it["date"] and it["date"] > tomorrow:
                it["date"] = None
            kind, basis = piece_type(site["focus"], it["url"], it["categories"])
            ctx.evidence(resp, locator=f"criticism listing: {it['title'][:120]}", excerpt=it["date"])
            db.upsert_article(ctx.con, ctx.stats, source_id=ctx.source_id, canonical_url=it["url"], title=it["title"],
                              published_at=it["date"], author_text=it["author"], publisher=site["name"], owner_group=site["name"],
                              article_type=kind, type_basis=basis, categories="; ".join(it["categories"]) or None, excerpt=it["excerpt"])
            ctx.count("parsed")
        ctx.con.commit()
        if site["method"] == "feed" or ctx.mode == "incremental":
            break
        nxt = BeautifulSoup(resp.text, "lxml").select_one('a[rel="next"], link[rel="next"]')
        if not nxt or not nxt.get("href"):
            break
        url = urllib.parse.urljoin(resp.url, nxt["href"])
    ctx.note(f"criticism outlet {site['method']} {site['url']}; metadata only")
