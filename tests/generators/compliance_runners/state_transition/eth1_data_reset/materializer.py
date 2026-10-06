"""Materialize Gloas ``process_eth1_data_reset`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)

from .concretization import STRATEGY

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class Eth1DataResetMaterializer(ConcretizingMaterializer):
    runner_name = "epoch_processing"
    handler_name = "eth1_data_reset"

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

        current_epoch = int(attributes["next_epoch"]) - 1
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        for _ in range(int(attributes["vote_count"])):
            vote = spec.Eth1Data()
            vote.deposit_root = spec.Root(self.rng.getrandbits(256).to_bytes(32, "big"))
            vote.deposit_count = type(vote.deposit_count)(self.rng.getrandbits(64))
            vote.block_hash = spec.Hash32(self.rng.getrandbits(256).to_bytes(32, "big"))
            pre.eth1_data_votes.append(vote)

        post = pre.copy()
        spec.process_eth1_data_reset(post)
        claimed = {
            name: bool(getattr(solution, name))
            for name in ("at_reset_boundary", "votes_nonempty")
            if hasattr(solution, name)
        }
        meta = {
            "description": "process_eth1_data_reset",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = Eth1DataResetMaterializer
