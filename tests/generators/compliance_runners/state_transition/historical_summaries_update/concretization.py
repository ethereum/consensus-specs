"""Manual concretization for historical-summary update coverage cases."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
    modulo_representative,
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Any) -> dict[str, int]:
        period = int(spec.SLOTS_PER_HISTORICAL_ROOT) // int(spec.SLOTS_PER_EPOCH)
        position = getattr(abstract_case, "update_remainder", "ZERO")
        next_epoch = modulo_representative(position, period) or period
        summary_count = {"EQ": 0, "GT_1": 1, "GT_FAR": rng.randint(2, 4)}[
            getattr(abstract_case, "summaries_nonempty", "GT_1")
        ]
        return {"next_epoch": next_epoch, "summary_count": summary_count}


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
