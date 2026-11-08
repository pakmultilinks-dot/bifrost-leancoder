"""Judge verification for LeanCoder, offline, no key, no Docker,
no Bifrost needed. Runs the full unit test suite, then replays every
recorded trace: re-applies the patches, runs the hidden tests, and
checks the ledger numbers. Prints PASS or FAIL with the measured
numbers, and exits 0 only when everything passes.

Runs in under 2 minutes. A live agent run from zero is NOT under
5 minutes, because it needs Bifrost and Ollama running and a model
downloaded. This script verifies the recorded runs instead.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_unit_tests(tests_dir):
    """Run the unit test suite. Returns (ran, failed, output)."""
    env = dict(os.environ)
    env["LEANCODER_VERIFY_NESTED"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s",
         str(tests_dir), "-v"],
        cwd=ROOT, capture_output=True, text=True, timeout=300, env=env)
    output = (result.stdout or "") + (result.stderr or "")
    ran = 0
    match = re.search(r"Ran (\d+) tests?", output)
    if match:
        ran = int(match.group(1))
    failed = result.returncode != 0
    return ran, failed, output


def check_traces(traces_dir, tasks_dir):
    """Replay every recorded trace. Returns (report lines, all matched)."""
    from leancoder.replay import replay_ledger

    traces_dir = Path(traces_dir)
    files = sorted(traces_dir.glob("*.json")) if traces_dir.is_dir() else []
    if not files:
        return (["Traces: no recorded traces found, replay skipped."],
                True, 0, 0)
    lines = []
    all_matched = True
    total_tasks = 0
    total_matched = 0
    for trace_file in files:
        report = replay_ledger(trace_file, tasks_dir=str(tasks_dir))
        total_tasks += report["checked"]
        total_matched += report["matched"]
        if not report["overall_match"]:
            all_matched = False
        lines.append("Trace " + trace_file.name + ": "
                     + str(report["matched"]) + " of "
                     + str(report["checked"]) + " tasks matched.")
        for task in report["tasks"]:
            if not task["match"]:
                for difference in task["differences"]:
                    lines.append("  Mismatch in " + task["task_id"] + ": "
                                 + difference)
    return lines, all_matched, total_tasks, total_matched


def main(argv=None):
    parser = argparse.ArgumentParser(description="LeanCoder verification")
    parser.add_argument("--traces-dir", default="traces")
    parser.add_argument("--tests-dir", default="tests")
    parser.add_argument("--tasks-dir", default="tasks")
    args = parser.parse_args(argv)

    start = time.time()
    print("LeanCoder verification")
    ran, tests_failed, _output = run_unit_tests(args.tests_dir)
    print("Unit tests: " + str(ran) + " run, "
          + ("FAILED" if tests_failed else "passed"))
    trace_lines, traces_matched, total_tasks, total_matched = check_traces(
        args.traces_dir, args.tasks_dir)
    for line in trace_lines:
        print(line)
    print("Tasks replayed: " + str(total_tasks) + ", matched: "
          + str(total_matched))
    elapsed = time.time() - start
    print("Elapsed: " + str(round(elapsed, 1)) + " seconds")
    ok = (not tests_failed) and traces_matched
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
