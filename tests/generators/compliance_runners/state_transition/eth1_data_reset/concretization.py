"""Manual concretization for ETH1 reset coverage cases."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Any) -> dict[str, int]:
        period = int(spec.EPOCHS_PER_ETH1_VOTING_PERIOD)
        remainder = getattr(abstract_case, "reset_remainder", "ZERO")
        next_epoch = {"ZERO": period, "ONE": 1, "LAST": period - 1, "INTERIOR": 2}[remainder]
        occupancy = getattr(abstract_case, "votes_nonempty", "GT_1")
        vote_count = {"EQ": 0, "GT_1": 1, "GT_FAR": rng.randint(2, 4)}[occupancy]
        return {"next_epoch": next_epoch, "vote_count": vote_count}


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
