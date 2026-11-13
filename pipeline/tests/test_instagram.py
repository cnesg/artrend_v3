import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from artrend_mag import instagram


class Resp:
    def __init__(self, body, code=200):
        self.body, self.status_code, self.text = body, code, json.dumps(body)

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, statuses):
        self.calls, self.statuses = [], list(statuses)

    def post(self, url, **kw):
        self.calls.append(("POST", url))
        if url.endswith("/media"):
            return Resp({"id": "C1"})
        if "rupload" in url:
            return Resp({"success": True})
        if url.endswith("/media_publish"):
            return Resp({"id": "M1"})
        raise AssertionError(url)

    def get(self, url, **kw):
        self.calls.append(("GET", url))
        if url.endswith("/C1"):
            return Resp({"status_code": self.statuses.pop(0)})
        return Resp({"permalink": "https://instagram.com/reel/x"})


class InstagramTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        day = root / "2026-11-11"
        day.mkdir()
        for ed, subj in (("KR", "백남준"), ("JP", "Mariko Mori")):
            (day / f"{ed}.mp4").write_bytes(b"\0" * 10)
            (day / f"{ed}.json").write_text(json.dumps(dict(edition=ed, file=f"{ed}.mp4", subject=subj, caption="캡션 #ARTREND")), encoding="utf-8")
        self.p = mock.patch.object(instagram, "SHORTS", root)
        self.p.start()

    def tearDown(self):
        self.p.stop()
        self.tmp.cleanup()

    def test_korean_short_first_and_recent_subject_skipped(self):
        d = dt.date(2026, 11, 11)
        self.assertEqual(instagram.choose(d, [])["edition"], "KR")
        log = [dict(date="2026-11-05", status="posted", subject="백남준")]
        self.assertEqual(instagram.choose(d, log)["edition"], "JP")
        old = [dict(date="2026-10-20", status="posted", subject="백남준")]
        self.assertEqual(instagram.choose(d, old)["edition"], "KR")

    def test_reel_flow_waits_for_processing_then_publishes(self):
        s = FakeSession(["IN_PROGRESS", "FINISHED"])
        out = instagram.post_reel(instagram.SHORTS / "2026-11-11" / "KR.mp4", "c", "U", "T", s=s, sleep=lambda _: None)
        self.assertEqual(out["media_id"], "M1")
        self.assertEqual([c[0] for c in s.calls], ["POST", "POST", "GET", "GET", "POST", "GET"])

    def test_processing_error_raises(self):
        with self.assertRaises(instagram.PostError):
            instagram.post_reel(instagram.SHORTS / "2026-11-11" / "KR.mp4", "c", "U", "T", s=FakeSession(["ERROR"]), sleep=lambda _: None)

    def test_caption_keeps_at_most_30_hashtags(self):
        cap = instagram.caption_of(dict(caption=" ".join(f"#t{i}" for i in range(40))))
        self.assertEqual(len([w for w in cap.split() if w.startswith("#")]), 30)


if __name__ == "__main__":
    unittest.main()
