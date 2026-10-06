"""Manual concretization for RANDAO-reset coverage cases."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Any) -> dict[str, Any]:
        vector_length = int(spec.EPOCHS_PER_HISTORICAL_VECTOR)
        destination_is_first_slot = getattr(abstract_case, "destination_is_first_slot", True)
        source_nonzero = getattr(abstract_case, "source_nonzero", True)
        source_matches_destination = getattr(
            abstract_case, "source_matches_destination", True
        )
        destination_index = 0 if destination_is_first_slot else 1
        if destination_index >= vector_length:
            raise ValueError("RANDAO vector is too short to realize destination slot")
        source_value = (rng.getrandbits(256) or 1) if source_nonzero else 0
        source_mix = source_value.to_bytes(32, "big")
        if source_matches_destination:
            destination_mix = source_mix
        else:
            destination_value = rng.getrandbits(256) or 1
            if destination_value == source_value:
                destination_value = (destination_value + 1) % (1 << 256) or 1
            destination_mix = destination_value.to_bytes(32, "big")
        return {
            "destination_index": destination_index,
            "source_mix": source_mix,
            "destination_mix": destination_mix,
        }


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
