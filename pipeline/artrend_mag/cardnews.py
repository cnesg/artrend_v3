"""Daily ARTREND card news: an Instagram-style carousel (1080x1350 PNG slides) per edition.

Every slide comes from a different kind of material so one set reads like a magazine spread, not one story told six
times: today's insight, a show to see before it peaks, an artist, an institution's own announcement, a rookie or prize,
a news story, a fair or biennale, a gallery opening. No two slides share a subject, a subject shown in the last few days
is skipped when a fresh one exists, and the artist on today's short is left to the video.

Rendered by the bundled Swift renderer (artrend_mag/render.swift, `cards` mode). Images are the institutions' official
images already listed in the feed (internal review only; publishable=false).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from . import shorts

FEED = shorts.FEED
OUT = shorts.ROOT / "outputs" / "cardnews"
WEB_PUBLIC = shorts.ROOT / "outputs" / "artrend-web" / "public" / "cardnews"
EDITIONS = shorts.EDITIONS
KEEP_DAYS = 7
AVOID_DAYS = 3
MAX_ITEMS = 7
ED_KO = {"KR": "한국", "JP": "일본", "AMERICAS": "미주", "EUROPE": "유럽"}


def clean(text: Optional[str]) -> str:
    t = re.sub(r"\[([^\]]+)\]\((?:https?:[^)]+)\)", r"\1", text or "")  # markdown links -> label
    return re.sub(r"\s+", " ", t).strip()


def md(iso: Optional[str]) -> str:
    return shorts.md(iso) or ""


def period(start: Optional[str], end: Optional[str]) -> str:
    a, b = md(start), md(end)
    return f"{a}–{b}" if a and b else (f"{a}부터" if a else (f"{b}까지" if b else ""))


def norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", (s or "").lower())[:24]


# -- one builder per kind of material; each yields candidate slides (best first)
def from_headlines(p: dict) -> Iterable[dict]:
    heads = [p["headlines"][i] for i in (p.get("top") or {}).get("hero", []) if i < len(p["headlines"])] or p.get("headlines") or []
    for h in heads:
        body = [clean(x) for x in (h.get("points") or [])][:2] + [clean(x) for x in (h.get("what") or [])][:2]
        yield dict(kicker="인사이트", title=clean(h["title"]), body=[clean(h.get("dek"))] + body, image=h.get("image"),
                   keys=[h["title"]], foot="ARTREND 자동 판단 · 전시·수상·비평·뉴스 데이터")


def from_early(p: dict) -> Iterable[dict]:
    for e in p.get("early") or []:
        where = " · ".join(x for x in [e.get("venue"), shorts.place(e.get("city")), period(e.get("start"), e.get("end"))] if x)
        yield dict(kicker=f"먼저 가볼 곳 · {e['level']}", title=f"《{shorts.short(e['title'], 40)}》", body=[where, e["status"]] + e["reasons"][:2],
                   image=e.get("image"), keys=[e["title"], e.get("venue") or ""] + list(e.get("artists") or [])[:3], foot=f"이미지·정보: {e.get('venue')} 공식 페이지")


def from_artists(p: dict, skip: set) -> Iterable[dict]:
    for a in p.get("artists") or []:
        if a["name"] in skip or not a.get("summary"):
            continue
        yield dict(kicker="작가 · " + " · ".join(a.get("cats") or []), title=a["name"], body=a["summary"][:4], image=a.get("image"),
                   keys=[a["name"]], foot="전시 정보와 기사 기준")


def from_official(p: dict) -> Iterable[dict]:
    for o in sorted(p.get("official") or [], key=lambda o: -o.get("weight", 1)):
        yield dict(kicker="기관 발표", title=clean(o.get("title_ko") or o["title"]), body=[f"{o['org']} 공식 발표", md(o.get("date"))],
                   image=None, keys=[o["title"]], foot=f"출처: {o['org']} 공식 소식")


def from_rookie(p: dict) -> Iterable[dict]:
    rk = p.get("rookie") or {}
    for r in [x for x in rk.get("people") or [] if x.get("watch")]:
        body = [r["award"], f"상의 무게 {r['weight']['level']} — " + "; ".join(x.split(" +")[0] for x in r["weight"]["reasons"][:2])]
        body += [f"왜: {r['why']}"] if len(r.get("why") or "") > 10 else []
        body += [c["detail"] for c in r.get("checks") or [] if c.get("ok") is True and c.get("detail")][:1]
        yield dict(kicker=f"신진 · {r['status']}", title=r["name"], body=body, image=None, keys=[r["name"]], foot="공식 선정·초기 경력·후속 지원 확인")
    for a in rk.get("awards") or []:
        winners = ", ".join(a.get("winners") or []) or "명단 확인 중"
        yield dict(kicker="수상·선정", title=a["award"], body=[f"수상: {winners}", f"주최: {a.get('organizer') or ''}".strip(" :"),
                                                              f"상의 무게 {a['weight']['level']} — " + "; ".join(r.split(" +")[0] for r in a["weight"]["reasons"][:2])],
                   image=None, keys=[a["award"]] + list(a.get("winners") or []), foot="공식 발표·보도 기준")


def from_news(p: dict) -> Iterable[dict]:
    for s in [x for x in p.get("stories") or [] if not x.get("short")]:
        if len(clean(s.get("title_ko") or s["title"])) > 64:
            continue  # long machine-translated headlines read badly on a card
        body = [b.lstrip("→ ").strip() for b in (s.get("bullets") or [])][:3]
        yield dict(kicker=f"뉴스 · {s['topic']}", title=clean(s.get("title_ko") or s["title"]), body=body or [clean(s.get("lead"))],
                   image=None, keys=[s["title"]], foot=f"출처: {s['outlet']}" + (f" 외 {s['n_outlets'] - 1}곳" if s["n_outlets"] > 1 else ""))


def from_fairs(p: dict) -> Iterable[dict]:
    for f in [x for x in p.get("fairs") or [] if x.get("status") != "종료"]:
        when = f"폐막 D-{f['d_day']}" if f["status"] == "진행 중" else f"개막 D-{f['d_day']}"
        yield dict(kicker=f"페어·비엔날레 · {when}", title=shorts.short(f["title"], 44),
                   body=[" · ".join(x for x in [shorts.place(f.get("city")), period(f.get("start"), f.get("end"))] if x),
                         f"참여 작가: {', '.join(f['artists'][:4])}" if f.get("artists") else ""],
                   image=f.get("image"), keys=[f["title"]], foot="주최 측 공식 정보 기준")


def from_market(p: dict) -> Iterable[dict]:
    for s in [x for x in p.get("news_week") or [] if x.get("topic") == "시장·경매·아트페어"]:
        t = clean(s.get("title_ko") or s["title"])
        if len(t) > 64:
            continue
        yield dict(kicker="시장 소식", title=t, body=[f"{(s.get('sources') or [{}])[0].get('outlet', '')} · {md(s.get('date'))}"]
                   + ([f"{s['n_outlets']}곳이 같은 소식을 실었다"] if s.get("n_outlets", 1) > 1 else []),
                   image=None, keys=[s["title"]], foot="보도 기준")


def from_galleries(p: dict) -> Iterable[dict]:
    for g in ((p.get("galleries") or {}).get("openings") or []):
        yield dict(kicker="갤러리 새 전시", title=f"《{shorts.short(g['title'], 40)}》",
                   body=[g["venue"], period(g.get("start"), g.get("end")), ", ".join(g.get("artists") or [])[:60]],
                   image=g.get("image"), keys=[g["title"], g["venue"]] + list(g.get("artists") or [])[:3], foot=f"이미지·정보: {g['venue']} 공식 페이지")


def recent_keys(edition: str, asof: dt.date) -> set:
    seen = set()
    for i in range(1, AVOID_DAYS + 1):
        f = OUT / (asof - dt.timedelta(days=i)).isoformat() / f"{edition}.json"
        if f.exists():
            for s in json.loads(f.read_text(encoding="utf-8")).get("slides", []):
                seen.update(norm(k) for k in s.get("keys") or [])
    return seen


# A weekly series: each weekday leads with one kind of material (3-4 slides), the rest of the set stays mixed.
# (key, series name, cover kicker, cover title, builder name)
SERIES = {
    0: ("rookie", "ROOKIE MONDAY", "월요일 · 신진", "이번 주 지켜볼 신진", "rookie"),
    1: ("gallery", "GALLERY TUESDAY", "화요일 · 갤러리", "갤러리가 지금 거는 전시", "galleries"),
    2: ("official", "MUSEUM WEDNESDAY", "수요일 · 기관 발표", "미술관·갤러리가 직접 발표한 것", "official"),
    3: ("artist", "ARTIST THURSDAY", "목요일 · 작가", "지금 이름이 오르는 작가", "artists"),
    4: ("weekend", "WEEKEND FRIDAY", "금요일 · 주말 전시", "이번 주말, 붐비기 전에 갈 곳", "early"),
    5: ("fair", "FAIR SATURDAY", "토요일 · 페어·비엔날레", "페어·비엔날레·시장 소식", "fairs"),
    6: ("week", "WEEKLY SUNDAY", "일요일 · 한 주 정리", "이번 주 미술 흐름 정리", "headlines"),
}
THEME_MIN, THEME_MAX = 2, 4


def series_of(day: dt.date) -> dict:
    key, name, kicker, title, builder = SERIES[day.weekday()]
    return dict(key=key, name=name, kicker=kicker, title=title, builder=builder)


def plan(p: dict, recent: set, short_subject: Optional[str], series: Optional[dict] = None) -> List[dict]:
    """Cover, then today's series (3-4 slides of one kind) when there is enough material, then one slide per other kind;
    never repeating a subject."""
    used: set = set()

    def take(gen: Iterable[dict]) -> Optional[dict]:
        def clash(c):
            ks = [norm(k) for k in c["keys"] if norm(k)]
            return any(k in used or any(len(u) >= 6 and (u in k or k in u) for u in used) for k in ks)
        cands = [c for c in gen if c["title"] and not clash(c)]
        fresh = [c for c in cands if not any(norm(k) in recent for k in c["keys"] if norm(k))]
        c = (fresh or cands or [None])[0]
        if c:
            used.update(norm(k) for k in c["keys"] if norm(k))
        return c

    skip_artist = {short_subject} if short_subject else set()
    builders: List[Callable[[], Iterable[dict]]] = [
        lambda: from_early(p), lambda: from_artists(p, skip_artist), lambda: from_official(p), lambda: from_news(p),
        lambda: from_rookie(p), lambda: from_fairs(p), lambda: from_galleries(p), lambda: from_headlines(p)]
    named = dict(rookie=lambda: from_rookie(p), galleries=lambda: from_galleries(p), official=lambda: from_official(p),
                 artists=lambda: from_artists(p, skip_artist), early=lambda: from_early(p), fairs=lambda: list(from_fairs(p)) + list(from_market(p)),
                 headlines=lambda: from_headlines(p))
    themed: List[dict] = []
    if series:
        snapshot = set(used)
        while len(themed) < THEME_MAX:
            c = take(named[series["builder"]]())
            if not c:
                break
            themed.append(c)
        if len(themed) < THEME_MIN:  # not enough material today: plain mixed set, no series label
            used.clear(); used.update(snapshot); themed, series = [], None
    if series:
        lead = themed[0]
        cover = dict(kicker=series["kicker"], title=series["title"], keys=[],
                     body=[f"{series['name']} · {len(themed)}장", lead["title"]], image=next((c["image"] for c in themed if c.get("image")), None),
                     foot="ARTREND 요일 시리즈 · 매주 같은 요일에 같은 주제")
        named["news"] = lambda: from_news(p)
        order = ["early", "artists", "official", "news", "rookie", "fairs", "galleries", "headlines"]
        rest_builders = [named[k] for k in order if k != series["builder"]]
        rest = [c for c in (take(b()) for b in rest_builders) if c][: max(0, MAX_ITEMS - len(themed))]
        items = themed + rest
    else:
        cover = take(from_headlines(p)) or take(from_early(p))
        if not cover:
            return []
        items = [c for c in (take(b()) for b in builders) if c][:MAX_ITEMS]
    if not cover.get("image"):
        cover["image"] = next((c["image"] for c in items[1:] + items[:1] if c.get("image")), None)
    return [dict(cover, kind="cover")] + [dict(c, kind="item", num=f"{i:02d}") for i, c in enumerate(items, 1)]


def make_one(edition: str, p: dict, day_dir: Path) -> Optional[dict]:
    asof = dt.date.fromisoformat(p["date"])
    short_meta = shorts.OUT / p["date"] / f"{edition}.json"
    short_subject = json.loads(short_meta.read_text(encoding="utf-8")).get("subject") if short_meta.exists() else None
    series = series_of(asof)
    slides = plan(p, recent_keys(edition, asof), short_subject, series)
    series_used = slides[0].get("kicker") == series["kicker"] if slides else False
    if not slides:
        return None
    kws = [k["label"] for k in p.get("keywords") or []][:8]
    slides.append(dict(kind="end", title="오늘의 미술 트렌드", chips=kws, keys=[],
                       body=["이미지: 각 기관 공식 페이지 · 내부 검토용", f"{p['date'].replace('-', '.')} · {ED_KO[edition]}판"]))
    out_dir = day_dir / edition
    shutil.rmtree(out_dir, ignore_errors=True)
    spec_slides = []
    for s in slides:
        img = shorts.fetch_image(s["image"]) if s.get("image") else None
        spec_slides.append(dict(kind=s["kind"], image=str(img) if img else None, kicker=s.get("kicker"), title=s["title"],
                                body=[b for b in s.get("body") or [] if b], chips=s.get("chips"), foot=s.get("foot"), num=s.get("num")))
    spec = dict(outDir=str(out_dir), width=1080, height=1350, brand="ARTREND", date=f"{p['date'].replace('-', '.')} {ED_KO[edition]}",
                slides=spec_slides)
    spec_path = day_dir / f".{edition}.cards.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run([str(shorts.renderer()), "cards", str(spec_path)], check=True, capture_output=True, timeout=600)
    spec_path.unlink()
    caption = "\n".join([f"[ARTREND {ED_KO[edition]}판 {p['date'].replace('-', '.')}" + (f" · {series['name']}" if series_used else "")
                         + f"] {slides[0]['title']}", ""]
                        + [f"{s['num']} {s['title']}" for s in slides if s["kind"] == "item"]
                        + ["", " ".join(f"#{re.sub(r'[^0-9A-Za-z가-힣]', '', k)}" for k in kws[:5]) + " #ARTREND #미술 #전시"])
    meta = dict(edition=edition, date=p["date"], dir=edition, series=series["name"] if series_used else None, files=[f"{i:02d}.png" for i in range(1, len(slides) + 1)],
                slides=[dict(kind=s["kind"], kicker=s.get("kicker"), title=s["title"], body=s.get("body"), keys=s.get("keys"), foot=s.get("foot"))
                        for s in slides],
                caption=caption, publishable=False)
    (day_dir / f"{edition}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


def publish_to_web(asof: dt.date) -> None:
    keep = {(asof - dt.timedelta(days=i)).isoformat() for i in range(KEEP_DAYS)}
    WEB_PUBLIC.mkdir(parents=True, exist_ok=True)
    for d in WEB_PUBLIC.iterdir():
        if d.is_dir() and d.name not in keep:
            shutil.rmtree(d, ignore_errors=True)
    index = []
    for d in sorted((x for x in OUT.iterdir() if x.is_dir() and x.name in keep), reverse=True):
        for e in EDITIONS:
            f = d / f"{e}.json"
            if not f.exists():
                continue
            m = json.loads(f.read_text(encoding="utf-8"))
            dst = WEB_PUBLIC / d.name / e
            if d.name == asof.isoformat() or not dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(d / e, dst)
            index.append(dict(m, srcs=[f"/cardnews/{d.name}/{e}/{x}" for x in m["files"]]))
    (FEED / "cardnews.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


def make(asof: dt.date, editions=EDITIONS) -> List[dict]:
    day_dir = OUT / asof.isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    metas = []
    for e in editions:
        f = FEED / asof.isoformat() / f"{e}.json"
        if not f.exists():
            continue
        try:
            m = make_one(e, json.loads(f.read_text(encoding="utf-8")), day_dir)
        except subprocess.CalledProcessError as err:
            print(json.dumps(dict(edition=e, error=(err.stderr or b"").decode(errors="replace")[-400:]), ensure_ascii=False))
            continue
        if m:
            metas.append(m)
    publish_to_web(asof)
    return metas


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="render today's ARTREND card news")
    ap.add_argument("--asof", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--editions", default=",".join(EDITIONS))
    a = ap.parse_args(argv)
    for m in make(a.asof, [e.strip() for e in a.editions.split(",") if e.strip()]):
        print(json.dumps(dict(edition=m["edition"], slides=len(m["files"]), kinds=[s["kicker"] for s in m["slides"][1:-1]]), ensure_ascii=False))


if __name__ == "__main__":
    main()
