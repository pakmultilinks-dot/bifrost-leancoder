"""Tests for the task pack: hidden tests fail on the starter,
and pass on a correct reference solution. No live call."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REFERENCE = {
    "task1_add_function": {
        "mathutil.py": '''"""Small math helpers."""\n\n\ndef add(a, b):\n    """Return a plus b."""\n    return a + b\n\n\ndef subtract(a, b):\n    """Return a minus b."""\n    return a - b\n\n\ndef median(values):\n    """Return the median of a list of numbers."""\n    if not values:\n        raise ValueError("median of an empty list")\n    ordered = sorted(values)\n    n = len(ordered)\n    mid = n // 2\n    if n % 2:\n        return ordered[mid]\n    return (ordered[mid - 1] + ordered[mid]) / 2\n''',
    },
    "task2_fix_off_by_one": {
        "counter.py": '''"""Counting helpers."""\n\n\ndef total_upto(n):\n    """Return 1 + 2 + ... + n."""\n    total = 0\n    for i in range(1, n + 1):\n        total += i\n    return total\n''',
    },
    "task3_write_tests": {
        "tests/test_stringutil.py": '''"""Tests for slugify."""\nimport os\nimport sys\nimport unittest\n\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n\nfrom stringutil import slugify\n\n\nclass TestSlugify(unittest.TestCase):\n    def test_two_words(self):\n        self.assertEqual(slugify("Hello World"), "hello-world")\n\n    def test_extra_spaces(self):\n        self.assertEqual(slugify("  A  B  "), "a-b")\n\n    def test_already_slug(self):\n        self.assertEqual(slugify("hello"), "hello")\n\n\nif __name__ == "__main__":\n    unittest.main()\n''',
    },
    "task4_refactor_dupe": {
        "pricing.py": '''"""Pricing helpers, 20 percent tax."""\n\n\ndef add_tax(amount):\n    """Add 20 percent tax, round to 2 decimals."""\n    return round(amount * 1.20, 2)\n\n\ndef price_with_tax(amount):\n    """Add 20 percent tax, round to 2 decimals."""\n    return add_tax(amount)\n\n\ndef price_with_discount(amount, percent):\n    """Apply a percent discount, then add 20 percent tax."""\n    discount = amount * (percent / 100)\n    after = amount - discount\n    return add_tax(after)\n''',
    },
    "task5_input_validation": {
        "validate.py": '''"""Input validation helpers."""\n\n\ndef parse_age(value):\n    """Parse an age string into an int."""\n    if value is None or str(value).strip() == "":\n        raise ValueError("age must not be empty")\n    try:\n        age = int(value)\n    except (TypeError, ValueError):\n        raise ValueError("age must be a whole number") from None\n    if age < 0:\n        raise ValueError("age cannot be negative")\n    if age > 150:\n        raise ValueError("age cannot be over 150")\n    return age\n''',
    },
}


def _copy_task(task_id, tmp):
    task = ROOT / "tasks" / task_id
    for item in (task / "starter").rglob("*"):
        if item.is_file():
            target = Path(tmp) / item.relative_to(task / "starter")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(item, target)
    shutil.copytree(task / "hidden", Path(tmp) / "hidden")


def _run_hidden(tmp):
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "hidden", "-v"],
        cwd=tmp, capture_output=True, text=True, timeout=120)


class TestTaskPack(unittest.TestCase):
    def test_all_five_tasks_exist(self):
        for task_id in REFERENCE:
            task = ROOT / "tasks" / task_id
            self.assertTrue((task / "task.md").exists(), task_id)
            self.assertTrue((task / "starter").is_dir(), task_id)
            self.assertTrue((task / "hidden" / "test_hidden.py").exists(),
                            task_id)

    def test_hidden_fails_on_starter(self):
        for task_id in REFERENCE:
            with tempfile.TemporaryDirectory() as tmp:
                _copy_task(task_id, tmp)
                result = _run_hidden(tmp)
                self.assertNotEqual(result.returncode, 0, task_id)

    def test_hidden_passes_on_reference_solution(self):
        for task_id, files in REFERENCE.items():
            with tempfile.TemporaryDirectory() as tmp:
                _copy_task(task_id, tmp)
                for relpath, content in files.items():
                    target = Path(tmp) / relpath
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                result = _run_hidden(tmp)
                self.assertEqual(result.returncode, 0,
                                 task_id + "\n" + result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
