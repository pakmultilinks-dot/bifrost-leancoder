"""Tests for the approval gate."""
import unittest

from leancoder.approval import ApprovalGate


class TestApprovalGate(unittest.TestCase):
    def test_auto_approve_returns_true_without_asking(self):
        seen = []
        gate = ApprovalGate(auto_approve=True,
                            input_fn=lambda prompt: seen.append(prompt) or "n")
        self.assertTrue(gate.request("write_patch", "Write file a.py"))
        self.assertEqual(seen, [])
        self.assertEqual(gate.decisions[0]["mode"], "demo auto-approve")

    def test_manual_yes(self):
        gate = ApprovalGate(input_fn=lambda prompt: "y")
        self.assertTrue(gate.request("write_patch", "Write file a.py"))
        self.assertTrue(gate.decisions[0]["approved"])

    def test_manual_no(self):
        gate = ApprovalGate(input_fn=lambda prompt: "n")
        self.assertFalse(gate.request("run_tests", "Run tests"))
        self.assertFalse(gate.decisions[0]["approved"])

    def test_empty_answer_is_no(self):
        gate = ApprovalGate(input_fn=lambda prompt: "")
        self.assertFalse(gate.request("git_commit", "Commit"))

    def test_decisions_recorded(self):
        gate = ApprovalGate(input_fn=lambda prompt: "yes")
        gate.request("write_patch", "Write file a.py", "diff here")
        self.assertEqual(len(gate.decisions), 1)
        self.assertEqual(gate.decisions[0]["kind"], "write_patch")


if __name__ == "__main__":
    unittest.main()
