"""Cost tracker core: estimate, reserve, reconcile, and persist to cost_log.json.

Implements the budget governance rules from the spec:
- Every paid operation produces a preflight estimate
- The orchestrator reserves estimated budget before execution
- Budget overruns trigger pauses (in warn/cap mode)
- Actual spend is reconciled when the tool finishes or fails
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from lib.config_model import BudgetMode


class EntryStatus(str, Enum):
    ESTIMATED = "estimated"
    RESERVED = "reserved"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class BudgetExceededError(Exception):
    """Raised when an operation would exceed the budget in cap mode."""
    pass


class ApprovalRequiredError(Exception):
    """Raised when an operation needs user approval before proceeding."""
    pass


class CostTracker:
    """Tracks estimated, reserved, and actual costs for a pipeline project."""

    def __init__(
        self,
        budget_total_usd: float = 10.0,
        reserve_pct: float = 0.10,
        single_action_approval_usd: float = 0.50,
        require_approval_for_new_paid_tool: bool = True,
        mode: BudgetMode = BudgetMode.WARN,
        cost_log_path: Optional[Path] = None,
    ) -> None:
        self.budget_total_usd = budget_total_usd
        self.reserve_pct = reserve_pct
        self.single_action_approval_usd = single_action_approval_usd
        self.require_approval_for_new_paid_tool = require_approval_for_new_paid_tool
        self.mode = mode
        self.cost_log_path = cost_log_path
        self.entries: list[dict[str, Any]] = []
        self._approved_tools: set[str] = set()

        if cost_log_path and cost_log_path.exists():
            self._load()

    # ---- Budget calculations ----

    @property
    def budget_reserved_usd(self) -> float:
        return sum(
            e.get("reserved_usd", 0.0)
            for e in self.entries
            if e["status"] == EntryStatus.RESERVED.value
        )

    @property
    def budget_spent_usd(self) -> float:
        return sum(
            e.get("actual_usd", 0.0)
            for e in self.entries
            if e["status"] in (EntryStatus.COMPLETED.value, EntryStatus.FAILED.value)
        )

    @property
    def budget_remaining_usd(self) -> float:
        return self.budget_total_usd - self.budget_spent_usd - self.budget_reserved_usd

    @property
    def usable_budget_usd(self) -> float:
        """Budget minus the reserve holdback."""
        holdback = self.budget_total_usd * self.reserve_pct
        return max(0.0, self.budget_remaining_usd - holdback)

    def cost_snapshot(self) -> dict[str, float]:
        return {
            "total_spent_usd": round(self.budget_spent_usd, 4),
            "total_reserved_usd": round(self.budget_reserved_usd, 4),
            "budget_remaining_usd": round(self.budget_remaining_usd, 4),
        }

    # ---- Core operations ----

    def estimate(self, tool: str, operation: str, estimated_usd: float) -> str:
        """Record an estimate. Returns entry ID."""
        entry_id = self._new_id()
        self.entries.append({
            "id": entry_id,
            "tool": tool,
            "operation": operation,
            "status": EntryStatus.ESTIMATED.value,
            "estimated_usd": round(estimated_usd, 4),
            "reserved_usd": 0.0,
            "actual_usd": 0.0,
            "timestamp": self._now(),
        })
        self._save()
        return entry_id

    def reserve(self, entry_id: str) -> None:
        """Reserve budget for an estimated entry.

        Raises BudgetExceededError in cap mode, or ApprovalRequiredError
        when the action exceeds the single-action approval threshold.
        """
        entry = self._find(entry_id)
        estimated = entry["estimated_usd"]

        # Check single-action approval threshold
        if estimated > self.single_action_approval_usd:
            if self.mode != BudgetMode.OBSERVE:
                raise ApprovalRequiredError(
                    f"Action costs ${estimated:.2f}, exceeds "
                    f"single-action threshold ${self.single_action_approval_usd:.2f}"
                )

        # Check new paid tool approval
        if self.require_approval_for_new_paid_tool and estimated > 0:
            if entry["tool"] not in self._approved_tools:
                if self.mode != BudgetMode.OBSERVE:
                    raise ApprovalRequiredError(
                        f"First paid use of tool {entry['tool']!r} requires approval"
                    )

        # Check budget
        if estimated > self.usable_budget_usd:
            if self.mode == BudgetMode.CAP:
                raise BudgetExceededError(
                    f"Reservation of ${estimated:.2f} exceeds usable budget "
                    f"${self.usable_budget_usd:.2f}"
                )

        entry["status"] = EntryStatus.RESERVED.value
        entry["reserved_usd"] = estimated
        entry["timestamp"] = self._now()
        self._save()

    def approve_tool(self, tool: str) -> None:
        """Mark a tool as approved for paid operations."""
        self._approved_tools.add(tool)

    def reconcile(self, entry_id: str, actual_usd: float, success: bool = True) -> None:
        """Reconcile actual spend after tool execution."""
        entry = self._find(entry_id)
        entry["status"] = EntryStatus.COMPLETED.value if success else EntryStatus.FAILED.value
        entry["actual_usd"] = round(actual_usd, 4)
        entry["reserved_usd"] = 0.0
        entry["timestamp"] = self._now()
        self._save()

    def refund(self, entry_id: str) -> None:
        """Cancel a reservation without executing."""
        entry = self._find(entry_id)
        entry["status"] = EntryStatus.REFUNDED.value
        entry["reserved_usd"] = 0.0
        entry["timestamp"] = self._now()
        self._save()

    # ---- Persistence ----

    def _save(self) -> None:
        if self.cost_log_path is None:
            return
        data = {
            "version": "1.0",
            "budget_total_usd": self.budget_total_usd,
            "budget_reserved_usd": round(self.budget_reserved_usd, 4),
            "budget_spent_usd": round(self.budget_spent_usd, 4),
            "entries": self.entries,
        }
        self.cost_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cost_log_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        with open(self.cost_log_path) as f:  # type: ignore[arg-type]
            data = json.load(f)
        self.entries = data.get("entries", [])
        self.budget_total_usd = data.get("budget_total_usd", self.budget_total_usd)

    # ---- Helpers ----

    def _find(self, entry_id: str) -> dict[str, Any]:
        for entry in self.entries:
            if entry["id"] == entry_id:
                return entry
        raise KeyError(f"Cost entry {entry_id!r} not found")

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
