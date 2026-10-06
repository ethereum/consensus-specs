"""Materialize Gloas ``process_randao_mixes_reset`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)

from .concretization import STRATEGY

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class RandaoMixesResetMaterializer(ConcretizingMaterializer):
    runner_name = "epoch_processing"
    handler_name = "randao_mixes_reset"

    strategy = STRATEGY

    def materialize_concrete_attributes(
        self, solution: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        vector_length = int(spec.EPOCHS_PER_HISTORICAL_VECTOR)
        destination_index = int(attributes["destination_index"])
        source_index = (destination_index - 1) % vector_length
        if (
            source_index == destination_index
            and attributes["source_mix"] != attributes["destination_mix"]
        ):
            raise ValueError(
                "RANDAO vector is too short to realize distinct source and destination"
            )
        current_epoch = source_index
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        for index in range(vector_length):
            pre.randao_mixes[index] = spec.Bytes32(self.rng.getrandbits(256).to_bytes(32, "big"))
        source_mix = spec.Bytes32(attributes["source_mix"])
        destination_mix = spec.Bytes32(attributes["destination_mix"])
        pre.randao_mixes[source_index] = source_mix
        pre.randao_mixes[destination_index] = destination_mix

        post = pre.copy()
        spec.process_randao_mixes_reset(post)
        claimed = {
            name: bool(getattr(solution, name))
            for name in (
                "destination_is_first_slot",
                "source_nonzero",
                "source_matches_destination",
            )
            if hasattr(solution, name)
        }
        meta = {"description": "process_randao_mixes_reset", "claimed": claimed}
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = RandaoMixesResetMaterializer
