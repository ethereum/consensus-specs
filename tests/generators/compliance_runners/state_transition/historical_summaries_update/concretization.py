"""Manual concretization for historical-summary update coverage cases."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Any) -> dict[str, int]:
        period = int(spec.SLOTS_PER_HISTORICAL_ROOT) // int(spec.SLOTS_PER_EPOCH)
        at_boundary = bool(getattr(abstract_case, "at_update_boundary", True))
        next_epoch = period if at_boundary else 1
        summary_count = (
            rng.randint(1, 4) if getattr(abstract_case, "summaries_nonempty", True) else 0
        )
        return {"next_epoch": next_epoch, "summary_count": summary_count}


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
