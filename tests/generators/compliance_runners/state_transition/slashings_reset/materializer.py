"""Materialize Gloas ``process_slashings_reset`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class SlashingsResetMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "slashings_reset"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        at_first_slot = bool(getattr(solution, "destination_is_first_slot", True))
        destination_nonzero = bool(getattr(solution, "destination_nonzero", True))
        vector_length = int(spec.EPOCHS_PER_SLASHINGS_VECTOR)
        current_epoch = vector_length - 1 if at_first_slot else 0
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        destination_index = (current_epoch + 1) % vector_length
        pre.slashings[destination_index] = (
            spec.Gwei(spec.EFFECTIVE_BALANCE_INCREMENT) if destination_nonzero else spec.Gwei(0)
        )

        post = pre.copy()
        spec.process_slashings_reset(post)
        claimed = {
            name: bool(getattr(solution, name))
            for name in ("destination_is_first_slot", "destination_nonzero")
            if hasattr(solution, name)
        }
        meta = {"description": "process_slashings_reset", "claimed": claimed}
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = SlashingsResetMaterializer
