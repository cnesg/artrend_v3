"""Daily ARTREND shorts: one vertical (1080x1920, ~25-35s) video per edition, built from the web feed
(outputs/web_data/<date>/<EDITION>.json) and read-only DB facts.

Formats rotate by weekday and edition (ROTATION), so each morning gives four different kinds of video:
artist note (birth year, nationality, public-collection holdings, current show, why now, press, same-city show),
see-first / opening-soon / last-chance top 3, the week's exhibition keyword, and a three-item news brief.
A format without enough material yields to the next one. Narration: macOS Korean voice (`say -v Yuna`);
music: a generated ambient pad (no licensed audio); rendering: artrend_mag/render.swift (system frameworks only).

Images are the institutions' official exhibition images and public-collection works already listed in the feed.
They are fetched once into work/shorts_cache for rendering; the videos are for internal review (publishable=false):
clear image rights before posting anywhere public.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sqlite3
import urllib.request
import wave
from pathlib import Path
from typing import List, Optional

from . import config
from .daily_trend import NATION_KO, city_ko
from .daily_trend import short_org as dt_short_org

ROOT = config.PROJECT_ROOT if hasattr(config, "PROJECT_ROOT") else Path(__file__).resolve().parents[1]
FEED = ROOT / "outputs" / "web_data"
OUT = ROOT / "outputs" / "shorts"
WEB_PUBLIC = ROOT / "outputs" / "artrend-web" / "public" / "shorts"
CACHE = ROOT / "work" / "shorts_cache"
RENDER_SRC = Path(__file__).with_name("render.swift")
RENDER_BIN = ROOT / "work" / "bin" / "artrend_render"
EDITIONS = ("KR", "JP", "AMERICAS", "EUROPE")
VOICE = "Yuna"
KEEP_DAYS = 7
UA = "ARTREND-magazine-research/1.0 (internal preview)"
TAGS = {"KR": "#한국미술", "JP": "#일본미술", "AMERICAS": "#미주미술", "EUROPE": "#유럽미술"}


def short(text: str, n: int) -> str:
    t = re.sub(r"\s+", " ", (text or "").replace("《", "").replace("》", "")).strip()
    t = re.split(r"\s?:\s|\s[—–-]\s", t)[0].strip() or t
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def short_org(name: str) -> str:
    return re.sub(r"\s*\(.*?\)\s*", "", name or "").strip()


def md(iso: Optional[str]) -> Optional[str]:
    try:
        d = dt.date.fromisoformat((iso or "")[:10])
    except ValueError:
        return None
    return f"{d.month}월 {d.day}일"


# -- choosing today's subject
def candidates(page: dict) -> List[dict]:
    """The artist seen in both shows and press first (with an image), then the strongest early-signal shows with an image."""
    arts = [a for a in page.get("artists") or [] if a.get("image") and (a.get("shows") or a.get("works"))]
    arts.sort(key=lambda a: (-(bool(a.get("press")) and any(s["status"] != "종료" for s in a.get("shows") or [])),
                             -len(a.get("press") or []), -len(a.get("shows") or [])))
    early = [e for e in page.get("early") or [] if e.get("image")]
    return [dict(kind="artist", **a) for a in arts] + [dict(kind="show", **e) for e in early]


MIN_WIDTH = 640  # a thumbnail blown up to 1080x1920 looks broken


def width_of(path: Path) -> int:
    try:
        out = subprocess.run(["sips", "-g", "pixelWidth", str(path)], capture_output=True, text=True, timeout=30).stdout
        return int(re.search(r"pixelWidth:\s*(\d+)", out).group(1))
    except Exception:
        return 0


def sharp(url: Optional[str]) -> bool:
    p = fetch_image(url) if url else None
    return bool(p) and width_of(p) >= MIN_WIDTH


def recent_subjects(edition: str, asof: dt.date, days: int = 7) -> set:
    """Subjects already given a video in the last `days` days (so the daily video moves on to someone new)."""
    seen = set()
    for i in range(1, days + 1):
        f = OUT / (asof - dt.timedelta(days=i)).isoformat() / f"{edition}.json"
        if f.exists():
            seen.add(json.loads(f.read_text(encoding="utf-8")).get("subject"))
    return seen


def subject_of(c: dict) -> str:
    return c.get("name") or c.get("title") or ""


def pick(page: dict, avoid: set = frozenset()) -> Optional[dict]:
    cands = candidates(page)
    fresh = [c for c in cands if subject_of(c) not in avoid] or cands
    for c in fresh[:8]:
        if sharp(c.get("image")):
            return c
    return fresh[0] if fresh else None


def spoken(reason: str) -> str:
    """Feed reasons are written for the page; the video says them as a beat."""
    reason = re.sub(r"이번 주 (\d+)개 매체가 다뤘다", "이번 주 언론이 잇따라 다뤘다", reason)
    reason = re.sub(r"최근 석 달 동안 (\d+)개 매체에 나온 작가", r"석 달 사이 \1곳에서 이름이 나왔다", reason)
    return reason.split(" — ")[0] if len(reason) > 40 else reason


KR_CITY = {"Daejeon": "대전", "Ulsan": "울산", "Sejong": "세종", "Rome": "로마", "Roma": "로마", "Milan": "밀라노", "Milano": "밀라노",
           "Madrid": "마드리드", "Barcelona": "바르셀로나", "Amsterdam": "암스테르담", "Vienna": "빈", "Wien": "빈", "Basel": "바젤",
           "Zurich": "취리히", "Zürich": "취리히", "Brussels": "브뤼셀", "Lisbon": "리스본", "Munich": "뮤헨", "Hamburg": "함부르크",
           "Florence": "피렌체", "Copenhagen": "코펜하겐", "Stockholm": "스톡홀름", "Oslo": "오슬로", "Edinburgh": "에든버러",
           "Yokohama": "요코하마", "Kanazawa": "가나자와", "Fukuoka": "후쿠오카", "Nagoya": "나고야", "Naoshima": "나오시마",
           "Sapporo": "삿포로", "Hiroshima": "히로시마", "Kobe": "고베", "Chicago": "시카고", "San Francisco": "샌프란시스코",
           "Mexico City": "멕시코시티", "Ciudad de México": "멕시코시티", "Toronto": "토론토", "Miami": "마이애미",
           "Washington": "워싱턴", "Boston": "보스턴", "Philadelphia": "필라델피아", "Bogotá": "보고타", "Buenos Aires": "부에노스아이레스",
           "Rio de Janeiro": "리우데자네이루", "Lima": "리마", "Santiago": "산티아고",
           "Yongin": "용인", "Ansan": "안산", "Gwacheon": "과천", "Suwon": "수원", "Goyang": "고양", "Seongnam": "성남", "Paju": "파주",
           "Cheongju": "청주", "Jeonju": "전주", "Changwon": "창원", "Jeju": "제주", "Gangneung": "강릉", "Chuncheon": "춘천", "Pohang": "포항"}


def place(city: Optional[str]) -> Optional[str]:
    if not city:
        return None
    ko = KR_CITY.get(city) or next((v for k, v in KR_CITY.items() if k in city), None) or city_ko(city)
    return ko if re.search(r"[가-힣]", ko) or not re.fullmatch(r"[A-Za-z .'-]+", city) else city



# -- facts for the script (DB read-only)
HOLD_KO = {"The Museum of Modern Art": "뉴욕 현대미술관(MoMA)", "Whitney Museum of American Art": "휘트니미술관",
           "The Metropolitan Museum of Art": "메트로폴리탄미술관", "Art Institute of Chicago": "시카고미술관", "The Broad": "더 브로드",
           "Tate": "테이트", "Rijksmuseum": "레이크스미술관", "Cleveland Museum of Art": "클리블랜드미술관",
           "National Gallery of Art": "미국 국립미술관", "Smithsonian American Art Museum": "스미스소니언 미국미술관"}
COUNT_KO = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯"}
ORDINAL_KO = {1: "첫", 2: "두", 3: "세", 4: "네", 5: "다섯"}
HANGUL = re.compile(r"[가-힣]{2}")
ANY_HANGUL = re.compile(r"[가-힣]")
REGION_KO = {"KR": "국내", "JP": "일본", "AMERICAS": "미주", "EUROPE": "유럽"}
NOT_A_TITLE = re.compile(r",\s*(UK|USA|US|France|Germany|Italy|Japan)$")


def _db():
    try:
        return sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error:
        return None


def artist_facts(name: str, entity_id: Optional[str] = None) -> dict:
    """Birth/death year, nationality and public-collection holdings as recorded by the collections themselves."""
    con = _db()
    if con is None:
        return {}
    try:
        ids = [r[0] for r in con.execute("select entity_id from entities where canonical_name=? or entity_id=?", (name, entity_id or ""))]
        if not ids:
            return {}
        q = ",".join("?" * len(ids))
        bio = con.execute(f"select max(birth_year), max(death_year), max(nationality_text) from entities where entity_id in ({q})", ids).fetchone()
        holds = con.execute(f"select h.canonical_name, count(*) from works w join entities h on h.entity_id = w.holding_entity_id "
                            f"where w.artist_entity_id in ({q}) group by 1 order by 2 desc limit 3", ids).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        con.close()
    nat = NATION_KO.get((bio[2] or "").strip()) if bio and bio[2] else None
    died = bio[1] if bio and bio[1] and bio[1] < dt.date.today().year + 1 else None  # 9999 = 'living' in some collections
    return dict(born=bio[0] if bio else None, died=died, nationality=nat,
                holdings=[(HOLD_KO.get(h, h), n) for h, n in holds if n])


def title_ko(event_id: Optional[str]) -> Optional[str]:
    if not event_id:
        return None
    con = _db()
    if con is None:
        return None
    try:
        r = con.execute("select translation_ko from metadata_translations where source_table='events' and source_field='title' "
                        "and status='translated' and source_key=? order by updated_at desc limit 1", (event_id,)).fetchone()
    except sqlite3.Error:
        r = None
    finally:
        con.close()
    return r[0].strip() if r and r[0] and HANGUL.search(r[0]) else None


# -- wording helpers
def day(iso: Optional[str]) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat((iso or "")[:10])
    except ValueError:
        return None


def dot(iso: Optional[str], with_year: bool = True) -> Optional[str]:
    d = day(iso)
    return (f"{d.year}.{d.month}.{d.day}" if with_year else f"{d.month}.{d.day}") if d else None


def period(ev: dict) -> Optional[str]:
    s, e = dot(ev.get("start")), dot(ev.get("end"))
    if s and e:
        return f"{s} – {e[5:] if e[:4] == s[:4] else e}"
    return (f"{s} 개막" if s else None) or (f"~ {e}" if e else None)


def when_of(ev: dict, asof: dt.date) -> Optional[str]:
    s, e = day(ev.get("start")), day(ev.get("end"))
    if s and s > asof:
        return f"{md(ev['start'])} 개막 · " + ("내일" if (s - asof).days == 1 else f"{(s - asof).days}일 뒤")
    if e:
        left = (e - asof).days
        if left < 0:
            return None
        return "오늘 마감" if left == 0 else (f"{md(ev['end'])} 마감 · {left}일 남음" if left <= 14 else f"{md(ev['end'])}까지 전시 중")
    return "전시 중" if s else None


def said_when(ev: dict, asof: dt.date) -> str:
    s, e = day(ev.get("start")), day(ev.get("end"))
    if s and s > asof:
        return f"{md(ev['start'])}에 개막합니다."
    if e:
        left = (e - asof).days
        return "오늘이 마지막 날입니다." if left == 0 else (f"{md(ev['end'])}까지, {left}일 남았습니다." if left <= 14 else f"{md(ev['end'])}까지 이어집니다.")
    return ""


def show_title(ev: dict) -> tuple:
    """(on-screen title, Korean title to read aloud or None, original title shown small when translated)."""
    raw = short(re.sub(r"^\[[^\]]{1,20}\]\s*", "", ev.get("title") or "").strip(" “”\"'「」『』"), 60)
    if ANY_HANGUL.search(raw):
        return raw, raw, None
    ko = title_ko(ev.get("event_id") or ev.get("id"))
    ko = ko.strip(" “”\"'「」『』") if ko else None
    if ko and ko.lower() == raw.lower():
        return raw, None, None
    return (short(ko, 60), short(ko, 40), raw) if ko else (raw, None, None)


def venue(ev: dict) -> str:
    return dt_short_org(short_org(ev.get("venue") or ""))


def where(ev: dict) -> str:
    city = place(ev.get("city"))
    v = venue(ev)
    return " · ".join(x for x in (v, city if city and city not in v else None) if x)


def loc(ev: dict) -> str:
    city, v = place(ev.get("city")) or "", venue(ev)
    return v if not city or city in v else f"{city} {v}"


def clean_say(text: str) -> str:
    t = re.sub(r"[《》‘’“”\"]", "", text or "")
    t = re.sub(r"\s*(…|⋯|\.\.+)\s*", ", ", t.replace(" · ", ", "))
    t = re.sub(r"\((공식|종합|사진|영상)\)", "", t)
    t = re.sub(r"\.(\s*\.)+", ".", t)
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"[,\s]+$", ".", t) if t.endswith(",") else t


def credit(ev: dict) -> Optional[str]:
    org = venue(ev)
    return f"이미지: {org} 공식 페이지" if org else None


def beat(layout, title, say, image=None, kicker=None, sub=None, rows=None, big=None, big_label=None, num=None, credit=None):
    return dict(layout=layout, title=title, say=clean_say(say), image_url=image, kicker=kicker, sub=[s for s in (sub or []) if s],
                rows=[r for r in (rows or []) if r[1]], big=big, bigLabel=big_label, num=num, credit=credit)


def end_beat(image=None):
    return beat("end", "매일 아침, 지금 뜨는 미술", "아트렌드. 매일 아침, 지금 뜨는 미술.", image=image,
                sub=["@artrend.official", "출처: 각 기관 공식 페이지 · 언론 보도"])


# -- formats: each returns dict(fmt, subject, title, beats, sources) or None when today's material is too thin
def fmt_artist(page: dict, avoid: set) -> Optional[dict]:
    arts = [c for c in candidates(page) if c["kind"] == "artist"]
    subj = pick(dict(page, early=[]), avoid) if arts else None
    if not subj or subj["kind"] != "artist":
        return None
    asof = day(page["date"])
    name = subj["name"]
    shows = [s for s in subj.get("shows") or [] if s["status"] != "종료"] or subj.get("shows") or []
    show = shows[0] if shows else None
    imgs = [s["image"] for s in shows if s.get("image")] + [w["image"] for w in subj.get("works") or [] if w.get("image")]
    img = lambda k: imgs[k % len(imgs)] if imgs else None
    pressed = bool(subj.get("press"))
    upcoming = bool(show) and show["status"] == "개막 예정"
    hook = (("곧 전시가 열리고, 뉴스에도 올랐다" if upcoming else "지금 전시장과 뉴스에 동시에 떴다") if pressed and show
            else ("이번 주 기사마다 나오는 이름" if pressed else ("곧 무대에 오른다" if upcoming else "지금 막 무대에 올랐다")))
    out = [beat("hook", name, f"오늘의 작가, {name}. {hook}.", image=img(0), kicker="ARTIST NOTE · 오늘의 작가", sub=[hook],
                credit=credit(show) if show else None)]
    f = artist_facts(name, subj.get("entity_id"))
    bio = " · ".join(x for x in ((f"{f['born']}년생" if f.get("born") and not f.get("died") else
                                  (f"{f['born']}–{f['died']}" if f.get("born") else None)), f.get("nationality")) if x)
    holds = f.get("holdings") or []
    if bio or holds:
        said = (f"{f['born']}년에 태어난 {f.get('nationality') or ''} 작가입니다. " if f.get("born") else "")
        if holds:
            said += f"{holds[0][0]}이 작품 {holds[0][1]}점을 소장하고 있습니다."
        out.append(beat("fact" if holds else "info", "어떤 작가인가", said, image=img(len(imgs) - 1), kicker="WHO",
                        big=f"{holds[0][1]}점" if holds else None, big_label=f"{holds[0][0]} 소장 작품" if holds else None,
                        rows=[("출생", bio)] + [("소장", " · ".join(f"{h} {n}점" for h, n in holds[1:3]))],
                        credit="소장 기록: 각 미술관 공개 컬렉션"))
    if show:
        disp, said_title, orig = show_title(show)
        group = len(show.get("artists") or []) > 1
        kind = f"단체전 · {len(show['artists'])}명 참여" if group else "개인전"
        say = (f"{loc(show)}에서 " + (f"{said_title}, " if said_title else "") +
               ("단체전에 참여합니다. " if group else ("개인전이 곧 열립니다. " if upcoming else "개인전이 열리고 있습니다. ")) + said_when(show, asof))
        out.append(beat("info", f"《{disp}》", say, image=img(1), kicker="EXHIBITION · 지금 볼 전시", credit=credit(show),
                        rows=[("장소", where(show)), ("기간", period(show)), ("형식", kind), ("원제", orig)]))
    early = {short(e["title"], 60): e for e in page.get("early") or []}
    sig = early.get(short(show["title"], 60)) if show else None
    why = [spoken(w) for w in (sig or {}).get("reasons") or []][:3]
    if pressed:
        n = len(subj["press"])
        why.append(f"최근 보도 {n}건에 이름이 올랐다" if n > 1 else "최근 보도에 이름이 올랐다")
    if why:
        out.append(beat("text", "왜 지금인가", " ".join(w.rstrip(".") + "." for w in why[:3]), image=img(2), kicker="WHY NOW",
                        sub=why[:3], credit=credit(show) if show and imgs else None))
    if not (bio or holds) and len(why) < 2:
        return None  # too little to say about this artist today; the next format takes the slot
    ko_press = [p for p in subj.get("press") or [] if HANGUL.search(p.get("title") or "")]
    fx_press = [p for p in subj.get("press") or [] if not HANGUL.search(p.get("title") or "")]
    if not ko_press and fx_press:
        p = fx_press[0]
        head = re.sub(r"^(News|Press|Update)\s+", "", p["title"]).strip()
        out.append(beat("text", f"“{short(head, 70)}”", f"해외에서도 소식이 나왔습니다. {p.get('outlet') or ''}.", kicker="IN THE NEWS · 해외 보도",
                        sub=[" · ".join(x for x in (p.get("outlet"), md(p.get("date"))) if x)]))
    if ko_press:
        p = ko_press[0]
        head = re.sub(r"\s*\.\.\.$|…$", "", p["title"]).strip()
        out.append(beat("text", f"‘{short(head, 46)}’", f"언론의 시선. {short(head, 46)}.", kicker="IN THE NEWS · 보도",
                        sub=[" · ".join(x for x in (p.get("outlet"), md(p.get("date")), f"출처 {p['n_outlets']}곳" if p.get("n_outlets", 1) > 1 else None) if x)]))
    if show:
        near = [e for e in (page.get("exhibitions") or {}).get("all", {}).get("open_now", [])
                if e.get("city") == show.get("city") and e.get("venue") != show.get("venue") and name not in (e.get("artists") or [])]
        if near:
            e = near[0]
            disp, said_title, _ = show_title(e)
            out.append(beat("list", f"《{disp}》", f"같은 {place(show.get('city')) or '도시'}에서 함께 볼 전시. {venue(e)}" +
                            (f"의 {said_title}." if said_title else "입니다."), image=e.get("image"), kicker="ALSO SEE · 같은 도시에서",
                            rows=[("장소", where(e)), ("기간", period(e))], credit=credit(e)))
    out.append(end_beat(img(0)))
    src = [s.get("url") for s in subj.get("shows") or [] if s.get("url")] + [p["url"] for p in subj.get("press") or []][:4]
    return dict(fmt="artist", subject=name, title=f"{name} — 왜 지금 뜨나", beats=out, sources=src)


ROUNDUPS = {
    "early": ("SEE FIRST · 먼저 가볼 전시", "지금 먼저 가볼 전시", "붐비기 전에 먼저 가 볼 전시"),
    "upcoming": ("OPENING SOON · 곧 개막", "곧 문을 여는 전시", "곧 문을 여는 전시"),
    "closing": ("LAST CHANCE · 마감 임박", "놓치면 아쉬운 마감 임박 전시", "곧 끝나는 전시"),
}


def roundup_items(page: dict, kind: str, n: int = 3) -> List[dict]:
    asof = day(page["date"])
    ex = page.get("exhibitions") or {}
    if kind == "early":
        pool = [e for e in page.get("early") or [] if e.get("level") != "체크"]
    elif kind == "upcoming":
        pool = sorted([e for e in (ex.get("all") or {}).get("upcoming") or ex.get("upcoming") or [] if (day(e.get("start")) or asof) > asof],
                      key=lambda e: (not e.get("image"), e.get("kind") not in ("museum", "gallery"), e.get("start") or ""))
    else:
        pool = sorted([e for e in (ex.get("all") or {}).get("closing") or ex.get("closing") or [] if (day(e.get("end")) or asof) >= asof],
                      key=lambda e: (not e.get("image"), e.get("kind") not in ("museum", "gallery"), e.get("end") or ""))
    out, venues = [], set()
    for e in pool:
        v = venue(e)
        if not v or v in venues or not e.get("title") or NOT_A_TITLE.search(e["title"]):
            continue
        if kind == "closing" and day(e.get("end")) == asof and len(pool) > n + 2:
            continue
        venues.add(v)
        out.append(e)
        if len(out) == n:
            break
    return out


def fmt_roundup(page: dict, kind: str) -> Optional[dict]:
    items = roundup_items(page, kind)
    if len(items) < 3 or not any(e.get("image") for e in items):
        return None
    asof = day(page["date"])
    kicker, title, said = ROUNDUPS[kind]
    head = f"{title} {len(items)}"
    out = [beat("hook", head, f"{REGION_KO.get(page.get('edition'), '')}에서 {said} {COUNT_KO[len(items)]} 곳을 골랐습니다.",
                image=next(e["image"] for e in items if e.get("image")), kicker=kicker,
                sub=[" · ".join(venue(e) for e in items)], credit=credit(next(e for e in items if e.get("image"))))]
    for i, e in enumerate(items, 1):
        disp, said_title, orig = show_title(e)
        reason = spoken((e.get("reasons") or [""])[0]) if kind == "early" else None
        say = (f"{ORDINAL_KO[i]} 번째. {loc(e)}" + (f", {said_title}." if said_title else ".") +
               f" {said_when(e, asof)} " + (reason or ""))
        out.append(beat("list", f"《{disp}》", say, image=e.get("image"), num=f"{i:02d}", kicker=" · ".join(x for x in (e.get("level"), when_of(e, asof)) if x),
                        rows=[("장소", where(e)), ("기간", period(e)),
                              ("원제", orig)], sub=[reason] if reason else None, credit=credit(e)))
    out.append(end_beat(items[0].get("image")))
    return dict(fmt=kind, subject=f"{kind}:" + "|".join(short(e["title"], 30) for e in items), title=head, beats=out,
                sources=[e.get("url") for e in items if e.get("url")])


def keyword_items(page: dict, h: dict) -> List[dict]:
    """'《t》 — venue(city), dates' lines of a theme headline, matched back to the feed's exhibitions for image and dates."""
    ex = (page.get("exhibitions") or {}).get("all") or {}
    pool = [e for k in ("open_now", "opened", "upcoming", "closing") for e in ex.get(k) or []] + list(page.get("early") or [])
    by_title = {short(e.get("title") or "", 60): e for e in pool}
    out = []
    for line in h.get("what") or []:
        m = re.match(r"《(.+?)》\s*[—-]\s*(.+)", line)
        if not m:
            continue
        e = by_title.get(short(m.group(1), 60))
        if e:
            out.append(e)
    return out


