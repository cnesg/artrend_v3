import datetime as dt
import unittest
from unittest import mock

from artrend_mag import shorts


def artist(**kw):
    base = dict(name="김작가", entity_id="ent_x", image="https://x/a.jpg", works=[], press=[],
                shows=[dict(id="evt_1", title="《빛》", venue="서울시립미술관", city="Seoul", start="2026-11-01", end="2027-02-14",
                            status="전시 중", url="https://x/s", image="https://x/a.jpg", artists=["김작가"])])
    base.update(kw)
    return base


def page(**kw):
    base = dict(date="2026-11-10", edition="KR", edition_ko="한국", artists=[], early=[], headlines=[], news_week=[],
                exhibitions=dict(all=dict(open_now=[], upcoming=[], closing=[])))
    base.update(kw)
    return base


def show(i, **kw):
    base = dict(id=f"evt_{i}", title=f"전시{i}", venue=f"미술관{i}", city="Seoul", kind="museum", start="2026-10-01",
                end="2026-12-01", image=f"https://x/{i}.jpg", url=f"https://x/{i}")
    base.update(kw)
    return base


NO_FACTS = mock.patch.object(shorts, "artist_facts", lambda name, eid=None: {})
FACTS = mock.patch.object(shorts, "artist_facts", lambda name, eid=None: dict(born=1946, nationality="세르비아",
                                                                              holdings=[("뉴욕 현대미술관(MoMA)", 56)]))
NO_TR = mock.patch.object(shorts, "title_ko", lambda eid: None)
SHARP = mock.patch.object(shorts, "sharp", lambda url: True)


class ArtistFormatTest(unittest.TestCase):
    def test_profile_carries_facts_exhibition_and_reasons(self):
        a = artist(press=[dict(title="김작가 개인전 개막", url="u", outlet="o", date="2026-11-09", n_outlets=3)])
        p = page(artists=[a], early=[dict(title="빛", reasons=["이번 주 6개 매체가 다뤘다", "지난주보다 보도가 늘고 있다"])])
        with FACTS, NO_TR, SHARP:
            s = shorts.fmt_artist(p, set())
        layouts = [b["layout"] for b in s["beats"]]
        self.assertEqual(layouts[0], "hook")
        self.assertEqual(layouts[-1], "end")
        who = next(b for b in s["beats"] if b["kicker"] == "WHO")
        self.assertEqual(who["big"], "56점")
        self.assertIn("1946년에 태어난 세르비아 작가", who["say"])
        info = next(b for b in s["beats"] if b["layout"] == "info")
        self.assertIn(("기간", "2026.11.1 – 2027.2.14"), info["rows"])
        self.assertIn("2월 14일까지 이어집니다", info["say"])
        why = next(b for b in s["beats"] if b["kicker"] == "WHY NOW")
        self.assertIn("이번 주 언론이 잇따라 다뤘다", why["sub"])

    def test_artist_with_nothing_to_say_yields_the_slot(self):
        a = artist(press=[dict(title="Kim joins a group show", url="u", outlet="o", date="2026-11-09", n_outlets=1)])
        with NO_FACTS, NO_TR, SHARP:
            self.assertIsNone(shorts.fmt_artist(page(artists=[a]), set()))


class RoundupTest(unittest.TestCase):
    def test_closing_skips_same_day_endings_when_there_is_choice_and_one_venue_once(self):
        items = [show(1, end="2026-11-10"), show(2, end="2026-11-12"), show(3, end="2026-11-13", venue="미술관2"),
                 show(4, end="2026-11-14"), show(5, end="2026-11-15"), show(6, end="2026-11-16")]
        got = shorts.roundup_items(page(exhibitions=dict(all=dict(closing=items))), "closing")
        self.assertEqual([e["id"] for e in got], ["evt_2", "evt_4", "evt_5"])

    def test_upcoming_roundup_reads_ordinals_and_dates(self):
        items = [show(i, start=f"2026-11-1{i}", end="2026-12-20") for i in (1, 2, 3)]
        with NO_TR:
            s = shorts.fmt_roundup(page(exhibitions=dict(all=dict(upcoming=items))), "upcoming")
        lists = [b for b in s["beats"] if b["layout"] == "list"]
        self.assertEqual([b["num"] for b in lists], ["01", "02", "03"])
        self.assertTrue(lists[0]["say"].startswith("첫 번째. 서울 미술관1"))
        self.assertEqual(lists[0]["kicker"], "11월 11일 개막 · 내일")

    def test_thin_material_gives_no_roundup(self):
        self.assertIsNone(shorts.fmt_roundup(page(exhibitions=dict(all=dict(upcoming=[show(1, start="2026-11-12")]))), "upcoming"))


class NewsFormatTest(unittest.TestCase):
    def test_filler_topics_and_machine_fragments_are_left_out(self):
        good = [dict(title=f"국립현대미술관 {i}번째 소장품 기증 발표와 전시 계획", date="2026-11-09", topic=t, n_outlets=3, url="u")
                for i, t in ((1, "기관"), (2, "전시·프로그램"), (3, "시장·경매·아트페어"))]
        bad = [dict(title="아이돌 사진전 개최..팬 향한 애정(공식)", date="2026-11-09", topic="그 밖의 소식", n_outlets=40, url="u"),
               dict(title="Séraphine 루이 2분", title_ko="Séraphine 루이 2분", date="2026-11-09", topic="기관", n_outlets=9, url="u")]
        s = shorts.fmt_news(page(news_week=bad + good))
        self.assertEqual(len([b for b in s["beats"] if b["layout"] == "list"]), 3)
        self.assertNotIn("아이돌", " ".join(b["title"] for b in s["beats"]))
        self.assertIn(("보도", "출처 3곳"), s["beats"][1]["rows"])


class RotationTest(unittest.TestCase):
    def test_editions_start_on_different_formats_the_same_morning(self):
        d = dt.date(2026, 11, 10)
        firsts = [shorts.rotation_for(e, d)[0] for e in shorts.EDITIONS]
        self.assertEqual(len(set(firsts)), 4)
        self.assertEqual(set(shorts.rotation_for("KR", d)), set(shorts.ROTATION))

    def test_falls_through_to_the_next_format_with_material(self):
        items = [show(i, start=f"2026-11-1{i}", end="2026-12-20") for i in (1, 2, 3)]
        with NO_TR, NO_FACTS:
            s = shorts.script_for(page(exhibitions=dict(all=dict(upcoming=items))))
        self.assertEqual(s["fmt"], "upcoming")


class WordingTest(unittest.TestCase):
    def test_spoken_rewrites_outlet_counts(self):
        self.assertEqual(shorts.spoken("이번 주 6개 매체가 다뤘다"), "이번 주 언론이 잇따라 다뤘다")
        self.assertEqual(shorts.spoken("백남준, 최근 석 달 동안 51개 매체에 나온 작가"), "백남준, 석 달 사이 51곳에서 이름이 나왔다")

    def test_say_drops_marks_the_voice_would_read(self):
        self.assertEqual(shorts.clean_say("《빛》 · 서울…개막(공식).."), "빛, 서울, 개막.")

    def test_city_inside_venue_is_not_repeated(self):
        self.assertEqual(shorts.loc(dict(venue="서울시립미술관", city="Seoul")), "서울시립미술관")
        self.assertEqual(shorts.loc(dict(venue="Pinault Collection", city="Venice")), "베네치아 Pinault Collection")


if __name__ == "__main__":
    unittest.main()
