"""Tests for trace replay. Everything is offline, no live call."""
import tempfile
import unittest
from pathlib import Path

from leancoder.ledger import RunLedger
from leancoder.replay import TraceError, load_trace, replay_ledger

ROOT = Path(__file__).resolve().parent.parent

MEDIAN_FILE = '''"""Small math helpers."""\n\n\ndef add(a, b):\n    """Return a plus b."""\n    return a + b\n\n\ndef subtract(a, b):\n    """Return a minus b."""\n    return a - b\n\n\ndef median(values):\n    """Return the median of a list of numbers."""\n    if not values:\n        raise ValueError("median of an empty list")\n    ordered = sorted(values)\n    n = len(ordered)\n    mid = n // 2\n    if n % 2:\n        return ordered[mid]\n    return (ordered[mid - 1] + ordered[mid]) / 2\n'''

WRONG_FILE = '''"""Small math helpers."""\n\n\ndef add(a, b):\n    """Return a plus b."""\n    return a + b\n\n\ndef subtract(a, b):\n    """Return a minus b."""\n    return a - b\n\n\ndef median(values):\n    """Return the median of a list of numbers."""\n    return 0\n'''


def _good_ledger(tmp):
    ledger = RunLedger(run_id="test-replay-good", traces_dir=tmp)
    ledger.record_model_call("task1_add_function", "lean",
                             "gemini/gemini-2.5-flash", 100, 50)
    ledger.record_patch("task1_add_function", 1, "mathutil.py", MEDIAN_FILE)
    ledger.record_test_result("task1_add_function", True, 0, "ok")
    ledger.record_task_result("task1_add_function", "lean",
                              "gemini/gemini-2.5-flash", True, 1, 100, 50)
    return ledger.save()


class TestReplayMatch(unittest.TestCase):
    def test_replay_matches_good_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _good_ledger(tmp)
            report = replay_ledger(path, tasks_dir=ROOT / "tasks")
            self.assertTrue(report["overall_match"])
            self.assertEqual(report["checked"], 1)
            self.assertEqual(report["matched"], 1)
            task = report["tasks"][0]
            self.assertTrue(task["expected_passed"])
            self.assertTrue(task["replay_passed"])
            self.assertEqual(task["differences"], [])

    def test_replay_detects_test_outcome_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RunLedger(run_id="test-replay-wrong",
                               traces_dir=tmp)
            ledger.record_model_call("task1_add_function", "lean",
                                     "gemini/gemini-2.5-flash", 100, 50)
            ledger.record_patch("task1_add_function", 1, "mathutil.py",
                                WRONG_FILE)
            ledger.record_test_result("task1_add_function", True, 0, "ok")
            ledger.record_task_result("task1_add_function", "lean",
                                      "gemini/gemini-2.5-flash",
                                      True, 1, 100, 50)
            path = ledger.save()
            report = replay_ledger(path, tasks_dir=ROOT / "tasks")
            self.assertFalse(report["overall_match"])
            self.assertEqual(len(report["tasks"][0]["differences"]), 1)
            self.assertIn("passed", report["tasks"][0]["differences"][0])

    def test_replay_detects_token_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RunLedger(run_id="test-replay-tokens",
                               traces_dir=tmp)
            ledger.record_model_call("task1_add_function", "lean",
                                     "gemini/gemini-2.5-flash", 100, 50)
            ledger.record_patch("task1_add_function", 1, "mathutil.py",
                                MEDIAN_FILE)
            ledger.record_task_result("task1_add_function", "lean",
                                      "gemini/gemini-2.5-flash",
                                      True, 1, 999, 0)
            path = ledger.save()
            report = replay_ledger(path, tasks_dir=ROOT / "tasks")
            self.assertFalse(report["overall_match"])
            self.assertTrue(any("token" in d.lower() for d in
                                report["tasks"][0]["differences"]))

    def test_replay_no_patch_for_passed_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RunLedger(run_id="test-replay-nopatch",
                               traces_dir=tmp)
            ledger.record_model_call("task1_add_function", "lean",
                                     "gemini/gemini-2.5-flash", 100, 50)
            ledger.record_task_result("task1_add_function", "lean",
                                      "gemini/gemini-2.5-flash",
                                      True, 1, 100, 50)
            path = ledger.save()
            report = replay_ledger(path, tasks_dir=ROOT / "tasks")
            self.assertFalse(report["overall_match"])
            self.assertTrue(any("no patch" in d.lower() for d in
                                report["tasks"][0]["differences"]))

    def test_replay_failed_task_with_no_patch_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RunLedger(run_id="test-replay-failed",
                               traces_dir=tmp)
            ledger.record_model_call("task1_add_function", "lean",
                                     "gemini/gemini-2.5-flash", 100, 50)
            ledger.record_task_result("task1_add_function", "lean",
                                      "gemini/gemini-2.5-flash",
                                      False, 3, 100, 50,
                                      error="No patch found.")
            path = ledger.save()
            report = replay_ledger(path, tasks_dir=ROOT / "tasks")
            self.assertTrue(report["overall_match"])


class TestLoadTrace(unittest.TestCase):
    def test_bad_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(TraceError):
                load_trace(path)

    def test_missing_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.json"
            path.write_text('{"run_id": "x"}', encoding="utf-8")
            with self.assertRaises(TraceError):
                load_trace(path)

    def test_missing_file_raises(self):
        with self.assertRaises(TraceError):
            load_trace("/tmp/does-not-exist-leancoder.json")


if __name__ == "__main__":
    unittest.main()
