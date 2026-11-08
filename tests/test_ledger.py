"""Tests for the token ledger. Everything is offline, no live call."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from leancoder.agent import Agent
from leancoder.approval import ApprovalGate
from leancoder.bifrost_client import ChatResult
from leancoder.budget import TokenBudget
from leancoder.ledger import RunLedger
from leancoder.tools import SandboxTools

ROOT = Path(__file__).resolve().parent.parent

MEDIAN_PATCH = """FILE: mathutil.py
```python
\"\"\"Small math helpers.\"\"\"


def add(a, b):
    \"\"\"Return a plus b.\"\"\"
    return a + b


def subtract(a, b):
    \"\"\"Return a minus b.\"\"\"
    return a - b


def median(values):
    \"\"\"Return the median of a list of numbers.\"\"\"
    if not values:
        raise ValueError("median of an empty list")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2
```
"""


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, messages, model=None):
        content, prompt, completion = self.replies.pop(0)
        return ChatResult(content,
                          {"prompt_tokens": prompt,
                           "completion_tokens": completion,
                           "total_tokens": prompt + completion},
                          model or "test/model")


def _setup_task1(tmp):
    task = ROOT / "tasks" / "task1_add_function"
    for item in (task / "starter").rglob("*"):
        if item.is_file():
            target = Path(tmp) / item.relative_to(task / "starter")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(item, target)
    shutil.copytree(task / "hidden", Path(tmp) / "hidden")
    return (task / "task.md").read_text(encoding="utf-8")


class TestLedgerRecords(unittest.TestCase):
    def test_model_call_cost_unknown_when_none(self):
        ledger = RunLedger(run_id="test-1")
        entry = ledger.record_model_call("task1_add_function", "lean",
                                         "gemini/gemini-2.5-flash",
                                         100, 50)
        self.assertEqual(entry["total_tokens"], 150)
        self.assertIsNone(entry["cost"])

    def test_model_call_with_explicit_cost(self):
        ledger = RunLedger(run_id="test-2")
        entry = ledger.record_model_call("task1_add_function", "lean",
                                         "ollama/qwen2.5-coder",
                                         10, 5, cost=0.0)
        self.assertEqual(entry["cost"], 0.0)

    def test_tool_test_approval_patch_records(self):
        ledger = RunLedger(run_id="test-3")
        ledger.record_tool_call("read_file", "mathutil.py")
        ledger.record_test_result("task1_add_function", True, 0, "ok")
        ledger.record_approval("write_patch", "Write file mathutil.py",
                               True)
        ledger.record_patch("task1_add_function", 1, "mathutil.py",
                            "content here")
        data = ledger.to_dict()
        self.assertEqual(len(data["tool_calls"]), 1)
        self.assertEqual(len(data["test_results"]), 1)
        self.assertEqual(len(data["approvals"]), 1)
        self.assertEqual(len(data["patches"]), 1)

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RunLedger(run_id="test-save", traces_dir=tmp)
            ledger.record_model_call("task1_add_function", "lean",
                                     "gemini/gemini-2.5-flash", 100, 50)
            ledger.record_task_result("task1_add_function", "lean",
                                      "gemini/gemini-2.5-flash", True, 1,
                                      100, 50)
            path = ledger.save()
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "test-save.json")
            loaded = RunLedger.load(path)
            self.assertEqual(loaded.run_id, "test-save")
            self.assertEqual(len(loaded.model_calls), 1)
            self.assertEqual(len(loaded.task_results), 1)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["run_id"], "test-save")


class TestLedgerSummary(unittest.TestCase):
    def _ledger(self):
        ledger = RunLedger(run_id="test-summary")
        ledger.record_task_result("task1_add_function", "lean",
                                  "gemini/gemini-2.5-flash", True, 1,
                                  100, 50, cost=None)
        ledger.record_task_result("task2_fix_off_by_one", "direct",
                                  "gemini/gemini-2.5-flash", False, 3,
                                  200, 100, cost=None)
        return ledger

    def test_summary_lean_vs_direct(self):
        info = self._ledger().summary()
        self.assertEqual(info["total_tasks"], 2)
        self.assertEqual(info["passed"], 1)
        self.assertEqual(info["failed"], 1)
        self.assertEqual(info["total_tokens"], 450)
        self.assertEqual(info["lean_tokens"], 150)
        self.assertEqual(info["direct_tokens"], 300)

    def test_tokens_per_passing_task_excludes_failed(self):
        info = self._ledger().summary()
        self.assertEqual(info["tokens_per_passing_task"], 150)

    def test_cost_total_unknown_when_any_unknown(self):
        info = self._ledger().summary()
        self.assertEqual(info["cost_total"], "unknown")

    def test_cost_total_known_when_all_known(self):
        ledger = RunLedger(run_id="test-cost")
        ledger.record_task_result("task1_add_function", "lean",
                                  "ollama/qwen2.5-coder", True, 1,
                                  100, 50, cost=0.0)
        ledger.record_task_result("task2_fix_off_by_one", "lean",
                                  "ollama/qwen2.5-coder", True, 1,
                                  80, 20, cost=0.0)
        self.assertEqual(ledger.summary()["cost_total"], 0.0)

    def test_tokens_per_passing_none_when_none_passed(self):
        ledger = RunLedger(run_id="test-none")
        ledger.record_task_result("task1_add_function", "lean",
                                  "gemini/gemini-2.5-flash", False, 3,
                                  100, 50)
        self.assertIsNone(ledger.summary()["tokens_per_passing_task"])

    def test_summary_text_has_task_lines(self):
        text = self._ledger().summary_text()
        self.assertIn("task1_add_function", text)
        self.assertIn("task2_fix_off_by_one", text)
        self.assertIn("Total: 2 tasks", text)
        self.assertIn("Tokens per passing task: 150", text)


class TestAgentLedgerWiring(unittest.TestCase):
    def test_agent_records_model_call_and_task_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            client = FakeClient([(MEDIAN_PATCH, 100, 50)])
            tools = SandboxTools(tmp)
            budget = TokenBudget(20000)
            approval = ApprovalGate(auto_approve=True)
            ledger = RunLedger(run_id="test-agent")
            agent = Agent(client, tools, budget, approval,
                          "gemini/gemini-2.5-flash", ledger=ledger)
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": False})
            self.assertTrue(result["passed"])
            self.assertEqual(len(ledger.model_calls), 1)
            self.assertEqual(ledger.model_calls[0]["total_tokens"], 150)
            self.assertIsNone(ledger.model_calls[0]["cost"])
            self.assertEqual(len(ledger.task_results), 1)
            self.assertTrue(ledger.task_results[0]["passed"])
            self.assertEqual(ledger.task_results[0]["total_tokens"], 150)

    def test_agent_records_approval_and_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            client = FakeClient([(MEDIAN_PATCH, 10, 5)])
            tools = SandboxTools(tmp)
            budget = TokenBudget(20000)
            approval = ApprovalGate(auto_approve=True)
            ledger = RunLedger(run_id="test-agent-2")
            agent = Agent(client, tools, budget, approval,
                          "gemini/gemini-2.5-flash", ledger=ledger)
            agent.run({"id": "task1_add_function",
                       "description": desc, "private": False})
            self.assertEqual(len(ledger.approvals), 1)
            self.assertTrue(ledger.approvals[0]["approved"])
            self.assertEqual(ledger.approvals[0]["mode"],
                             "demo auto-approve")
            self.assertEqual(len(ledger.patches), 1)
            self.assertEqual(ledger.patches[0]["file"], "mathutil.py")
            self.assertIn("def median", ledger.patches[0]["content"])

    def test_agent_records_test_result_and_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            client = FakeClient([(MEDIAN_PATCH, 10, 5)])
            tools = SandboxTools(tmp)
            budget = TokenBudget(20000)
            approval = ApprovalGate(auto_approve=True)
            ledger = RunLedger(run_id="test-agent-3")
            agent = Agent(client, tools, budget, approval,
                          "gemini/gemini-2.5-flash", ledger=ledger)
            agent.run({"id": "task1_add_function",
                       "description": desc, "private": False})
            self.assertEqual(len(ledger.test_results), 1)
            self.assertTrue(ledger.test_results[0]["passed"])
            actions = [e["action"] for e in ledger.tool_calls]
            self.assertIn("write_patch", actions)
            self.assertIn("run_tests", actions)
            self.assertIn("read_file", actions)

    def test_agent_local_model_cost_is_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            client = FakeClient([(MEDIAN_PATCH, 10, 5)])
            tools = SandboxTools(tmp)
            budget = TokenBudget(20000)
            approval = ApprovalGate(auto_approve=True)
            ledger = RunLedger(run_id="test-agent-4")
            agent = Agent(client, tools, budget, approval,
                          "ollama/qwen2.5-coder", ledger=ledger)
            agent.run({"id": "task1_add_function",
                       "description": desc, "private": False})
            self.assertEqual(ledger.task_results[0]["cost"], 0.0)

    def test_agent_private_refusal_records_zero_token_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            client = FakeClient([(MEDIAN_PATCH, 10, 5)])
            tools = SandboxTools(tmp)
            budget = TokenBudget(20000)
            approval = ApprovalGate(auto_approve=True)
            ledger = RunLedger(run_id="test-agent-5")
            agent = Agent(client, tools, budget, approval,
                          "gemini/gemini-2.5-flash", ledger=ledger)
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": True})
            self.assertFalse(result["passed"])
            self.assertEqual(len(ledger.model_calls), 0)
            self.assertEqual(len(ledger.task_results), 1)
            self.assertEqual(ledger.task_results[0]["total_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
