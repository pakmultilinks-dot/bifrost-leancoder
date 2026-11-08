"""Tests for the sandboxed tools."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from leancoder.tools import OutsideSandboxError, SandboxTools

ROOT = Path(__file__).resolve().parent.parent


class TestSandboxTools(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tools = SandboxTools(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_and_read(self):
        self.tools.write_patch("a.py", "x = 1\n")
        self.tools.write_patch("sub/b.py", "y = 2\n")
        self.assertIn("a.py", self.tools.list_files())
        self.assertIn("sub/b.py", self.tools.list_files())
        self.assertEqual(self.tools.read_file("a.py"), "x = 1\n")

    def test_search_code(self):
        self.tools.write_patch("a.py", "def total_upto(n):\n    pass\n")
        hits = self.tools.search_code("total_upto")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["file"], "a.py")

    def test_search_code_never_reads_hidden_tests(self):
        self.tools.write_patch("a.py", "def total_upto(n):\n    pass\n")
        self.tools.write_patch("hidden/test_hidden.py",
                               "def test_total_upto():\n    assert True\n")
        hits = self.tools.search_code("total_upto")
        self.assertEqual([h["file"] for h in hits], ["a.py"])
        read_targets = [e["target"] for e in self.tools.log
                        if e["action"] == "read_file"]
        self.assertNotIn("hidden/test_hidden.py", read_targets)

    def test_write_outside_sandbox_refused(self):
        with self.assertRaises(OutsideSandboxError):
            self.tools.write_patch("../evil.py", "bad\n")
        with self.assertRaises(OutsideSandboxError):
            self.tools.write_patch("/tmp/evil.py", "bad\n")

    def test_read_outside_sandbox_refused(self):
        with self.assertRaises(OutsideSandboxError):
            self.tools.read_file("../outside.py")

    def test_git_status_returns_string(self):
        status = self.tools.git_status()
        self.assertIsInstance(status, str)

    def test_run_tests_pass_and_fail(self):
        task = ROOT / "tasks" / "task1_add_function"
        for item in (task / "starter").rglob("*"):
            if item.is_file():
                target = Path(self.tmp.name) / item.relative_to(task / "starter")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(item, target)
        hidden = Path(self.tmp.name) / "hidden"
        shutil.copytree(task / "hidden", hidden)
        failed = self.tools.run_tests()
        self.assertFalse(failed["passed"])
        good = '''"""Small math helpers."""\n\n\ndef add(a, b):\n    """Return a plus b."""\n    return a + b\n\n\ndef subtract(a, b):\n    """Return a minus b."""\n    return a - b\n\n\ndef median(values):\n    """Return the median of a list of numbers."""\n    if not values:\n        raise ValueError("median of an empty list")\n    ordered = sorted(values)\n    n = len(ordered)\n    mid = n // 2\n    if n % 2:\n        return ordered[mid]\n    return (ordered[mid - 1] + ordered[mid]) / 2\n'''
        self.tools.write_patch("mathutil.py", good)
        passed = self.tools.run_tests()
        self.assertTrue(passed["passed"])
        self.assertEqual(passed["returncode"], 0)

    def test_git_commit_in_real_repo(self):
        if shutil.which("git") is None:
            self.skipTest("git not available")
        subprocess.run(["git", "init", "-q"], cwd=self.tmp.name, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"],
                       cwd=self.tmp.name, check=True)
        subprocess.run(["git", "config", "user.name", "Test"],
                       cwd=self.tmp.name, check=True)
        self.tools.write_patch("a.py", "x = 1\n")
        result = self.tools.git_commit("first commit")
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
