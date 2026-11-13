import unittest

from artrend_mag import why
from artrend_mag.web_export import show_key, uniq_shows


class WhyTest(unittest.TestCase):
    def test_cause_named_by_most_titles_wins(self):
        self.assertEqual(why.driver(["작가 A 회고전 개막", "A 회고전 리뷰", "A, 수상"])[0], "대규모 회고전")
        self.assertEqual(why.driver(["경매서 30억 원에 낙찰…최고가"])[0], "경매 기록")
        self.assertIsNone(why.driver(["새 소식", ""]))
        self.assertEqual(why.driver(["공모전 선정작가 B 개인전", "B 개인전 개막"])[0], "수상·선정")

    def test_abroad_is_read_from_the_korean_desk_only(self):
        t = ["백남준아트센터, 상파울루 미술관과 공동기획전 개막"]
        self.assertEqual(why.driver(t, "KR")[0], "해외 기관 진출")
        self.assertIsNone(why.driver(["런던 테이트 전시"], "EUROPE"))

    def test_director_title_is_not_an_acquisition(self):
        self.assertIsNone(why.driver(["문화재연구소장 발표"]))

    def test_artist_without_named_cause_gets_the_museum_reason(self):
        a = dict(name="Sarah Sze", press=[], shows=[dict(title="Sarah Sze: Forever", venue="MoMA", kind="museum")])
        self.assertEqual(why.artist(a, "AMERICAS")[0], "미술관 개인전")
        a["shows"][0]["title"] = "Group Show"
        self.assertEqual(why.artist(a, "AMERICAS")[0], "미술관 기획전 초대")

    def test_artist_with_only_an_upcoming_show_is_not_called_on_view(self):
        a = dict(name="Asuka", press=[], shows=[dict(title="Yume", venue="Perrotin", kind="gallery", status="개막 예정")])
        self.assertEqual(why.artist(a)[0], "곧 개막")

    def test_keyword_reasons_by_kind(self):
        self.assertEqual(why.keyword(dict(label="경주아트페어", kind="행사"))[0], "페어 주간")
        self.assertIn("재평가", why.keyword(dict(label="회고전", kind="형식"))[1])
        self.assertEqual(why.keyword(dict(label="판화", kind="매체", examples=[]))[0], "판화 전시 잇따름")

    def test_show_closing_and_opening(self):
        self.assertEqual(why.show(dict(title="풍경", status="종료 D-4", artists=["a", "b"]))[0], "곧 종료")
        self.assertEqual(why.show(dict(title="풍경", status="개막 D-1", artists=[]))[0], "곧 개막")


class ShowKeyTest(unittest.TestCase):
    def test_same_show_listed_twice_collapses(self):
        a = "서서울미술관 뉴미디어 신진작가전 《탈피하지 못하는 뱀은》"
        b = "2026 서서울미술관 뉴미디어 신진작가전 《탈피하지 못하는 뱀은》"
        self.assertEqual(show_key(a, "서울시립미술관"), show_key(b, "서울시립 서서울미술관"))
        self.assertEqual(len(uniq_shows([dict(title=a), dict(title=b)])), 1)

    def test_short_generic_titles_stay_apart_by_venue(self):
        self.assertEqual(len(uniq_shows([dict(title="개인전", venue="A"), dict(title="개인전", venue="B")])), 2)


class RookieReaderTest(unittest.TestCase):
    def test_desk_notes_are_not_shown_to_readers(self):
        from artrend_mag.web_export import reader_why, rookie_points
        self.assertIsNone(reader_why("보도 요약에 선정 사유 문장 없음."))
        self.assertIsNone(reader_why("e-flux 공지 — 수상(본문은 이미지 캡션 위주라 사유 미확인)."))
        self.assertEqual(reader_why("e-flux 공지 — 수상과 신작 전시."), "수상과 신작 전시.")
        c = dict(checks=[dict(rule="R02 초기 경력", ok=True, detail="보도로 확인된 가장 이른 개인전 2023년 · 최근 기사 위주 검색이라 더 이른 이력이 있을 수 있음"),
                         dict(rule="R03 독립 확인", ok=None, detail="이름 검색을 하지 않음 — 편집자 확인 필요"),
                         dict(rule="R05 후속 지원", ok=True, detail="상에 딸린 후속 지원: 상금 2,000만원")])
        pts = rookie_points(c, None)
        self.assertEqual(pts, ["2023년부터 개인전을 열어 온 경력 초기 작가다.", "수상 뒤 이어지는 지원: 상금 2,000만원"])
        self.assertFalse(any("검색" in p or "확인 필요" in p for p in pts))

    def test_homonym_career_is_withheld(self):
        from artrend_mag.web_export import rookie_points
        c = dict(checks=[dict(rule="R02", ok=True, detail="보도로 확인된 가장 이른 개인전 2026년"),
                         dict(rule="R03", ok=None, detail="… — 동명이인 기사가 많아 같은 사람인지 편집자 확인 전에는 통과로 보지 않음")])
        self.assertEqual(rookie_points(c, None), [])


if __name__ == "__main__":
    unittest.main()
