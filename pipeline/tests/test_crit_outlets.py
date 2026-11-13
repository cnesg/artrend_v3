import json
import unittest

from artrend_mag.sources import crit_outlets


class PieceTypeTest(unittest.TestCase):
    def test_criticism_outlet_defaults_to_criticism_but_reads_markers(self):
        self.assertEqual(crit_outlets.piece_type("criticism", "https://x/a", [])[0], "criticism")
        self.assertEqual(crit_outlets.piece_type("criticism", "https://x/reviews/a", [])[0], "review")
        self.assertEqual(crit_outlets.piece_type("criticism", "https://x/a", ["Interviews"])[0], "interview")
        self.assertEqual(crit_outlets.piece_type("criticism", "https://x/a", ["事務局員募集"])[0], "news")

    def test_news_outlet_counts_only_marked_reviews(self):
        self.assertEqual(crit_outlets.piece_type("news", "https://x/market/a", ["Market"])[0], "news")
        self.assertEqual(crit_outlets.piece_type("news", "https://x/a", ["Recensioni"])[0], "review")


class SiteListTest(unittest.TestCase):
    def test_no_permission_blocked_outlet_is_collected(self):
        hosts = {s["home"].split("//")[-1].split("/")[0].removeprefix("www.") for s in crit_outlets.load_sites()}
        for blocked in ("artnews.com", "artforum.com", "artasiapacific.com", "artsy.net", "news.artnet.com", "facebook.com"):
            self.assertNotIn(blocked, hosts)

    def test_every_site_has_an_edition_and_a_listing(self):
        for s in crit_outlets.load_sites():
            self.assertIn(s["edition"], ("KR", "JP", "AMERICAS", "EUROPE"))
            self.assertIn(s["method"], ("feed", "html"))
            self.assertTrue(s["source_id"].startswith("crit_"))


class DirectoryTest(unittest.TestCase):
    def test_editor_list_is_complete_and_labelled_without_emoji(self):
        doc = json.load(open(crit_outlets.Path(__file__).resolve().parents[1] / "editorial" / "critique_outlets.json", encoding="utf-8"))
        self.assertEqual(len(doc["outlets"]), 138)
        for o in doc["outlets"]:
            self.assertTrue(o["status_label"].isprintable() and all(ord(ch) < 0x2600 or 0xAC00 <= ord(ch) <= 0xD7A3 for ch in o["status_label"]))


if __name__ == "__main__":
    unittest.main()