def fmt_keyword(page: dict) -> Optional[dict]:
    asof = day(page["date"])
    for h in page.get("headlines") or []:
        if h.get("axis") != "주제" or ":" not in h.get("title", ""):
            continue
        items = keyword_items(page, h)[:3]
        if len(items) < 2 or not any(e.get("image") for e in items):
            continue
        kw = h["title"].split(":", 1)[1].strip()
        point = (h.get("points") or [""])[0]
        m = re.search(r"전시 (\d+)\s*·\s*보도 (\d+)", h.get("evidence") or "")
        out = [beat("hook", kw, f"이번 주 전시장의 키워드, {kw}.", image=next((e["image"] for e in items if e.get("image")), None),
                    kicker="KEYWORD · 이번 주 전시 키워드", sub=[point], credit=next((credit(e) for e in items if e.get("image")), None))]
        if m:
            out.append(beat("fact", "같은 주제를 꺼낸 곳", f"{point} 이번 주 전시 {m.group(1)}곳과 보도 {m.group(2)}건이 같은 주제를 다뤘습니다.",
                            big=f"{int(m.group(1)) + int(m.group(2))}곳", big_label=f"전시 {m.group(1)} · 보도 {m.group(2)}", kicker="SIGNAL",
                            sub=[point]))
        for i, e in enumerate(items, 1):
            disp, said_title, orig = show_title(e)
            out.append(beat("list", f"《{disp}》", f"{loc(e)}" +
                            (f", {said_title}." if said_title else ".") + " " + said_when(e, asof), image=e.get("image"), num=f"{i:02d}",
                            kicker=kw, rows=[("장소", where(e)), ("기간", period(e)), ("원제", orig)], credit=credit(e)))
        out.append(end_beat(items[0].get("image")))
        return dict(fmt="keyword", subject=f"keyword:{kw}", title=f"이번 주 전시 키워드 — {kw}", beats=out,
                    sources=[e.get("url") for e in items if e.get("url")])
    return None


