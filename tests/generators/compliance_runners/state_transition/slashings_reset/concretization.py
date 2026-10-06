"""Manual concretization for slashings-reset coverage cases."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
    modulo_representative,
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Any) -> dict[str, int]:
        vector_length = int(spec.EPOCHS_PER_SLASHINGS_VECTOR)
        position = getattr(abstract_case, "destination_position", "ZERO")
        next_epoch = modulo_representative(position, vector_length) or vector_length
        destination_nonzero = getattr(abstract_case, "destination_nonzero", "GT_1")
        destination_value = {"EQ": 0, "GT_1": 1, "GT_FAR": rng.randint(2, (1 << 64) - 1)}[
            destination_nonzero
        ]
        return {"next_epoch": next_epoch, "destination_value": destination_value}


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
