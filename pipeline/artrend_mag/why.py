"""Why something is trending, said as a cause rather than a count.

A count ("이번 주 3건") says that people talk; the reader wants to know what happened: a record at auction,
a retrospective, a prize, an acquisition, a biennale invitation. The cause is read only from the titles of the
evidence already on the page (press, shows, announcements) — nothing is inferred beyond them. When no cause is
named in the evidence, a structural reason is given (a museum solo show, a fair week, a closing date), never a
made-up one. Price stays a market signal; it is described as such, not as artistic worth.
"""
import re
from typing import Iterable, List, Optional, Tuple

Reason = Tuple[str, str]  # (short label for a chip/kicker, one-line explanation)

# strongest cause first; on a tie in how many titles name it, the earlier one wins
DRIVERS: List[Tuple[re.Pattern, str, str]] = [
    (re.compile(r"별세|타계|작고|추모|영면|passed away|dies at|\bdied\b|obituary|逝去|死去", re.I),
     "작고 후 재조명", "작가가 세상을 떠난 뒤 작품과 미술사적 의미를 다시 짚는 글과 전시가 이어진다"),
    (re.compile(r"최고가|신기록|경매 기록|낙찰|억\s?원에|record price|auction record|sold for|hammer|落札", re.I),
     "경매 기록", "경매에서 새 가격 기록이 나왔다. 시장의 평가가 달라지고 있다는 뜻이지만, 가격이 곧 작품의 가치는 아니다"),
    (re.compile(r"회고전|retrospective|回顧展", re.I),
     "대규모 회고전", "그동안의 작업을 한자리에 모은 회고전이 열렸다. 작가를 다시 평가하는 계기가 된다"),
    (re.compile(r"수상|대상(?:을| 수상|에 선정)|상을 받|최종 후보|선정작가|공모전?\s?선정|선정됐|prize|award|winner|shortlist|受賞", re.I),
     "수상·선정", "상을 받거나 공모에 뽑혔다. 다음 전시나 미술관 소장으로 이어지는 경우가 많다"),
    (re.compile(r"소장(?:품|작|했|하기로|\s?결정)|기증|acqui|donat|gift of|収蔵|寄贈", re.I),
     "미술관 소장", "미술관이 작품을 소장품으로 들였거나 소장품전에서 다시 꺼냈다. 기관이 작품의 가치를 인정했다는 뜻이다"),
    (re.compile(r"비엔날레|트리엔날레|biennale|biennial|triennale|triennial|ビエンナーレ|トリエンナーレ", re.I),
     "비엔날레", "비엔날레에 참여한다. 해외 큐레이터와 관객에게 작업을 알릴 기회다"),
    (re.compile(r"해외|국제 무대|공동기획|뉴욕|런던|파리|베를린|상파울루|MoMA|모마|테이트|퐁피두|구겐하임|루브르"), "해외 기관 진출",
     "해외 주요 기관과 함께 전시를 연다. 해외에서도 이름이 알려지는 단계다"),
    (re.compile(r"전속|represent(?:ation|s)?\b|joins .*gallery|所属", re.I),
     "갤러리 전속", "갤러리와 전속 계약을 맺었다. 시장에서 작가의 입지가 커진다"),
    (re.compile(r"아트페어|art fair|\bfair\b|フェア|완판|sold out", re.I),
     "아트페어", "아트페어에 나왔거나 작품이 팔렸다. 컬렉터들의 관심이 모이고 있다"),
    (re.compile(r"개관|재개관|opens? (?:its |a )?new|new (?:museum|space|gallery)|開館", re.I),
     "새 공간 개관", "새 미술관이나 전시 공간이 문을 열었다. 그 지역에서 볼 수 있는 전시가 달라진다"),
    (re.compile(r"협업|콜라보|컬래버|collaborat|브랜드|팝업", re.I),
     "브랜드 협업", "미술 밖 브랜드와 협업했다. 미술관에 오지 않던 사람들에게도 알려진다"),
    (re.compile(r"국내 첫|첫 개인전|첫 국내|최초|first solo|初個展|初の個展", re.I),
     "첫 소개", "처음 소개되는 작업이다. 새로운 관객이 작가를 알게 된다"),
    (re.compile(r"개인전|solo (?:show|exhibition)|個展", re.I),
     "개인전", "작가의 작업을 한자리에서 볼 수 있는 개인전이 열렸다"),
]

