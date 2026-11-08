"""Tests for the committed measured traces.

These tests run offline with no live model call and no key. They check
that the example traces in examples/measured-traces/ are well formed,
that their token arithmetic is internally consistent, and that the
headline numbers in MEASURED.md match the traces. They do not make
any model call: a trace that fails its task must still pass these
checks, because a failed run is still a valid record.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRACES_DIR = REPO / "examples" / "measured-traces"
MEASURED = REPO / "MEASURED.md"

EXPECTED = {
    ("task1_add_function", "lean"): (860, True),
    ("task2_fix_off_by_one", "lean"): (596, True),
    ("task3_write_tests", "lean"): (305, True),
    ("task4_refactor_dupe", "lean"): (481, True),
    ("task5_input_validation", "lean"): (1102, False),
    ("task1_add_function", "direct"): (1321, True),
    ("task2_fix_off_by_one", "direct"): (278, True),
    ("task3_write_tests", "direct"): (408, True),
    ("task4_refactor_dupe", "direct"): (1491, False),
    ("task5_input_validation", "direct"): (312, True),
}


def load_traces():
    found = {}
    for path in sorted(TRACES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result = data["task_results"][0]
        key = (result["task_id"], result["mode"])
        found[key] = (path.name, data, result)
    return found


class TestMeasuredTraces(unittest.TestCase):
    def test_ten_traces_cover_all_tasks_and_modes(self):
        found = load_traces()
        self.assertEqual(set(found), set(EXPECTED))
        self.assertEqual(len(found), 10)

    def test_token_arithmetic_matches_model_calls(self):
        for key, (name, data, result) in load_traces().items():
            calls = data.get("model_calls", [])
            prompt = sum(c.get("prompt_tokens", 0) for c in calls)
            completion = sum(c.get("completion_tokens", 0) for c in calls)
            self.assertEqual(result["prompt_tokens"], prompt, name)
            self.assertEqual(result["completion_tokens"], completion, name)
            self.assertEqual(
                result["prompt_tokens"] + result["completion_tokens"],
                EXPECTED[key][0], name)

    def test_recorded_pass_fail_matches_expected(self):
        for key, (name, data, result) in load_traces().items():
            self.assertEqual(result["passed"], EXPECTED[key][1], name)

    def test_no_estimated_model_calls(self):
        for key, (name, data, result) in load_traces().items():
            self.assertFalse(result.get("estimated"), name)
            for call in data.get("model_calls", []):
                self.assertFalse(call.get("estimated"), name)

    def test_no_key_or_secret_in_traces(self):
        text = ""
        for path in TRACES_DIR.glob("*.json"):
            text += path.read_text(encoding="utf-8")
        self.assertNotIn("sk-bf-", text)
        self.assertNotIn("BIFROST_API_KEY", text)
        self.assertNotRegex(text, r"Bearer [A-Za-z0-9]")

    def test_measured_doc_matches_traces(self):
        text = MEASURED.read_text(encoding="utf-8")
        lean_total = sum(v[0] for k, v in EXPECTED.items()
                         if k[1] == "lean")
        direct_total = sum(v[0] for k, v in EXPECTED.items()
                           if k[1] == "direct")
        self.assertIn(str(lean_total), text)
        self.assertIn(str(direct_total), text)
        self.assertIn("560.5", text)
        self.assertIn("579.75", text)
        for (task_id, mode), (total, passed) in EXPECTED.items():
            self.assertIn(str(total), text)
            self.assertIn(task_id, text)
        self.assertRegex(text, r"failed", re.IGNORECASE)


if __name__ == "__main__":
    unittest.main()
