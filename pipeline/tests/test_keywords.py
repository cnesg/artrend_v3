import datetime as dt
import unittest

from artrend_mag import keywords

D = dt.date(2026, 11, 4)


class FakeVB:
    def __init__(self, stories, events=None):  # noqa: D401
        self._stories, self.events, self.asof = stories, events or {}, D

    def stories(self, scope, lo, hi, report_day):
        return self._stories

    def ko_of(self, table, key, field, text):
        return None

    def is_specialist(self, a):
        return False

    def source_label(self, a, bare=False):
        return a["publisher"]


def story(title, outlet, days_ago, n=0):
    a = dict(article_id=f"{title}{outlet}{n}", title=title, publisher=outlet, canonical_url=f"https://x/{n}{outlet}",
             published_at=(D - dt.timedelta(days=days_ago)).isoformat())
    return dict(lead=a, members=[a], outlets=[outlet])


def baseline(n=200):
    """Four quiet weeks of ordinary exhibition news."""
    return [story(f"작가 개인전 개최 {i}", f"base{i % 9}", 8 + i % 27, i) for i in range(n)]


class HotKeywordTests(unittest.TestCase):
    def labels(self, stories, people=None):
        return [k["label"] for k in keywords.hot(FakeVB(stories), "KR", D, people)]

    def test_rising_concept_from_several_outlets_is_a_trend(self):
        week = [story(f"섬유 작업 전시 {i}", f"o{i}", i % 5, 1000 + i) for i in range(4)]
        out = keywords.hot(FakeVB(baseline() + week), "KR", D)
        k = next(k for k in out if k["label"] == "섬유·직조")
        self.assertEqual(k["n"], 4)
        self.assertEqual(k["rise"], "새로 등장")
        self.assertEqual(len(k["examples"]), 3)

    def test_one_outlet_repeating_itself_is_not_a_trend(self):
        week = [story(f"섬유 작업 전시 {i}", "same", i % 5, 1000 + i) for i in range(5)]
        self.assertNotIn("섬유·직조", self.labels(baseline() + week))

    def test_a_word_that_is_always_there_is_not_a_trend(self):
        base = [story(f"회화 전시 {i}", f"b{i % 9}", 8 + i % 27, i) for i in range(200)]
        week = [story(f"회화 전시 {i}", f"o{i}", i % 5, 1000 + i) for i in range(10)] + baseline(40)[:30]
        self.assertNotIn("회화", self.labels(base + week))

    def test_bylines_and_sports_do_not_count(self):
        week = [story(f"미술관 소식 (사진=연합뉴스) {i}", f"o{i}", 1, 1000 + i) for i in range(5)]
        week += [story(f"파크골프대회 개인전 장애인 우승 {i}", f"p{i}", 1, 2000 + i) for i in range(5)]
        labels = self.labels(baseline() + week)
        self.assertNotIn("사진", labels)
        self.assertNotIn("장애·접근성", labels)

    def test_named_event_is_found_but_clause_fragments_are_not(self):
        week = [story(f"'아트에디션 아트페어 2026' 개막 {i}", f"o{i}", 1, 1000 + i) for i in range(3)]
        week += [story(f"작품을 볼 수 있는 아트페어 전시 {i}", f"q{i}", 1, 2000 + i) for i in range(3)]
        labels = self.labels(baseline() + week)
        self.assertIn("아트에디션 아트페어", labels)
        self.assertFalse(any(l.startswith("있는") for l in labels))
        self.assertEqual(keywords._norm_event("앞둔 광주비엔날레"), "광주비엔날레")
        self.assertEqual(keywords._norm_event("부산 비엔날레"), "부산 비엔날레")

    def test_people_need_full_names_and_two_signals(self):
        people = [dict(name="유영", press=5, shows=1), dict(name="홍진훤", press=3, shows=0), dict(name="Anselm Kiefer", press=1, shows=1),
                  dict(name="Kiefer", press=4, shows=0), dict(name="김철수", press=1, shows=0)]
        labels = self.labels(baseline(), people)
        self.assertEqual([l for l in labels if l in {"유영", "홍진훤", "Anselm Kiefer", "Kiefer", "김철수"}], ["홍진훤", "Anselm Kiefer"])

    def test_welfare_and_education_news_is_not_a_theme(self):
        week = [story(f"재단{i}, 발달장애 학생 미술교육 성과 전시 {i}", f"o{i}", i % 5, 1000 + i) for i in range(6)]
        week += [story(f"장애예술 작가 전시 개막 {i}", f"q{i}", 1, 2000 + i) for i in range(3)]
        self.assertNotIn("장애·접근성", self.labels(baseline() + week))

    def test_theme_on_the_walls_is_a_trend(self):
        events = {f"e{i}": dict(event_id=f"e{i}", edition_region="KR", start_date=(D - dt.timedelta(days=i)).isoformat(),
                                title=f"배리어프리 미술관{i} 기획전", url=f"https://v/{i}", venue_id=f"v{i}") for i in range(3)}
        week = [story(f"장애 예술가들의 신작 전시 {i}", f"o{i}", 1, 1000 + i) for i in range(2)]
        labels = [k["label"] for k in keywords.hot(FakeVB(baseline() + week, events), "KR", D)]
        self.assertIn("장애·접근성", labels)

    def test_one_gallery_reported_three_ways_is_one_voice(self):
        week = [story(f"부산은행갤러리, 11월 섬유예술 전시 선봬 {i}", f"o{i}", 1, 1000 + i) for i in range(3)]
        week += [story("섬유 작업 신작 전시", "q1", 2, 2000)]
        k = next(k for k in keywords.hot(FakeVB(baseline() + week), "KR", D) if k["label"] == "섬유·직조")
        self.assertEqual(k["n"], 2)

    def test_metaphor_and_substrings_are_not_war(self):
        rx = next(r for l, _, r in keywords.CONCEPT_RE if l == "전쟁·분쟁")
        self.assertIsNone(rx.search("비엔날레 첫 번째 참가자 발표"))
        self.assertIsNone(rx.search("캐나다 미술 시장, 미국과의 무역 전쟁에서 타격"))
        self.assertIsNone(rx.search("Canadian art market hit by the trade war"))
        self.assertIsNotNone(rx.search("Anti-War: A Conversation"))

    def test_non_museum_opening_is_not_a_new_museum(self):
        rx = next(r for l, _, r in keywords.CONCEPT_RE if l == "신규 개관")
        self.assertIsNone(rx.search("국가철도공단 KR컬처라운지 개관"))
        self.assertIsNotNone(rx.search("박서보미술관 개관전"))

    def test_quiet_week_is_filled_and_marked(self):
        strict = [dict(label="판화", kind="매체", score=2.0)]
        backup = [dict(label="판화", kind="매체", score=1.0), dict(label="사진", kind="매체", score=0.8)]
        artists = [dict(name="백남준", press=[dict(title="백남준 전시", url="u", date="2026-11-04")] * 3, shows=[]),
                   dict(name="Kim", press=[dict(title="t", url="u")] * 9, shows=[]),
                   dict(name="Sarah Sze", press=[dict(title="t", url="u")], shows=[dict(title="s", url="u", start="2026-11-01")])]
        early_items = [dict(title="《별, 괘卦》", venue="백남준아트센터", level="뜨는 중", url="u")]
        out = keywords.fill(strict, backup, artists, early_items, n=5)
        self.assertEqual([k["label"] for k in out], ["판화", "사진", "백남준", "Sarah Sze", "별, 괘卦"])
        self.assertTrue(all(k.get("filled") for k in out[1:]))
        self.assertEqual(out[2]["rise"], "이번 주 많이 언급")
        self.assertEqual(len(keywords.fill([dict(label=str(i), score=1) for i in range(6)], backup, artists, early_items)), 6)

    def test_tags_for_matches_concepts_and_names(self):
        kws = [dict(label="도자·공예"), dict(label="홍진훤")]
        self.assertEqual(keywords.tags_for("경기도자비엔날레 32만 명", kws), ["도자·공예"])
        self.assertEqual(keywords.tags_for("홍진훤, 올해의 작가상", kws), ["홍진훤"])


if __name__ == "__main__":
    unittest.main()
