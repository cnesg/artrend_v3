"""The web pages, as Obsidian notes: one note per edition and day, written from the same JSON the site reads, so the
vault shows exactly what a reader sees (keywords, why-now reasons, artist stories, gallery and market news, Rookie
Radar, criticism). Written by `cli web` after every export and by `cli vault` after every rebuild."""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from .obsidian_vault import EDITION_KO, WORK_ROOT

FOLDER = "00_오늘의 화면"
EDITIONS = ("KR", "JP", "AMERICAS", "EUROPE")
WEB_DATA = WORK_ROOT / "outputs" / "web_data"
VAULT = WORK_ROOT / "outputs" / "ARTREND_Obsidian_Vault"
MARKET = "시장·경매·아트페어"


def esc(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(s or "")).replace("[", "(").replace("]", ")").replace("|", "/").strip()


def link(title: Optional[str], url: Optional[str]) -> str:
    t = esc(title) or "제목 없음"
    return f"[{t}]({url})" if url else t


def period(a: Optional[str], b: Optional[str]) -> str:
    return " – ".join(x for x in (a, b) if x)


def title_of(r: dict) -> str:
    ko = r.get("title_ko")
    return f"{esc(ko)} ({esc(r.get('title'))})" if ko and ko != r.get("title") else esc(r.get("title"))


def section(lines: List[str], head: str, body: List[str], empty: str = "이번 화면에는 없음") -> None:
    lines += ["", f"## {head}", ""] + (body or [f"- {empty}"])


