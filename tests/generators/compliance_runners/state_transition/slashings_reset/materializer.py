"""Materialize Gloas ``process_slashings_reset`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)

from .concretization import STRATEGY

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class SlashingsResetMaterializer(ConcretizingMaterializer):
    runner_name = "epoch_processing"
    handler_name = "slashings_reset"

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
        vector_length = int(spec.EPOCHS_PER_SLASHINGS_VECTOR)
        next_epoch = int(attributes["next_epoch"])
        destination_index = next_epoch % vector_length
        current_epoch = next_epoch - 1
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        for index in range(vector_length):
            pre.slashings[index] = spec.Gwei(self.rng.getrandbits(64))
        pre.slashings[destination_index] = spec.Gwei(int(attributes["destination_value"]))

        post = pre.copy()
        spec.process_slashings_reset(post)
        claimed = {
            name: getattr(solution, name)
            for name in ("destination_position", "destination_nonzero")
            if hasattr(solution, name)
        }
        meta = {"description": "process_slashings_reset", "claimed": claimed}
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = SlashingsResetMaterializer