# what a concept on the strip means when it rises — a reading, not a count
CONCEPT_WHY = {
    "회고전": "작가의 작업을 돌아보는 회고전이 잇따른다. 작가를 재평가하는 흐름이다",
    "소장품": "미술관들이 소장품을 다시 꺼내 보여주고 있다. 가진 컬렉션을 새롭게 읽으려는 움직임이다",
    "기증": "작품 기증이 이어지고 있다. 미술관 컬렉션이 커지고, 작가의 미술사적 자리도 단단해진다",
    "경매": "경매 출품과 낙찰 소식이 몰렸다. 시장 가격이 다시 매겨지고 있지만, 가격이 곧 작품의 가치는 아니다",
    "아트페어": "페어 시즌이다. 갤러리와 컬렉터의 거래가 한 주에 몰린다",
    "비엔날레": "비엔날레 시즌이다. 어떤 작가가 국제 무대에 서는지 가려지는 시기다",
    "레지던시": "레지던시 선발과 결과 발표가 이어진다. 다음 세대 작가가 드러나는 단계다",
    "신진": "신진 작가 공모와 수상 결과가 나오는 시기다. 새 이름이 처음 알려진다",
    "전속 계약": "갤러리 전속 계약 소식이 있다. 시장에서 작가의 입지가 커진다",
    "신규 개관": "새 미술관과 갤러리가 문을 연다. 볼 수 있는 전시의 판도가 바뀐다",
    "휴관·폐관": "문을 닫거나 쉬는 기관이 있다. 그만큼 볼 수 있는 전시가 줄어든다",
    "기관장 인사": "기관장이 바뀐다. 그 기관의 다음 전시와 소장 방향도 달라질 수 있다",
    "예산·지원": "예산과 지원 제도가 바뀐다. 기관 프로그램의 규모가 달라진다",
}
KIND_WHY = {
    "매체": ("{l} 전시 잇따름", "여러 미술관과 갤러리가 비슷한 시기에 {l} 작업을 선보이고 있다"),
    "주제": ("전시·비평이 함께 다룸", "전시와 전문지가 같은 주에 함께 다룬 주제다. 작가들의 관심이 이쪽으로 모이고 있다"),
    "형식": ("{l} 소식 몰림", "{l} 관련 소식이 이번 주에 몰렸다"),
}
FAIR = re.compile(r"페어|fair|フェア|アートウィーク|art week|아트위크|Art Collaboration", re.I)
BIENNALE = re.compile(r"비엔날레|트리엔날레|biennale|biennial|triennale|ビエンナーレ|トリエンナーレ", re.I)


ABROAD = "해외 기관 진출"
WEAK = ("첫 소개", "개인전")  # read from the Korean desk's side: a London show is not 'abroad' for the Europe edition


def driver(texts: Iterable[str], edition: Optional[str] = None) -> Optional[Reason]:
    """The cause most of the evidence names; ties go to the stronger cause."""
    texts = [t for t in texts if t]
    best, best_n = None, 0
    for rx, short, long in DRIVERS:
        if short == ABROAD and edition != "KR":
            continue
        n = sum(1 for t in texts if rx.search(t))
        if short in WEAK:  # a plain solo show or debut names a format, not a cause: any real cause outranks it
            n = min(n, 1) * 0.5
        if n > best_n:
            best, best_n = (short, long), n
    return best


def _titles(items) -> List[str]:
    return [(x.get("title") if isinstance(x, dict) else x) or "" for x in items or []]


def _solo(name: str, title: str) -> bool:
    last = (name or "").split()[-1:] or [""]
    return bool(name) and (name in title or (len(last[0]) >= 3 and last[0] in title))


