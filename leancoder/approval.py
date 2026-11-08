"""Approval gate before risky operations.

Default is approval required. The gate asks the user before file
writes, shell commands, and Git actions, showing the exact diff or
command first. Demo mode (--auto-approve) is labelled as demo mode
in the output, and it must never be the default.
"""
from __future__ import annotations


class ApprovalGate:
    """Ask for approval, record every decision."""

    def __init__(self, auto_approve=False, input_fn=None):
        self.auto_approve = bool(auto_approve)
        self._input = input_fn or input
        self.decisions = []

    def request(self, kind, summary, detail=""):
        """Ask for approval. Returns True only on an explicit yes."""
        if self.auto_approve:
            self.decisions.append({
                "kind": kind, "summary": summary,
                "approved": True, "mode": "demo auto-approve",
            })
            return True
        print("Approval required: " + kind)
        print(summary)
        if detail:
            print(detail)
        answer = self._input("Approve? [y/N] ").strip().lower()
        approved = answer in ("y", "yes")
        self.decisions.append({
            "kind": kind, "summary": summary,
            "approved": approved, "mode": "manual",
        })
        return approved
