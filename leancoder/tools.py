"""Sandboxed tools for the agent.

Read-only tools need no approval: list_files, read_file,
search_code, git_status. Write tools go through write_patch,
run_tests, and git_commit, and the agent must get approval before
calling them. Every write is confined to the sandbox repo path,
and every action is logged.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


class OutsideSandboxError(ValueError):
    """Raised when a tool is asked to touch a path outside the sandbox."""


class SandboxTools:
    """File, shell, and Git tools confined to one sandbox repo."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.log = []

    def _record(self, action, target, ok=True, detail=""):
        entry = {"action": action, "target": str(target),
                 "ok": ok, "detail": detail}
        self.log.append(entry)
        return entry

    def _inside(self, relpath):
        target = (self.root / relpath).resolve()
        if target != self.root and self.root not in target.parents:
            raise OutsideSandboxError(
                "Refused: " + str(relpath) + " is outside the sandbox repo.")
        return target

    def list_files(self, subdir="."):
        base = self._inside(subdir)
        found = []
        for path in sorted(base.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                found.append(str(path.relative_to(self.root)))
        self._record("list_files", subdir)
        return found

    def read_file(self, relpath):
        target = self._inside(relpath)
        text = target.read_text(encoding="utf-8")
        self._record("read_file", relpath)
        return text

    def search_code(self, needle, subdir="."):
        """Small local code search, case-insensitive substring match."""
        needle = (needle or "").lower()
        hits = []
        for rel in self.list_files(subdir):
            if not rel.endswith(".py"):
                continue
            try:
                text = self.read_file(rel)
            except (OSError, UnicodeDecodeError):
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                if needle and needle in line.lower():
                    hits.append({"file": rel, "line": line_no,
                                 "text": line.strip()})
        self._record("search_code", needle)
        return hits

    def git_status(self):
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"], cwd=self.root,
                capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            self._record("git_status", self.root, ok=False,
                         detail="git not available")
            return "git not available"
        self._record("git_status", self.root)
        return result.stdout.strip() or "clean"

    def write_patch(self, relpath, new_content):
        """Write one file inside the sandbox, through this method only."""
        target = self._inside(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content, encoding="utf-8")
        self._record("write_patch", relpath)
        return str(target)

    def run_tests(self, command=None):
        """Run the hidden test suite inside the sandbox, capture output."""
        cmd = command or ["python3", "-m", "unittest", "discover",
                          "-s", "hidden", "-v"]
        try:
            result = subprocess.run(
                cmd, cwd=self.root, capture_output=True, text=True,
                timeout=120)
        except subprocess.SubprocessError as exc:
            self._record("run_tests", " ".join(cmd), ok=False, detail=str(exc))
            return {"passed": False, "returncode": -1, "output": str(exc)}
        output = (result.stdout or "") + (result.stderr or "")
        passed = result.returncode == 0
        self._record("run_tests", " ".join(cmd), ok=passed, detail=output[-500:])
        return {"passed": passed, "returncode": result.returncode,
                "output": output}

    def git_commit(self, message):
        try:
            add = subprocess.run(
                ["git", "add", "-A"], cwd=self.root,
                capture_output=True, text=True, timeout=30)
            commit = subprocess.run(
                ["git", "commit", "-m", message], cwd=self.root,
                capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            self._record("git_commit", message, ok=False, detail=str(exc))
            return {"ok": False, "output": str(exc)}
        output = (add.stdout or "") + (commit.stdout or "") + (commit.stderr or "")
        ok = commit.returncode == 0
        self._record("git_commit", message, ok=ok, detail=output[-500:])
        return {"ok": ok, "output": output}