def artist(a: dict, edition: Optional[str] = None) -> Reason:
    found = driver(_titles(a.get("press")) + _titles(a.get("shows")), edition)
    if found and found[0] != "개인전":
        return found
    shows = [s for s in a.get("shows") or [] if isinstance(s, dict)]
    museum = [s for s in shows if s.get("kind") == "museum"]
    solo = [s for s in museum if _solo(a.get("name"), s.get("title") or "")]
    if solo:
        return "미술관 개인전", f"{solo[0].get('venue') or '미술관'}에서 개인전을 연다. 미술관이 작가 한 명에게 전시실을 내준 만큼 작업을 인정받았다는 뜻이다"
    gallery_solo = [s for s in shows if s.get("kind") != "museum" and _solo(a.get("name"), s.get("title") or "")]
    if gallery_solo:
        return "갤러리 개인전", f"{gallery_solo[0].get('venue') or '갤러리'}에서 개인전을 연다. 컬렉터에게 신작을 선보이는 자리다"
    if museum:
        return "미술관 기획전 초대", f"{museum[0].get('venue') or '미술관'} 기획전에 참여한다. 미술관이 주목하는 작가라는 뜻이다"
    if found:
        return found
    if shows and all(s.get("status") == "개막 예정" for s in shows):
        return "곧 개막", "곧 전시가 열린다. 개막 전에 미리 알아둘 만한 이름이다"
    if shows or "전시 중" in (a.get("cats") or []) or "개인전" in (a.get("cats") or []):
        return "전시 중", "지금 전시를 볼 수 있고, 관련 기사도 이어지고 있다"
    return "보도 집중", "이번 주 여러 매체가 이 작가를 다뤘다"


def show(e: dict, edition: Optional[str] = None) -> Reason:
    found = driver([e.get("title") or ""] + _titles(e.get("press")), edition)
    if found and found[0] != "개인전":
        return found
    status = e.get("status") or ""
    if status.startswith("종료"):
        return "곧 종료", f"전시가 곧 끝난다({status}). 이번 주가 마지막 기회다"
    if "D-" in status:
        return "곧 개막", "곧 개막한다. 관람객이 몰리기 전에 먼저 볼 수 있다"
    if len(e.get("artists") or []) == 1:
        return "개인전", "한 작가의 작업만으로 꾸민 전시라 작업 세계를 깊이 볼 수 있다"
    if found:
        return found
    return "기획전", "하나의 주제로 여러 작가를 묶은 기획전이다. 요즘 미술관의 관심사를 보여준다"


def keyword(k: dict, artists: Optional[List[dict]] = None, edition: Optional[str] = None) -> Reason:
    label, kind = k["label"], k.get("kind")
    texts = _titles(k.get("examples"))
    if kind == "작가":
        a = next((a for a in artists or [] if a.get("name") == label), None)
        return artist(a, edition) if a else (driver(texts, edition) or ("보도 집중", "이번 주 여러 매체가 이 작가를 다뤘다"))
    if kind == "전시":
        return driver(texts, edition) or ("지금 뜨는 전시", "개막 뒤 기사가 나오기 시작한 전시다")
    if kind == "행사":
        if FAIR.search(label):
            return "페어 주간", "갤러리와 컬렉터가 한곳에 모이는 주간이라 거래와 신작 공개가 몰린다"
        if BIENNALE.search(label):
            return "비엔날레 개막", "해외 큐레이터와 작가가 모이는 행사다. 참여 작가에게는 중요한 이력이 된다"
        return driver(texts, edition) or ("행사 개막", "이번 주에 열리는 행사라 관심이 모인다")
    if label in CONCEPT_WHY:
        return label, CONCEPT_WHY[label]
    short, long = KIND_WHY.get(kind, ("관심 증가", "이번 주 다루는 곳이 늘었다"))
    short, long = short.format(l=label), long.format(l=label)
    cause = driver(texts, edition)
    if cause and cause[0] not in ("개인전",):
        long += f". 이번 주에는 '{cause[0]}' 소식도 함께 있었다"
    return short, long
