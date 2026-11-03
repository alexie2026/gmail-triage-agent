import datetime
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def make_email(mid, sender, subject):
    return {
        "id": mid, "sender": sender, "subject": subject, "snippet": "", "body": "",
        "date": datetime.datetime.now(tz=datetime.timezone.utc),
    }


class RunAllTests(unittest.TestCase):
    def setUp(self):
        self.labeled, self.fetched = [], []
        self.emails = {}
        self.tmp = tempfile.TemporaryDirectory()
        self.log_path = Path(self.tmp.name) / "log.json"

        reader = types.ModuleType("gmail_reader")
        reader.get_all_unread_ids_oldest_first = lambda: (list(self.emails), object())
        reader.fetch_email_by_id = lambda service, mid: (self.fetched.append(mid), self.emails[mid])[1]
        labeler = types.ModuleType("labeler")
        labeler.apply_low_priority_label = lambda mid: self.labeled.append(mid)
        sys.modules["gmail_reader"], sys.modules["labeler"] = reader, labeler
        sys.modules.pop("main", None)
        self.main = importlib.import_module("main")
        # stub model: anything with "promo" in the subject is low priority
        self.main.classify_email = lambda e: {
            "priority": "low_priority" if "promo" in e["subject"].lower() else "important",
            "reason": "stub",
        }

    def tearDown(self):
        self.tmp.cleanup()
        for name in ("gmail_reader", "labeler", "main"):
            sys.modules.pop(name, None)

    def add(self, *emails):
        for e in emails:
            self.emails[e["id"]] = e

    def test_dry_run_labels_nothing_but_logs_everything(self):
        self.add(make_email("1", "a@x.com", "Hello"), make_email("2", "b@y.com", "Big promo"))
        result = self.main.run_all(dry_run=True, log_path=self.log_path)
        self.assertEqual(self.labeled, [])
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(json.loads(self.log_path.read_text())), 2)

    def test_live_run_labels_only_low_priority(self):
        self.add(make_email("1", "a@x.com", "Hello"), make_email("2", "b@y.com", "Big promo"))
        self.main.run_all(dry_run=False, log_path=self.log_path)
        self.assertEqual(self.labeled, ["2"])

    def test_rerun_skips_ids_already_in_the_log(self):
        self.add(make_email("1", "a@x.com", "Hello"), make_email("2", "b@y.com", "Big promo"))
        self.main.run_all(dry_run=False, log_path=self.log_path)
        self.fetched.clear()
        result = self.main.run_all(dry_run=False, log_path=self.log_path)
        self.assertEqual(self.fetched, [])
        self.assertEqual(result["total"], 2)

    def test_repeated_sender_and_subject_collapses_to_low_priority(self):
        self.add(make_email("1", "a@x.com", "Weekly update"), make_email("2", "a@x.com", "Weekly update"))
        self.main.run_all(dry_run=False, log_path=self.log_path)
        self.assertEqual(self.labeled, ["2"])

    def test_important_override_is_not_collapsed(self):
        self.add(
            make_email("1", "a@x.com", "Security alert: new device"),
            make_email("2", "a@x.com", "Security alert: new device"),
        )
        self.main.run_all(dry_run=False, log_path=self.log_path)
        self.assertEqual(self.labeled, [])


if __name__ == "__main__":
    unittest.main()
