"""Materialize Gloas ``process_randao_mixes_reset`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class RandaoMixesResetMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "randao_mixes_reset"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        at_first_slot = bool(getattr(solution, "destination_is_first_slot", True))
        source_nonzero = bool(getattr(solution, "source_nonzero", True))
        source_matches_destination = bool(
            getattr(solution, "source_matches_destination", True)
        )
        vector_length = int(spec.EPOCHS_PER_HISTORICAL_VECTOR)
        current_epoch = vector_length - 1 if at_first_slot else 0
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        source_index = current_epoch % vector_length
        destination_index = (current_epoch + 1) % vector_length
        zero_mix = spec.Bytes32()
        source_mix = spec.Bytes32(b"\x01" * 32) if source_nonzero else zero_mix
        if source_matches_destination:
            destination_mix = source_mix
        else:
            destination_mix = (
                spec.Bytes32(b"\x02" * 32)
                if source_nonzero
                else spec.Bytes32(b"\x01" * 32)
            )
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
