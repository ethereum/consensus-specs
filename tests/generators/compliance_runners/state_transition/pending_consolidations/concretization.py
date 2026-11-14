"""Concrete queue witnesses for pending-consolidations coverage cases."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from tests.generators.compliance_runners.state_transition.aspects_helpers.comparison_witness import (
    value_for_comparison,
)
from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)

if TYPE_CHECKING:
    from random import Random


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Random) -> dict[str, Any]:
        layout = abstract_case.queue_layout
        entries = {
            "EMPTY": (),
            "SLASHED_ONLY": ((0, 1, "SLASHED"),),
            "BLOCKED_ONLY": ((0, 1, "BLOCKED"),),
            "PROCESS_ONE": ((0, 1, "PROCESSABLE"),),
            "SLASHED_THEN_PROCESS": (
                (0, 1, "SLASHED"),
                (2, 3, "PROCESSABLE"),
            ),
            "PROCESS_THEN_BLOCKED": (
                (0, 1, "PROCESSABLE"),
                (2, 3, "BLOCKED"),
            ),
        }.get(layout)
        if entries is None:
            raise ValueError(f"unknown queue layout: {layout}")

        concrete_entries = []
        for source_index, target_index, role in entries:
            source_balance = None
            if role == "PROCESSABLE":
                source_balance = value_for_comparison(
                    rng,
                    abstract_case.source_balance_to_effective,
                    int(spec.MAX_EFFECTIVE_BALANCE),
                    lower_bound=1,
                )
            concrete_entries.append(
                {
                    "source_index": source_index,
                    "target_index": target_index,
                    "role": role,
                    "source_balance": source_balance,
                }
            )
        return {"entries": concrete_entries}


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
