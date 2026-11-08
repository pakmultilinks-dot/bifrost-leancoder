"""Tests for verify.py. The end-to-end tests run verify.py as a
subprocess, which itself runs the unit suite. Those tests skip when
LEANCODER_VERIFY_NESTED is set, so a nested run cannot recurse.
Everything is offline, no live call."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verify import check_traces, run_unit_tests

from leancoder.ledger import RunLedger

NESTED = os.environ.get("LEANCODER_VERIFY_NESTED") == "1"

MEDIAN_FILE = '''"""Small math helpers."""\n\n\ndef add(a, b):\n    """Return a plus b."""\n    return a + b\n\n\ndef subtract(a, b):\n    """Return a minus b."""\n    return a - b\n\n\ndef median(values):\n    """Return the median of a list of numbers."""\n    if not values:\n        raise ValueError("median of an empty list")\n    ordered = sorted(values)\n    n = len(ordered)\n    mid = n // 2\n    if n % 2:\n        return ordered[mid]\n    return (ordered[mid - 1] + ordered[mid]) / 2\n'''


def _good_trace_dir(tmp):
    ledger = RunLedger(run_id="test-verify-good", traces_dir=tmp)
    ledger.record_model_call("task1_add_function", "lean",
                             "gemini/gemini-2.5-flash", 100, 50)
    ledger.record_patch("task1_add_function", 1, "mathutil.py", MEDIAN_FILE)
    ledger.record_task_result("task1_add_function", "lean",
                              "gemini/gemini-2.5-flash", True, 1, 100, 50)
    ledger.save()
    return tmp


def _bad_trace_dir(tmp):
    ledger = RunLedger(run_id="test-verify-bad", traces_dir=tmp)
    ledger.record_model_call("task1_add_function", "lean",
                             "gemini/gemini-2.5-flash", 100, 50)
    ledger.record_patch("task1_add_function", 1, "mathutil.py", MEDIAN_FILE)
    ledger.record_task_result("task1_add_function", "lean",
                              "gemini/gemini-2.5-flash", True, 1, 999, 0)
    ledger.save()
    return tmp


def _run_verify(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "verify.py")] + list(args),
        cwd=ROOT, capture_output=True, text=True, timeout=300)


class TestVerifyHelpers(unittest.TestCase):
    def test_unit_tests_run_and_pass(self):
        if NESTED:
            self.skipTest("nested verify run")
        ran, failed, _output = run_unit_tests(ROOT / "tests")
        self.assertGreaterEqual(ran, 51)
        self.assertFalse(failed)

    def test_check_traces_no_traces(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines, matched, total, matched_count = check_traces(
                tmp, ROOT / "tasks")
            self.assertTrue(matched)
            self.assertEqual(total, 0)
            self.assertEqual(matched_count, 0)
            self.assertIn("skipped", lines[0])

    def test_check_traces_good_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            _good_trace_dir(tmp)
            _lines, matched, total, matched_count = check_traces(
                tmp, ROOT / "tasks")
            self.assertTrue(matched)
            self.assertEqual(total, 1)
            self.assertEqual(matched_count, 1)

    def test_check_traces_bad_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            _bad_trace_dir(tmp)
            lines, matched, total, matched_count = check_traces(
                tmp, ROOT / "tasks")
            self.assertFalse(matched)
            self.assertEqual(total, 1)
            self.assertEqual(matched_count, 0)
            self.assertTrue(any("Mismatch" in line for line in lines))


class TestVerifyEndToEnd(unittest.TestCase):
    def test_verify_passes_with_no_traces(self):
        if NESTED:
            self.skipTest("nested verify run")
        with tempfile.TemporaryDirectory() as tmp:
            result = _run_verify("--traces-dir", tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)
            self.assertIn("Unit tests:", result.stdout)

    def test_verify_passes_with_good_trace(self):
        if NESTED:
            self.skipTest("nested verify run")
        with tempfile.TemporaryDirectory() as tmp:
            _good_trace_dir(tmp)
            result = _run_verify("--traces-dir", tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)
            self.assertIn("1 of 1 tasks matched", result.stdout)

    def test_verify_fails_with_bad_trace(self):
        if NESTED:
            self.skipTest("nested verify run")
        with tempfile.TemporaryDirectory() as tmp:
            _bad_trace_dir(tmp)
            result = _run_verify("--traces-dir", tmp)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL", result.stdout)


if __name__ == "__main__":
    unittest.main()