def news_title(n: dict) -> Optional[str]:
    t = n.get("title_ko") or (n.get("title") if HANGUL.search(n.get("title") or "") else None)
    if not t:
        return None
    t = re.sub(r"\s*(\.\.\.|…)$", "", re.sub(r"^\[[^\]]{1,12}\]\s*", "", t)).strip()
    t = re.sub(r"\s*(\.\.+|…|⋯)\s*", ", ", re.sub(r"\((공식|종합|사진|영상)\)", "", t)).strip(" ,.")
    return t if 12 <= len(t) <= 70 and len(ANY_HANGUL.findall(t)) >= 8 else None


def fmt_news(page: dict) -> Optional[dict]:
    asof = day(page["date"])
    pool = [n for n in page.get("news_week") or [] if news_title(n) and (asof - (day(n.get("date")) or asof)).days <= 4]
    pool.sort(key=lambda n: (-(n.get("n_outlets") or 1), n.get("topic") == "그 밖의 소식", -(day(n.get("date")) or asof).toordinal()))
    items, topics = [], []
    pool = [n for n in pool if n.get("topic") != "그 밖의 소식"]  # celebrity/event filler is not art news
    for n in pool:
        if topics.count(n.get("topic")) >= 2:
            continue
        topics.append(n.get("topic"))
        items.append(n)
        if len(items) == 3:
            break
    if len(items) < 3:
        return None
    out = [beat("hook", "이번 주 미술 뉴스 3", f"{REGION_KO.get(page.get('edition'), '')} 미술계, 이번 주 뉴스 세 가지만 짚어 봅니다.", kicker="NEWS BRIEF",
                sub=[" · ".join(sorted({n.get('topic') for n in items if n.get('topic')}))])]
    for i, n in enumerate(items, 1):
        t = news_title(n)
        outlets = n.get("n_outlets") or 1
        out.append(beat("list", t, f"{ORDINAL_KO[i]} 번째. {t}.", num=f"{i:02d}", kicker=n.get("topic"),
                        rows=[("날짜", md(n.get("date"))), ("출처", (n.get("sources") or [{}])[0].get("outlet") or ""),
                              ("보도", f"출처 {outlets}곳" if outlets > 1 else None)]))
    out.append(end_beat())
    return dict(fmt="news", subject="news:" + "|".join(news_title(n)[:20] for n in items), title="이번 주 미술 뉴스 3", beats=out,
                sources=[n.get("url") for n in items if n.get("url")])


