"""Token ledger: one JSON record per run, never invented numbers.

Every model call, tool call, test result, approval decision, applied
patch, and task result is recorded. Cost is recorded only when it is
known: a local model costs 0, a priced remote model records the price
it reports, and anything else is recorded as unknown, never guessed.
The ledger file lives under traces/, which is gitignored, so a run
record is never committed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class RunLedger:
    """Collect one run, then save it as one JSON file under traces/."""

    def __init__(self, run_id=None, traces_dir="traces"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.run_id = run_id or ("run-" + stamp)
        self.traces_dir = Path(traces_dir)
        self.created_at = _utc_now()
        self.model_calls = []
        self.tool_calls = []
        self.test_results = []
        self.approvals = []
        self.patches = []
        self.task_results = []

    def record_model_call(self, task_id, mode, model, prompt_tokens,
                          completion_tokens, cost=None, estimated=False):
        """Record one model call. cost None means the cost is unknown."""
        entry = {
            "task_id": task_id, "mode": mode, "model": model,
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(prompt_tokens) + int(completion_tokens),
            "cost": cost, "estimated": bool(estimated),
        }
        self.model_calls.append(entry)
        return entry

    def record_tool_call(self, action, target, ok=True, detail=""):
        entry = {"action": action, "target": str(target),
                 "ok": bool(ok), "detail": detail or ""}
        self.tool_calls.append(entry)
        return entry

    def record_test_result(self, task_id, passed, returncode=None,
                           output=""):
        entry = {"task_id": task_id, "passed": bool(passed),
                 "returncode": returncode, "output": (output or "")[-500:]}
        self.test_results.append(entry)
        return entry

    def record_approval(self, kind, summary, approved, mode="manual"):
        entry = {"kind": kind, "summary": summary,
                 "approved": bool(approved), "mode": mode}
        self.approvals.append(entry)
        return entry

    def record_patch(self, task_id, step, relpath, content):
        entry = {"task_id": task_id, "step": int(step),
                 "file": relpath, "content": content}
        self.patches.append(entry)
        return entry

    def record_task_result(self, task_id, mode, model, passed, steps,
                           prompt_tokens, completion_tokens, cost=None,
                           error="", estimated=False):
        """Record one finished task. cost None means the cost is unknown."""
        entry = {
            "task_id": task_id, "mode": mode, "model": model,
            "passed": bool(passed), "steps": int(steps),
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(prompt_tokens) + int(completion_tokens),
            "cost": cost, "error": error or "",
            "estimated": bool(estimated),
        }
        self.task_results.append(entry)
        return entry

    def to_dict(self):
        return {
            "run_id": self.run_id, "created_at": self.created_at,
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "test_results": self.test_results,
            "approvals": self.approvals,
            "patches": self.patches,
            "task_results": self.task_results,
        }

    @classmethod
    def from_dict(cls, data):
        ledger = cls(run_id=data.get("run_id", "unknown"),
                     traces_dir="traces")
        ledger.created_at = data.get("created_at", "")
        ledger.model_calls = list(data.get("model_calls") or [])
        ledger.tool_calls = list(data.get("tool_calls") or [])
        ledger.test_results = list(data.get("test_results") or [])
        ledger.approvals = list(data.get("approvals") or [])
        ledger.patches = list(data.get("patches") or [])
        ledger.task_results = list(data.get("task_results") or [])
        return ledger

    def save(self):
        """Write the ledger as traces/<run_id>.json. Returns the path."""
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        path = self.traces_dir / (self.run_id + ".json")
        path.write_text(json.dumps(self.to_dict(), indent=2),
                        encoding="utf-8")
        return path

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def summary(self):
        """Measured totals. Cost is 'unknown' when any cost is unknown."""
        per_task = []
        for task in self.task_results:
            per_task.append({
                "task_id": task["task_id"], "mode": task["mode"],
                "model": task["model"], "passed": task["passed"],
                "steps": task["steps"],
                "prompt_tokens": task["prompt_tokens"],
                "completion_tokens": task["completion_tokens"],
                "total_tokens": task["total_tokens"],
                "cost": task.get("cost"),
                "tokens_per_passing_task": (
                    task["total_tokens"] if task["passed"] else None),
            })
        total_tokens = sum(t["total_tokens"] for t in self.task_results)
        lean_tokens = sum(t["total_tokens"] for t in self.task_results
                          if t["mode"] == "lean")
        direct_tokens = sum(t["total_tokens"] for t in self.task_results
                            if t["mode"] == "direct")
        passed = [t for t in self.task_results if t["passed"]]
        tokens_per_passing = None
        if passed:
            tokens_per_passing = (
                sum(t["total_tokens"] for t in passed) // len(passed))
        costs = [t.get("cost") for t in self.task_results]
        if costs and all(c is not None for c in costs):
            cost_total = round(sum(float(c) for c in costs), 6)
        else:
            cost_total = "unknown"
        return {
            "run_id": self.run_id,
            "per_task": per_task,
            "total_tasks": len(self.task_results),
            "passed": len(passed),
            "failed": len(self.task_results) - len(passed),
            "total_tokens": total_tokens,
            "lean_tokens": lean_tokens,
            "direct_tokens": direct_tokens,
            "tokens_per_passing_task": tokens_per_passing,
            "cost_total": cost_total,
            "estimated_calls": sum(
                1 for c in self.model_calls if c.get("estimated")),
        }

    def summary_text(self):
        """Plain text summary, one line per task plus totals."""
        info = self.summary()
        lines = ["LeanCoder token ledger, run " + info["run_id"]]
        for task in info["per_task"]:
            cost = task["cost"]
            cost_text = "unknown" if cost is None else str(cost)
            lines.append(
                "Task " + task["task_id"] + " (" + task["mode"] + ", "
                + task["model"] + "): "
                + ("passed" if task["passed"] else "failed") + ", "
                + str(task["total_tokens"]) + " tokens, cost " + cost_text)
        lines.append(
            "Total: " + str(info["total_tasks"]) + " tasks, "
            + str(info["passed"]) + " passed, "
            + str(info["failed"]) + " failed, "
            + str(info["total_tokens"]) + " tokens "
            + "(lean " + str(info["lean_tokens"]) + ", direct "
            + str(info["direct_tokens"]) + ")")
        passing = info["tokens_per_passing_task"]
        lines.append("Tokens per passing task: "
                     + ("none passed" if passing is None else str(passing)))
        lines.append("Cost total: " + str(info["cost_total"]))
        lines.append("Estimated model calls: "
                     + str(info["estimated_calls"]))
        return "\n".join(lines)
