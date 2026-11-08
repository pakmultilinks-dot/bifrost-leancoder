"""The LeanCoder agent loop.

Plan, read files with tools, propose a patch, show the diff and ask
for approval, apply only after approval, run the tests, retry at
most 5 times, then report tokens and cost. Lean mode sends only the
files the task needs, found by local code search. Direct mode sends
the whole repo context on every model call. After a failed test run,
the failing test output is sent back to the model, and the files
are re-read so the next patch is written against the current file
state, not the original one.
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
from pathlib import Path

from .approval import ApprovalGate
from .bifrost_client import BifrostClient, BifrostError
from .budget import BudgetExceeded, TokenBudget
from .ledger import RunLedger
from .tools import SandboxTools

MAX_STEPS = 5
STOPWORDS = {
    "the", "and", "with", "into", "that", "this", "from", "your",
    "task", "write", "make", "function", "test", "tests",
}


def parse_patch(text):
    """Extract FILE: blocks from a model reply.

    Expected format, one block per file:
        FILE: mathutil.py
        ```python
        <new file content>
        ```
    Returns a dict of relative path to new content. Empty if no block.
    """
    patches = {}
    current = None
    buf = []
    for line in (text or "").splitlines():
        match = re.match(r"^FILE:\s*(\S+)\s*$", line.strip())
        if match:
            if current is not None:
                patches[current] = "\n".join(buf).strip() + "\n"
            current = match.group(1)
            buf = []
            continue
        if current is not None:
            if line.strip() in ("```", "```python"):
                continue
            buf.append(line)
    if current is not None:
        patches[current] = "\n".join(buf).strip() + "\n"
    return patches


def _keywords(description):
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", description or "")
    seen = []
    for word in words:
        low = word.lower()
        if len(low) > 3 and low not in STOPWORDS and low not in seen:
            seen.append(low)
    return seen


class Agent:
    """Run one task with one model, one budget, one approval gate."""

    def __init__(self, client, tools, budget, approval, model,
                 mode="lean", max_steps=MAX_STEPS, ledger=None):
        if mode not in ("lean", "direct"):
            raise ValueError("mode must be lean or direct")
        self.client = client
        self.tools = tools
        self.budget = budget
        self.approval = approval
        self.model = model
        self.mode = mode
        self.max_steps = max_steps
        self.ledger = ledger

    def _cost_for_call(self):
        """Local models cost 0. Remote cost is unknown, never invented."""
        return 0.0 if self._is_local_model() else None

    def _finish(self, result):
        """Record the finished task in the ledger, then return it."""
        if self.ledger is not None:
            for entry in self.tools.log:
                self.ledger.record_tool_call(
                    entry["action"], entry["target"], entry["ok"],
                    entry.get("detail", ""))
            trace = result.get("trace") or []
            estimated = any(t.get("estimated") for t in trace)
            self.ledger.record_task_result(
                task_id=result["task_id"], mode=self.mode,
                model=self.model, passed=result["passed"],
                steps=result["steps"],
                prompt_tokens=result["prompt_tokens"],
                completion_tokens=result["completion_tokens"],
                cost=self._cost_for_call(),
                error=result.get("error", ""), estimated=estimated)
        return result

    def _is_local_model(self):
        return self.model.startswith("ollama/")

    def _gather_context(self, task):
        files = [f for f in self.tools.list_files()
                 if f.endswith(".py") and not f.startswith("hidden/")]
        if self.mode == "direct":
            return {f: self.tools.read_file(f) for f in files}
        context = {}
        for keyword in _keywords(task.get("description", "")):
            for hit in self.tools.search_code(keyword):
                if hit["file"] not in context and hit["file"] in files:
                    context[hit["file"]] = self.tools.read_file(hit["file"])
        if not context and files:
            context[files[0]] = self.tools.read_file(files[0])
        return context

    def _prompt(self, task, context, feedback=""):
        parts = [
            "Complete this development task. Reply with one FILE: block "
            "per file you change, with the full new file content.",
            "Task: " + task.get("description", ""),
            "Files:",
        ]
        for name, text in context.items():
            parts.append("FILE: " + name + "\n" + text)
        if feedback:
            parts.append("Previous attempt failed. Fix this:\n" + feedback)
        return [{"role": "user", "content": "\n\n".join(parts)}]

    def run(self, task):
        """Run one task. Returns a result dict, never raises on task failure."""
        trace = []
        if task.get("private") and not self._is_local_model():
            return self._finish({
                "task_id": task.get("id", ""), "passed": False,
                "steps": 0, "total_tokens": 0,
                "prompt_tokens": 0, "completion_tokens": 0,
                "error": "Private task refused: private code runs only on "
                         "a local model, and the configured model is not "
                         "local. Use an ollama/ model.",
                "trace": trace,
            })
        context = self._gather_context(task)
        feedback = ""
        for step in range(1, self.max_steps + 1):
            if step > 1:
                # Re-read the files so the model sees the current state
                # after its own patch, not the original starter files.
                context = self._gather_context(task)
            messages = self._prompt(task, context, feedback)
            try:
                result = self.client.chat(messages, model=self.model)
            except BifrostError as exc:
                return self._finish({
                    "task_id": task.get("id", ""), "passed": False,
                    "steps": step, "total_tokens": self.budget.total_tokens,
                    "prompt_tokens": self.budget.prompt_tokens,
                    "completion_tokens": self.budget.completion_tokens,
                    "error": str(exc), "trace": trace,
                })
            try:
                self.budget.add(result.prompt_tokens, result.completion_tokens)
            except BudgetExceeded as exc:
                return self._finish({
                    "task_id": task.get("id", ""), "passed": False,
                    "steps": step, "total_tokens": self.budget.total_tokens,
                    "prompt_tokens": self.budget.prompt_tokens,
                    "completion_tokens": self.budget.completion_tokens,
                    "error": str(exc), "trace": trace,
                })
            if self.ledger is not None:
                self.ledger.record_model_call(
                    task.get("id", ""), self.mode, result.model,
                    result.prompt_tokens, result.completion_tokens,
                    cost=self._cost_for_call(), estimated=result.estimated)
            trace.append({"step": step, "model": result.model,
                          "prompt_tokens": result.prompt_tokens,
                          "completion_tokens": result.completion_tokens,
                          "estimated": result.estimated})
            patches = parse_patch(result.content)
            if not patches:
                feedback = "No FILE: patch block was found in the reply. Send the full new file content in a FILE: block."
                continue
            for relpath, new_content in patches.items():
                try:
                    old = self.tools.read_file(relpath)
                except OSError:
                    old = ""
                diff = "\n".join(difflib.unified_diff(
                    old.splitlines(), new_content.splitlines(),
                    fromfile="a/" + relpath, tofile="b/" + relpath))
                approved = self.approval.request(
                    "write_patch", "Write file " + relpath, diff)
                if self.ledger is not None:
                    self.ledger.record_approval(
                        "write_patch", "Write file " + relpath, approved,
                        mode=("demo auto-approve"
                              if self.approval.auto_approve else "manual"))
                if not approved:
                    return self._finish({
                        "task_id": task.get("id", ""), "passed": False,
                        "steps": step,
                        "total_tokens": self.budget.total_tokens,
                        "prompt_tokens": self.budget.prompt_tokens,
                        "completion_tokens": self.budget.completion_tokens,
                        "error": "Approval denied for " + relpath,
                        "trace": trace,
                    })
                self.tools.write_patch(relpath, new_content)
                if self.ledger is not None:
                    self.ledger.record_patch(
                        task.get("id", ""), step, relpath, new_content)
            trace[-1]["patches"] = patches
            test_result = self.tools.run_tests()
            if self.ledger is not None:
                self.ledger.record_test_result(
                    task.get("id", ""), test_result["passed"],
                    test_result.get("returncode"),
                    test_result.get("output", ""))
            if test_result["passed"]:
                return self._finish({
                    "task_id": task.get("id", ""), "passed": True,
                    "steps": step, "total_tokens": self.budget.total_tokens,
                    "prompt_tokens": self.budget.prompt_tokens,
                    "completion_tokens": self.budget.completion_tokens,
                    "error": "", "trace": trace,
                })
            feedback = "Tests failed:\n" + test_result["output"][-1500:]
        return self._finish({
            "task_id": task.get("id", ""), "passed": False,
            "steps": self.max_steps, "total_tokens": self.budget.total_tokens,
            "prompt_tokens": self.budget.prompt_tokens,
            "completion_tokens": self.budget.completion_tokens,
            "error": "Max steps reached without passing tests.",
            "trace": trace,
        })


def main(argv=None):
    parser = argparse.ArgumentParser(description="LeanCoder agent")
    parser.add_argument("--task", required=True, help="Task id, for example task1_add_function")
    parser.add_argument("--mode", default="lean", choices=["lean", "direct"])
    parser.add_argument("--model", default=None, help="Model in provider/model form")
    parser.add_argument("--budget", type=int, default=20000, help="Per-task token budget")
    parser.add_argument("--auto-approve", action="store_true",
                        help="Demo mode only: approve writes without asking")
    parser.add_argument("--tasks-dir", default="tasks")
    parser.add_argument("--work-dir", default=None,
                        help="Sandbox copy of the task starter files")
    parser.add_argument("--ledger-dir", default="traces",
                        help="Directory for the run ledger JSON file")
    args = parser.parse_args(argv)

    task_dir = Path(args.tasks_dir) / args.task
    desc_file = task_dir / "task.md"
    if not desc_file.exists():
        raise SystemExit("Task not found: " + str(task_dir))
    description = desc_file.read_text(encoding="utf-8")
    private = "PRIVATE" in description
    work = Path(args.work_dir) if args.work_dir else Path("sandbox") / args.task
    starter = task_dir / "starter"
    hidden = task_dir / "hidden"
    work.mkdir(parents=True, exist_ok=True)
    for item in starter.rglob("*"):
        if item.is_file():
            target = work / item.relative_to(starter)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
    hidden_target = work / "hidden"
    hidden_target.mkdir(parents=True, exist_ok=True)
    for item in hidden.rglob("*"):
        if item.is_file():
            target = hidden_target / item.relative_to(hidden)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")

    client = BifrostClient(model=args.model)
    tools = SandboxTools(work)
    budget = TokenBudget(args.budget)
    approval = ApprovalGate(auto_approve=args.auto_approve)
    if args.auto_approve:
        print("Demo mode: auto-approve is ON. Approval is normally required.")
    ledger = RunLedger(traces_dir=args.ledger_dir)
    agent = Agent(client, tools, budget, approval,
                  model=args.model or os.environ.get("BIFROST_MODEL", ""),
                  mode=args.mode, ledger=ledger)
    result = agent.run({"id": args.task, "description": description,
                        "private": private})
    ledger_path = ledger.save()
    print("Task:", result["task_id"], "passed:", result["passed"])
    print("Steps:", result["steps"], "total tokens:", result["total_tokens"])
    if result["error"]:
        print("Error:", result["error"])
    print("Ledger:", str(ledger_path))
    print(ledger.summary_text())
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