# weekday rotation; editions start at different points so the same morning gives four different kinds of video
ROTATION = ("artist", "early", "keyword", "upcoming", "artist", "news", "closing")
BUILD = {"artist": None, "early": lambda p, a: fmt_roundup(p, "early"), "upcoming": lambda p, a: fmt_roundup(p, "upcoming"),
         "closing": lambda p, a: fmt_roundup(p, "closing"), "keyword": lambda p, a: fmt_keyword(p), "news": lambda p, a: fmt_news(p)}


def rotation_for(edition: str, d: dt.date) -> List[str]:
    k = (d.weekday() + 2 * (EDITIONS.index(edition) if edition in EDITIONS else 0)) % len(ROTATION)
    seq = list(ROTATION[k:] + ROTATION[:k])
    return list(dict.fromkeys(seq))


def script_for(page: dict, avoid: set = frozenset()) -> Optional[dict]:
    for f in rotation_for(page.get("edition") or "KR", day(page["date"])):
        s = fmt_artist(page, avoid) if f == "artist" else BUILD[f](page, avoid)
        if s and s["subject"] not in avoid:
            return s
    return None


# -- media helpers
def fetch_image(url: str) -> Optional[Path]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".img")
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 200 or not (r.headers.get("Content-Type") or "").startswith("image"):
                return None
            path.write_bytes(r.read())
        return path
    except Exception:
        return None