def render(p: dict) -> str:
    ed, d = p["edition"], p["date"]
    L = ["---", f"type: web_page", f"edition: {ed}", f"date: {d}", "publishable: false", "---",
         f"# {EDITION_KO[ed]}판 · {d}", "", "웹 화면과 같은 데이터로 만든 노트다. 내부 검토용이며 공개하지 않는다."]

    section(L, "키워드", [f"{i}. **{esc(k['label'])}** · {esc(k.get('note'))}"
                          + (f" — {esc(k['why'][0])}" if k.get("why") else "")
                          + (f"\n    - {esc(k['why'][1])}" if len(k.get("why") or []) > 1 else "")
                          for i, k in enumerate(p.get("keywords") or [], 1)])

    top = p.get("top") or {}
    section(L, "지금 뜨는 것", [f"{i}. {link(t['title'], t.get('url'))} · {esc(t.get('reason'))} · {esc(t.get('ago'))}"
                               for i, t in enumerate(top.get("trending") or [], 1)])

    br = p.get("briefing") or {}
    section(L, "오늘의 인사이트", [f"- {esc(x)}" for x in br.get("insights") or []])

    section(L, "헤드라인", [f"- **{esc(h['title'])}** ({esc(h.get('axis'))})" + (f"\n    - {esc(h['dek'])}" if h.get("dek") else "")
                            + "".join(f"\n    - {esc(x)}" for x in h.get("points") or [])
                            for h in p.get("headlines") or []])

    stories = p.get("stories") or []
    main = [s for s in stories if not s.get("short")]
    body = []
    for s in main:
        body.append(f"{s.get('rank')}. **{link(title_of(s), s.get('url'))}** · {esc(s.get('topic'))} · {s.get('n_outlets')}개 매체 · {s.get('date')}")
        body += [f"    - {esc(b)}" for b in s.get("bullets") or []]
        if s.get("so_what") and not any(s["so_what"] in b for b in s.get("bullets") or []):
            body.append(f"    - 의미: {esc(s['so_what'])}")
        others = [link(x.get("outlet"), x.get("url")) for x in (s.get("sources") or [])[1:6]]
        if others:
            body.append(f"    - 같은 소식: {', '.join(others)}")
    section(L, "주요 소식", body)
    section(L, "짧은 소식", [f"- {link(title_of(s), s.get('url'))} · {s.get('date')}" for s in stories if s.get("short")])

    body = []
    for a in p.get("artists") or []:
        why = a.get("why") or []
        body.append(f"### {esc(a['name'])}" + (f" · {esc(why[0])}" if why else ""))
        body += [x for x in (esc(a.get("profile")) and f"- {esc(a['profile'])}", a.get("record") and f"- 기록 · {esc(a['record'])}") if x]
        body += [f"- {esc(x)}" for x in a.get("summary") or []]
        for sh in a.get("shows") or []:
            body.append(f"- 전시: {link(sh.get('title'), sh.get('url'))} · {esc(sh.get('venue'))} · {period(sh.get('start'), sh.get('end'))}")
        for c in a.get("career") or []:
            body.append("- 이력: " + " · ".join(esc(c.get(k)) for k in ("year", "kind", "title", "venue") if c.get(k)))
        for pr in (a.get("press") or [])[:4]:
            body.append(f"- 보도: {link(pr.get('title_ko') or pr.get('title'), pr.get('url'))}" + (f" — {esc(pr['excerpt'])}" if pr.get("excerpt") else ""))
        body.append("")
    section(L, "작가 스토리", body)

    section(L, "EARLY SIGNAL", [f"- **{link(e['title'], e.get('url'))}** · {esc(e.get('venue'))} · {esc(e.get('status'))} · {period(e.get('start'), e.get('end'))}"
                                + (f"\n    - {esc(e['why'][0])}" if e.get("why") else "")
                                + "".join(f"\n    - {esc(r)}" for r in e.get("reasons") or [])
                                for e in p.get("early") or []])

    ex = p.get("exhibitions") or {}
    show = lambda e: f"- {link(e['title'], e.get('url'))} · {esc(e.get('venue'))} · {period(e.get('start'), e.get('end'))}" + (f" · {esc(e['why'])}" if isinstance(e.get("why"), str) else "")
    section(L, f"전시 · 주목 (열려 있는 전시 {ex.get('open_count', 0)}개)", [show(e) for e in ex.get("featured") or []])
    section(L, "전시 · 이번 주 개막", [show(e) for e in ex.get("opened") or []])
    section(L, "전시 · 개막 예정", [show(e) for e in ex.get("upcoming") or []])

    g = p.get("galleries") or {}
    ga = g.get("all") or {}
    section(L, "갤러리 · 개막", [show(e) for e in ga.get("openings") or g.get("openings") or []])
    section(L, "갤러리 · 소식 (최근 14일)", [f"- {n.get('date')} · {esc(n.get('source'))} · {link(n['title'], n.get('url'))}"
                                         for n in ga.get("news") or g.get("news") or []])
    section(L, "기관 공식 소식", [f"- {o.get('date')} · {esc(o.get('org'))} · {link(o.get('title_ko') or o['title'], o.get('url'))}"
                               for o in p.get("official") or []])

    section(L, "시장 · 경매 · 아트페어 소식", [f"- {r.get('date')} · {link(title_of(r), r.get('url'))} · {r.get('n_outlets')}개 매체"
                                         for r in p.get("news_week") or [] if r.get("topic") == MARKET])
    section(L, "페어 · 비엔날레 (60일)", [f"- {esc(f.get('status'))} · **{link(f['title'], f.get('url'))}** · {period(f.get('start'), f.get('end'))} {esc(f.get('city'))}"
                                     for f in p.get("fairs") or []])

    rk = p.get("rookie") or {}
    body = []
    for r in rk.get("people") or []:
        body.append(f"- **{esc(r['name'])}** · {esc(r.get('award'))} · {esc(r.get('status'))}")
        body += [f"    - {esc(x)}" for x in r.get("points") or []]
    section(L, "ROOKIE RADAR", body)
    section(L, "올해의 상·선정", [f"- {esc(a.get('award'))} · {esc(a.get('organizer'))} · {', '.join(a.get('winners') or []) or '—'}"
                               for a in rk.get("awards") or []])

    cr = p.get("critique") or {}
    section(L, f"비평 · 리뷰 (최근 {cr.get('days', 14)}일)", [f"- {r.get('date')} · {esc(r.get('outlet'))} · {link(r.get('title_ko') or r['title'], r.get('url'))}"
                                                        + (f" · {esc(r['author'])}" if r.get("author") else "")
                                                        for r in cr.get("recent") or p.get("criticism") or []])

    section(L, "이번 주 전체 소식", [f"- {r.get('date')} · {esc(r.get('topic'))} · {link(title_of(r), r.get('url'))}"
                                  for r in p.get("news_week") or []])
    return "\n".join(L) + "\n"


def write(web_data: Path = WEB_DATA, vault: Path = VAULT) -> Dict[str, int]:
    if not vault.exists() or not web_data.exists():
        return {"웹 화면 노트": 0}
    out = vault / FOLDER
    n, index = 0, ["# 오늘의 화면", "", "웹 화면과 같은 내용의 노트. 날짜를 고르면 판별 페이지가 열린다.", ""]
    days = sorted((x.name for x in web_data.iterdir() if x.is_dir() and re.fullmatch(r"\d{4}-\d\d-\d\d", x.name)), reverse=True)
    for d in days:
        cells = []
        for ed in EDITIONS:
            src = web_data / d / f"{ed}.json"
            if not src.exists():
                continue
            name = f"{d} {EDITION_KO[ed]} 화면"
            (out / d).mkdir(parents=True, exist_ok=True)
            (out / d / f"{name}.md").write_text(render(json.loads(src.read_text(encoding="utf-8"))), encoding="utf-8")
            cells.append(f"[[{name}|{EDITION_KO[ed]}]]")
            n += 1
        index.append(f"- {d} · " + " · ".join(cells))
    for old in out.iterdir() if out.exists() else []:  # days no longer exported
        if old.is_dir() and old.name not in days:
            for f in old.iterdir():
                f.unlink()
            old.rmdir()
    out.mkdir(parents=True, exist_ok=True)
    (out / "오늘의 화면.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return {"웹 화면 노트": n}
