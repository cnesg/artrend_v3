import json
import tempfile
import unittest
from pathlib import Path

from artrend_mag import vault_web

PAGE = dict(
    edition="KR", date="2026-11-13",
    keywords=[dict(label="옥션쇼", note="이번 주 9건", why=["경매 기록", "서울옥션이 2주간 1000점을 내놓는다"])],
    stories=[dict(rank=1, title="서울옥션, 1000점 '옥션쇼' 연다", url="https://a.test/1", topic="시장·경매·아트페어", n_outlets=11,
                  date="2026-11-11", short=False, bullets=["11일부터 24일까지 강남센터"], so_what="가격은 시장의 온도일 뿐이다.",
                  sources=[dict(outlet="a", url="https://a.test/1"), dict(outlet="b", url="https://b.test/2")])],
    news_week=[dict(title="필립스옥션 [뉴욕] 경매 | 개최", url="https://c.test/3", date="2026-11-12", topic="시장·경매·아트페어", n_outlets=4),
               dict(title="전시 소식", url="https://d.test/4", date="2026-11-12", topic="전시·프로그램", n_outlets=1)],
    rookie=dict(people=[dict(name="이영호", award="단원미술제", status="주목할 신진", points=["2023년부터 개인전을 열어 온 경력 초기 작가다."])]),
    galleries=dict(all=dict(news=[dict(title="New show", url="https://g.test", date="2026-11-06", source="Arario Gallery")])),
)


class VaultWebTest(unittest.TestCase):
    def test_note_carries_what_the_reader_sees(self):
        md = vault_web.render(PAGE)
        self.assertIn("**옥션쇼** · 이번 주 9건 — 경매 기록", md)
        self.assertIn("같은 소식: [b](https://b.test/2)", md)
        self.assertIn("2023년부터 개인전을 열어 온 경력 초기 작가다.", md)
        self.assertIn("Arario Gallery", md)
        market = md.split("## 시장 · 경매 · 아트페어 소식")[1].split("## ")[0]
        self.assertIn("필립스옥션 (뉴욕) 경매 / 개최", market)  # brackets and pipes cannot break the markdown
        self.assertNotIn("전시 소식", market)
        self.assertIn("## EARLY SIGNAL\n\n- 이번 화면에는 없음", md)

    def test_write_mirrors_every_day_and_drops_old_days(self):
        with tempfile.TemporaryDirectory() as t:
            web, vault = Path(t) / "web", Path(t) / "vault"
            (web / "2026-11-13").mkdir(parents=True)
            (web / "2026-11-13" / "KR.json").write_text(json.dumps(PAGE, ensure_ascii=False), encoding="utf-8")
            (vault / vault_web.FOLDER / "2026-11-01").mkdir(parents=True)
            (vault / vault_web.FOLDER / "2026-11-01" / "old.md").write_text("x", encoding="utf-8")
            self.assertEqual(vault_web.write(web, vault), {"웹 화면 노트": 1})
            folder = vault / vault_web.FOLDER
            self.assertTrue((folder / "2026-11-13" / "2026-11-13 한국 화면.md").exists())
            self.assertFalse((folder / "2026-11-01").exists())
            self.assertIn("[[2026-11-13 한국 화면|한국]]", (folder / "오늘의 화면.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