def narrate(text: str, dest: Path) -> Optional[float]:
    if not shutil.which("say") or not text.strip():
        return None
    try:
        subprocess.run(["say", "-v", VOICE, "-r", "178", "-o", str(dest), text], check=True, capture_output=True, timeout=60)
        info = subprocess.run(["afinfo", str(dest)], capture_output=True, text=True, timeout=30).stdout
        m = re.search(r"estimated duration:\s*([\d.]+)", info)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def renderer() -> Path:
    if not RENDER_BIN.exists() or RENDER_BIN.stat().st_mtime < RENDER_SRC.stat().st_mtime:
        RENDER_BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", str(RENDER_SRC), "-o", str(RENDER_BIN)], check=True, capture_output=True, timeout=600)
    return RENDER_BIN



MIN_SECONDS = {"hook": 3.2, "end": 3.0}
MUSIC_VOLUME = 0.16
PROGRESSIONS = (  # soft pad chords (Hz); rotated by date so the bed is not the same every morning
    ((220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)),
    ((146.83, 220.0, 293.66), (116.54, 174.61, 233.08), (174.61, 220.0, 261.63), (130.81, 196.0, 246.94)),
    ((164.81, 246.94, 329.63), (130.81, 196.0, 261.63), (146.83, 220.0, 293.66), (123.47, 185.0, 246.94)),
)


