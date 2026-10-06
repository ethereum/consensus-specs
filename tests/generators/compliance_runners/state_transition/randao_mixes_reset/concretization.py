"""Manual concretization for RANDAO-reset coverage cases."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.concretization import (
    ConcretizationStrategy,
    modulo_representative,
)


class ManualConcretizer:
    def concretize(self, abstract_case: Any, spec: Any, rng: Any) -> dict[str, Any]:
        vector_length = int(spec.EPOCHS_PER_HISTORICAL_VECTOR)
        position = getattr(abstract_case, "destination_position", "ZERO")
        source_nonzero = getattr(abstract_case, "source_nonzero", True)
        source_matches_destination = getattr(abstract_case, "source_matches_destination", True)
        next_epoch = modulo_representative(position, vector_length) or vector_length
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
            "next_epoch": next_epoch,
            "source_mix": source_mix,
            "destination_mix": destination_mix,
        }


STRATEGY = ConcretizationStrategy("manual", ManualConcretizer())
