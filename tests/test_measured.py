"""Tests for the committed measured traces.

These tests run offline with no live model call and no key. They check
that the example traces in examples/measured-traces/ are well formed,
that their token arithmetic is internally consistent, and that the
headline numbers in MEASURED.md match the traces. They do not make
any model call: a trace that fails its task must still pass these
checks, because a failed run is still a valid record.

The Batch 4 class does the same for the 30 traces in
examples/measured-traces-batch4/ (5 tasks, 3 repeats, 2 modes).
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRACES_DIR = REPO / "examples" / "measured-traces"
TRACES_DIR_BATCH4 = REPO / "examples" / "measured-traces-batch4"
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


EXPECTED_BATCH4 = {
    # (task, mode): [(total tokens, passed), ...] in run order.
    ("task1_add_function", "lean"): [(1204, True), (1249, True),
                                     (2212, False)],
    ("task1_add_function", "direct"): [(979, True), (792, True),
                                       (1619, True)],
    ("task2_fix_off_by_one", "lean"): [(288, True), (709, True),
                                       (276, True)],
    ("task2_fix_off_by_one", "direct"): [(1687, False), (278, True),
                                         (722, True)],
    ("task3_write_tests", "lean"): [(2221, False), (453, True),
                                    (408, True)],
    ("task3_write_tests", "direct"): [(408, True), (853, True),
                                      (408, True)],
    ("task4_refactor_dupe", "lean"): [(2652, False), (1655, True),
                                      (462, True)],
    ("task4_refactor_dupe", "direct"): [(459, True), (472, True),
                                        (2593, True)],
    ("task5_input_validation", "lean"): [(1724, False), (1409, True),
                                         (660, True)],
    ("task5_input_validation", "direct"): [(990, True), (1745, False),
                                          (1431, True)],
}


def load_traces_batch4():
    found = {}
    for path in sorted(TRACES_DIR_BATCH4.glob("*.json"),
                       key=lambda p: p.stat().st_mtime):
        data = json.loads(path.read_text(encoding="utf-8"))
        result = data["task_results"][0]
        key = (result["task_id"], result["mode"])
        found.setdefault(key, []).append((path.name, data, result))
    return found


class TestMeasuredTracesBatch4(unittest.TestCase):
    def test_thirty_traces_cover_all_tasks_modes_and_repeats(self):
        found = load_traces_batch4()
        self.assertEqual(set(found), set(EXPECTED_BATCH4))
        self.assertEqual(len(found), 10)
        for key, runs in found.items():
            self.assertEqual(len(runs), 3, key)
        total = sum(len(runs) for runs in found.values())
        self.assertEqual(total, 30)

    def test_token_arithmetic_matches_model_calls(self):
        for key, runs in load_traces_batch4().items():
            for name, data, result in runs:
                calls = data.get("model_calls", [])
                prompt = sum(c.get("prompt_tokens", 0) for c in calls)
                completion = sum(c.get("completion_tokens", 0)
                                 for c in calls)
                self.assertEqual(result["prompt_tokens"], prompt, name)
                self.assertEqual(result["completion_tokens"], completion,
                                 name)

    def test_recorded_tokens_and_pass_fail_match_expected(self):
        for key, runs in load_traces_batch4().items():
            expected = EXPECTED_BATCH4[key]
            self.assertEqual(len(runs), len(expected), key)
            for (name, _data, result), (total, passed) in zip(runs,
                                                              expected):
                self.assertEqual(
                    result["prompt_tokens"] + result["completion_tokens"],
                    total, name)
                self.assertEqual(result["passed"], passed, name)

    def test_no_estimated_model_calls(self):
        for key, runs in load_traces_batch4().items():
            for name, data, result in runs:
                self.assertFalse(result.get("estimated"), name)
                for call in data.get("model_calls", []):
                    self.assertFalse(call.get("estimated"), name)

    def test_no_key_or_secret_in_traces(self):
        text = ""
        for path in TRACES_DIR_BATCH4.glob("*.json"):
            text += path.read_text(encoding="utf-8")
        self.assertNotIn("sk-bf-", text)
        self.assertNotIn("BIFROST_API_KEY", text)
        self.assertNotRegex(text, r"Bearer [A-Za-z0-9]")

    def test_measured_doc_contains_batch4_numbers(self):
        text = MEASURED.read_text(encoding="utf-8")
        self.assertIn("Batch 4", text)
        self.assertIn("797.5", text)
        self.assertIn("923.4", text)
        self.assertIn("11 of 15", text)
        self.assertIn("13 of 15", text)
        for task_id in ("task1_add_function", "task2_fix_off_by_one",
                        "task3_write_tests", "task4_refactor_dupe",
                        "task5_input_validation"):
            self.assertIn(task_id, text)


if __name__ == "__main__":
    unittest.main()
