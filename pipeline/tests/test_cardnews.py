import unittest

from artrend_mag import cardnews


def page():
    show = dict(title="《빛》", venue="서울시립미술관", city="Seoul", start="2026-11-01", end="2027-02-14", status="개막 9일째",
                level="뜨는 중", reasons=["이번 주 4개 매체가 다뤘다"], image="https://x/a.jpg", artists=["김작가"])
    return dict(
        date="2026-11-10",
        headlines=[dict(title="이번 주 전시 키워드: 판화", dek="전시 3곳", points=["판화가 돌아왔다."], what=[], image=None)],
        top=dict(hero=[0]),
        early=[show, dict(show, title="《다른 전시》", venue="리움", artists=["이작가"])],
        artists=[dict(name="김작가", cats=["전시 중"], summary=["전시와 보도에 동시에 오른 이름"], image="https://x/a.jpg"),
                 dict(name="박작가", cats=["개인전"], summary=["이번 주 개인전으로 무대에 오른 작가."], image=None)],
        official=[dict(title="소장품 기증 발표", title_ko=None, org="국립현대미술관", date="2026-11-09", weight=2, url="u")],
        stories=[dict(title="미술관 새 관장 선임", title_ko=None, topic="기관·정책·제도", bullets=["9일 발표됐다."], lead="", outlet="a.kr",
                      n_outlets=3, short=False)],
        rookie=dict(people=[], awards=[]), fairs=[], galleries=dict(openings=[]), keywords=[dict(label="판화")],
    )


class CardnewsPlanTest(unittest.TestCase):
    def test_one_slide_per_kind_and_no_repeated_subject(self):
        slides = cardnews.plan(page(), set(), None)
        self.assertEqual(slides[0]["kind"], "cover")
        kinds = [s["kicker"].split(" · ")[0] for s in slides[1:]]
        self.assertEqual(kinds, ["먼저 가볼 곳", "작가", "기관 발표", "뉴스"])
        # the early-signal show already brought 김작가 in, so the artist slide moves on to someone else
        self.assertEqual(slides[2]["title"], "박작가")

    def test_recent_subjects_are_skipped_when_fresh_ones_exist(self):
        slides = cardnews.plan(page(), {cardnews.norm("《빛》")}, None)
        self.assertEqual(slides[1]["title"], "《다른 전시》")

    def test_todays_short_artist_is_left_to_the_video(self):
        p = page()
        p["early"] = []
        slides = cardnews.plan(p, set(), "김작가")
        self.assertNotIn("김작가", [s["title"] for s in slides])


if __name__ == "__main__":
    unittest.main()


class SeriesTest(unittest.TestCase):
    def test_weekday_series(self):
        import datetime as dt
        self.assertEqual(cardnews.series_of(dt.date(2026, 11, 9))["key"], "rookie")   # Monday
        self.assertEqual(cardnews.series_of(dt.date(2026, 11, 13))["key"], "weekend")  # Friday

    def test_series_leads_and_set_stays_mixed(self):
        import datetime as dt
        slides = cardnews.plan(page(), set(), None, cardnews.series_of(dt.date(2026, 11, 13)))
        self.assertEqual(slides[0]["kicker"], "금요일 · 주말 전시")
        kinds = [s["kicker"].split(" · ")[0] for s in slides[1:]]
        self.assertEqual(kinds[:2], ["먼저 가볼 곳", "먼저 가볼 곳"])
        self.assertIn("기관 발표", kinds)

    def test_thin_series_falls_back_to_mixed_set(self):
        import datetime as dt
        slides = cardnews.plan(page(), set(), None, cardnews.series_of(dt.date(2026, 11, 9)))  # no rookies in the fixture
        self.assertNotEqual(slides[0]["kicker"], "월요일 · 신진")
