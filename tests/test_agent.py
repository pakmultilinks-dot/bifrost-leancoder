"""Tests for the agent loop. The model is mocked, no live call."""
import shutil
import tempfile
import unittest
from pathlib import Path

from leancoder.agent import Agent, parse_patch
from leancoder.approval import ApprovalGate
from leancoder.bifrost_client import ChatResult
from leancoder.budget import TokenBudget
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

WRONG_PATCH = """FILE: mathutil.py
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
    return 0
```
"""


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, model=None):
        self.calls.append(messages)
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


class TestParsePatch(unittest.TestCase):
    def test_extracts_file_block(self):
        patches = parse_patch(MEDIAN_PATCH)
        self.assertIn("mathutil.py", patches)
        self.assertIn("def median", patches["mathutil.py"])

    def test_no_block_is_empty(self):
        self.assertEqual(parse_patch("hello, no patch here"), {})


class TestAgent(unittest.TestCase):
    def _make_agent(self, tmp, replies, budget=20000, auto_approve=True,
                    model="gemini/gemini-2.5-flash", mode="lean", max_steps=3):
        client = FakeClient(replies)
        tools = SandboxTools(tmp)
        budget_obj = TokenBudget(budget)
        approval = ApprovalGate(auto_approve=auto_approve)
        agent = Agent(client, tools, budget_obj, approval, model,
                      mode=mode, max_steps=max_steps)
        return agent, client, budget_obj

    def test_passing_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            agent, client, budget = self._make_agent(
                tmp, [(MEDIAN_PATCH, 100, 50)])
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": False})
            self.assertTrue(result["passed"])
            self.assertEqual(result["total_tokens"], 150)
            self.assertEqual(len(client.calls), 1)

    def test_failing_task_reports_not_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            agent, client, budget = self._make_agent(
                tmp, [(WRONG_PATCH, 10, 5)], max_steps=1)
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": False})
            self.assertFalse(result["passed"])
            self.assertEqual(result["steps"], 1)

    def test_no_patch_reply_retries_then_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            agent, client, budget = self._make_agent(
                tmp, [("hello", 10, 5)], max_steps=1)
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": False})
            self.assertFalse(result["passed"])

    def test_budget_exceeded_stops_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            agent, client, budget = self._make_agent(
                tmp, [(MEDIAN_PATCH, 100, 50)], budget=100)
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": False})
            self.assertFalse(result["passed"])
            self.assertIn("budget", result["error"].lower())

    def test_approval_denied_stops_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            client = FakeClient([(MEDIAN_PATCH, 10, 5)])
            tools = SandboxTools(tmp)
            budget = TokenBudget(20000)
            approval = ApprovalGate(input_fn=lambda prompt: "n")
            agent = Agent(client, tools, budget, approval,
                          "gemini/gemini-2.5-flash")
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": False})
            self.assertFalse(result["passed"])
            self.assertIn("Approval denied", result["error"])

    def test_private_task_refused_for_remote_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            client = FakeClient([(MEDIAN_PATCH, 10, 5)])
            tools = SandboxTools(tmp)
            budget = TokenBudget(20000)
            approval = ApprovalGate(auto_approve=True)
            agent = Agent(client, tools, budget, approval,
                          "gemini/gemini-2.5-flash")
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": True})
            self.assertFalse(result["passed"])
            self.assertIn("local", result["error"])
            self.assertEqual(len(client.calls), 0)

    def test_private_task_allowed_for_local_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            agent, client, budget = self._make_agent(
                tmp, [(MEDIAN_PATCH, 10, 5)], model="ollama/qwen2.5-coder")
            result = agent.run({"id": "task1_add_function",
                                "description": desc, "private": True})
            self.assertTrue(result["passed"])
            self.assertEqual(len(client.calls), 1)

    def test_lean_context_is_smaller_than_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            desc = _setup_task1(tmp)
            tools = SandboxTools(tmp)
            tools.write_patch("unrelated.py", "UNRELATED_MARKER = 1\n")
            client = FakeClient([(MEDIAN_PATCH, 10, 5)])
            budget = TokenBudget(20000)
            approval = ApprovalGate(auto_approve=True)
            lean = Agent(client, tools, budget, approval,
                         "gemini/gemini-2.5-flash", mode="lean")
            context = lean._gather_context(
                {"description": "Add a pure function median to mathutil.py"})
            joined = "\n".join(context.values())
            self.assertIn("def add", joined)
            self.assertNotIn("UNRELATED_MARKER", joined)
            direct = Agent(client, tools, TokenBudget(20000), approval,
                           "gemini/gemini-2.5-flash", mode="direct")
            direct_context = direct._gather_context({"description": "x"})
            self.assertIn("UNRELATED_MARKER",
                          "\n".join(direct_context.values()))


if __name__ == "__main__":
    unittest.main()
