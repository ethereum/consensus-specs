"""Manual concretization for ETH1 reset coverage cases."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Any) -> dict[str, int]:
        period = int(spec.EPOCHS_PER_ETH1_VOTING_PERIOD)
        at_boundary = bool(getattr(abstract_case, "at_reset_boundary", True))
        next_epoch = period if at_boundary else 1
        vote_count = (
            rng.randint(1, 4) if getattr(abstract_case, "votes_nonempty", True) else 0
        )
        return {"next_epoch": next_epoch, "vote_count": vote_count}


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
