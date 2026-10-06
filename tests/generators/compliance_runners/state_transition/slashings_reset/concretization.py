"""Manual concretization for slashings-reset coverage cases."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Any) -> dict[str, int]:
        vector_length = int(spec.EPOCHS_PER_SLASHINGS_VECTOR)
        destination_is_first_slot = getattr(abstract_case, "destination_is_first_slot", True)
        destination_index = 0 if destination_is_first_slot else 1
        destination_nonzero = getattr(abstract_case, "destination_nonzero", True)
        if destination_index >= vector_length:
            raise ValueError("slashings vector is too short to realize destination slot")
        destination_value = (rng.getrandbits(64) or 1) if destination_nonzero else 0
        return {"destination_index": destination_index, "destination_value": destination_value}


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