def music_bed(seconds: float, dest: Path, seed: int = 0, rate: int = 44100) -> Path:
    """Generated ambient pad (no licensed music needed): slow chords, soft attack, gentle fade."""
    import numpy as np
    chords = PROGRESSIONS[seed % len(PROGRESSIONS)]
    n = int((seconds + 1.0) * rate)
    t = np.arange(n) / rate
    out = np.zeros(n)
    span = 4.0
    for k in range(int(seconds // span) + 2):
        t0 = k * span
        env = np.clip((t - t0) / 1.5, 0, 1) * np.clip((t0 + span + 1.5 - t) / 1.5, 0, 1)
        if not env.any():
            continue
        for f in chords[k % len(chords)]:
            for det, amp in ((1.0, 1.0), (1.004, 0.6), (2.0, 0.18)):
                out += amp * env * np.sin(2 * np.pi * f * det * t + k)
        out += 0.5 * env * np.sin(2 * np.pi * chords[k % len(chords)][0] / 2 * t)
    out *= np.clip(t / 1.0, 0, 1) * np.clip((seconds + 1.0 - t) / 2.0, 0, 1)
    out = (out / (np.abs(out).max() or 1) * 0.6 * 32767).astype("<i2")
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(out.tobytes())
    return dest


def caption_for(s: dict, edition: str) -> str:
    lines = [s["title"], ""]
    for b in s["beats"][1:-1]:
        bits = [b["title"]] + [f"{k} {v}" for k, v in b.get("rows") or [] if k in ("장소", "기간")]
        if b.get("big"):
            bits.append(f"{b['bigLabel']} {b['big']}")
        lines.append("· " + " | ".join(x for x in bits if x))
    tags = ["#ARTREND", "#아트렌드", "#미술", "#전시", "#전시추천", TAGS[edition]]
    if s["fmt"] == "artist":
        tags.insert(2, "#" + re.sub(r"\W", "", s["subject"]))
    lines += ["", "정보: 각 미술관·갤러리 공식 페이지, 공개 컬렉션 기록, 언론 보도", "", " ".join(tags)]
    return "\n".join(lines)


def make_one(edition: str, page: dict, day_dir: Path, voice: bool = True) -> Optional[dict]:
    asof = dt.date.fromisoformat(page["date"])
    s = script_for(dict(page, edition=page.get("edition") or edition), recent_subjects(edition, asof))
    if not s:
        return None
    work = day_dir / f".{edition}"
    work.mkdir(parents=True, exist_ok=True)
    spec_beats = []
    for i, b in enumerate(s["beats"]):
        img = fetch_image(b["image_url"]) if b.get("image_url") else None
        audio = work / f"b{i}.aiff"
        secs = narrate(b["say"], audio) if voice and b["say"] else None
        floor = MIN_SECONDS.get(b["layout"], 3.4)
        dur = max(floor, secs + 0.8) if secs else floor + 0.6
        spec_beats.append(dict(layout=b["layout"], image=str(img) if img else None, kicker=b.get("kicker"), title=b["title"],
                               sub=b.get("sub") or None, rows=[list(r) for r in b.get("rows") or []] or None, big=b.get("big"),
                               bigLabel=b.get("bigLabel"), num=b.get("num"), credit=b.get("credit") if img else None,
                               duration=round(dur, 2), audio=str(audio) if secs else None))
    total = sum(b["duration"] for b in spec_beats)
    music = music_bed(total, work / "music.wav", seed=asof.toordinal() + EDITIONS.index(edition))
    out = day_dir / f"{edition}.mp4"
    spec = dict(out=str(out), width=1080, height=1920, fps=30, brand="ARTREND", date=f"{asof.year}.{asof.month}.{asof.day} · {page.get('edition_ko') or edition}",
                music=str(music), musicVolume=MUSIC_VOLUME, beats=spec_beats)
    (work / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run([str(renderer()), "shorts", str(work / "spec.json")], check=True, capture_output=True, timeout=1800)
    shutil.rmtree(work, ignore_errors=True)
    credits = sorted({b["credit"].replace("이미지: ", "") for b in spec_beats if b.get("credit") and b["credit"].startswith("이미지")})
    meta = dict(edition=edition, date=page["date"], file=f"{edition}.mp4", title=s["title"], subject=s["subject"], format=s["fmt"],
                kind="artist" if s["fmt"] == "artist" else "roundup", seconds=round(total, 1),
                script=[b["say"] for b in s["beats"]], caption=caption_for(s, edition),
                image_credit=", ".join(credits) or None, sources=[u for u in s["sources"] if u][:6], publishable=False)
    (day_dir / f"{edition}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def publish_to_web(asof: dt.date, metas: List[dict]) -> None:
    """Copy the videos into the localhost app (public/shorts/<date>/) and keep an index of the last KEEP_DAYS days."""
    dst = WEB_PUBLIC / asof.isoformat()
    dst.mkdir(parents=True, exist_ok=True)
    for m in metas:
        shutil.copy2(OUT / asof.isoformat() / m["file"], dst / m["file"])
    keep = {(asof - dt.timedelta(days=i)).isoformat() for i in range(KEEP_DAYS)}
    for d in WEB_PUBLIC.iterdir():
        if d.is_dir() and d.name not in keep:
            shutil.rmtree(d, ignore_errors=True)
    index = []
    for d in sorted((x for x in OUT.iterdir() if x.is_dir() and x.name in keep), reverse=True):
        for f in sorted(d.glob("*.json"), key=lambda f: EDITIONS.index(f.stem) if f.stem in EDITIONS else 9):
            m = json.loads(f.read_text(encoding="utf-8"))
            if (WEB_PUBLIC / d.name / m["file"]).exists():
                index.append(dict(m, src=f"/shorts/{d.name}/{m['file']}"))
    (FEED / "shorts.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


def make(asof: dt.date, editions=EDITIONS, voice: bool = True) -> List[dict]:
    day_dir = OUT / asof.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    metas = []
    for e in editions:
        f = FEED / asof.isoformat() / f"{e}.json"
        if not f.exists():
            continue
        try:
            m = make_one(e, json.loads(f.read_text(encoding="utf-8")), day_dir, voice)
        except subprocess.CalledProcessError as err:
            print(json.dumps(dict(edition=e, error=(err.stderr or b"").decode(errors="replace")[-400:]), ensure_ascii=False))
            continue
        if m:
            metas.append(m)
    publish_to_web(asof, metas)
    return metas


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="render today's ARTREND shorts")
    ap.add_argument("--asof", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--editions", default=",".join(EDITIONS))
    ap.add_argument("--no-voice", action="store_true")
    a = ap.parse_args(argv)
    for m in make(a.asof, [e.strip() for e in a.editions.split(",") if e.strip()], voice=not a.no_voice):
        print(json.dumps(dict(edition=m["edition"], format=m["format"], title=m["title"], seconds=m["seconds"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
