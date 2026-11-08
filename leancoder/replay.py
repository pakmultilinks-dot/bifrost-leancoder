"""Replay a recorded run offline: re-apply the recorded patches to a
fresh copy of the starter code, run the hidden tests, and check the
ledger numbers match the trace. No model call, no key, no network.
A difference is reported plainly, never silently fixed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class TraceError(ValueError):
    """Raised when a trace file is missing, unreadable, or incomplete."""


REQUIRED_KEYS = ("run_id", "task_results", "model_calls", "patches")


def load_trace(path):
    """Load a ledger JSON file. Raises TraceError on any problem."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TraceError("Cannot read trace file " + str(path)
                         + ": " + str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise TraceError("Trace file " + str(path)
                         + " is not valid JSON: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise TraceError("Trace file " + str(path)
                         + " does not hold a JSON object.")
    for key in REQUIRED_KEYS:
        if key not in data:
            raise TraceError("Trace file " + str(path)
                             + " is missing the key: " + key)
    return data


def _copy_task(task_id, tasks_dir, work):
    task = Path(tasks_dir) / task_id
    starter = task / "starter"
    hidden = task / "hidden"
    if not starter.is_dir() or not hidden.is_dir():
        raise TraceError("Task not found or incomplete: " + str(task))
    for item in starter.rglob("*"):
        if item.is_file():
            target = work / item.relative_to(starter)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(item, target)
    shutil.copytree(hidden, work / "hidden")


def _run_hidden(work):
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "hidden", "-v"],
        cwd=work, capture_output=True, text=True, timeout=120)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def replay_task(task_id, data, tasks_dir="tasks"):
    """Replay one recorded task. Returns a report dict."""
    task_results = [t for t in data.get("task_results") or []
                    if t.get("task_id") == task_id]
    if not task_results:
        return {"task_id": task_id, "match": False,
                "differences": ["No task result for " + task_id
                                + " in the trace."]}
    expected = task_results[0]
    differences = []
    calls = [c for c in data.get("model_calls") or []
             if c.get("task_id") == task_id]
    recorded_tokens = sum(int(c.get("total_tokens") or 0) for c in calls)
    if recorded_tokens != int(expected.get("total_tokens") or 0):
        differences.append(
            "Ledger token total " + str(expected.get("total_tokens"))
            + " does not match the sum of model calls "
            + str(recorded_tokens) + ".")
    patches = {}
    for patch in data.get("patches") or []:
        if patch.get("task_id") == task_id:
            patches[patch.get("file")] = patch.get("content", "")
    if not patches and expected.get("passed"):
        differences.append(
            "Task is recorded as passed, but no patch was recorded.")
    replay_passed = False
    if patches:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            try:
                _copy_task(task_id, tasks_dir, work)
            except TraceError as exc:
                differences.append(str(exc))
                return {"task_id": task_id, "match": False,
                        "expected_passed": bool(expected.get("passed")),
                        "replay_passed": False,
                        "expected_tokens": expected.get("total_tokens"),
                        "recorded_tokens": recorded_tokens,
                        "differences": differences}
            for relpath, content in patches.items():
                target = work / relpath
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            replay_passed, _output = _run_hidden(work)
    if replay_passed != bool(expected.get("passed")):
        differences.append(
            "Replayed hidden tests "
            + ("passed" if replay_passed else "failed")
            + ", but the trace records the task as "
            + ("passed" if expected.get("passed") else "failed") + ".")
    return {
        "task_id": task_id,
        "match": not differences,
        "expected_passed": bool(expected.get("passed")),
        "replay_passed": replay_passed,
        "expected_tokens": expected.get("total_tokens"),
        "recorded_tokens": recorded_tokens,
        "differences": differences,
    }


def replay_ledger(path, tasks_dir="tasks"):
    """Replay every task in a trace file. Returns an overall report."""
    data = load_trace(path)
    results = []
    for task in data.get("task_results") or []:
        results.append(replay_task(task.get("task_id"), data,
                                   tasks_dir=tasks_dir))
    return {
        "run_id": data.get("run_id"),
        "tasks": results,
        "checked": len(results),
        "matched": sum(1 for r in results if r["match"]),
        "overall_match": all(r["match"] for r in results),
    }


def replay_summary_text(report):
    """Plain text summary of a replay report."""
    lines = ["Replay of run " + str(report.get("run_id")) + ": "
             + str(report.get("matched")) + " of "
             + str(report.get("checked")) + " tasks matched."]
    for task in report.get("tasks") or []:
        status = "match" if task["match"] else "MISMATCH"
        lines.append("Task " + task["task_id"] + ": " + status
                     + " (recorded "
                     + ("passed" if task["expected_passed"] else "failed")
                     + ", replay "
                     + ("passed" if task["replay_passed"] else "failed")
                     + ")")
        for difference in task.get("differences") or []:
            lines.append("  Difference: " + difference)
    return "\n".join(lines)
