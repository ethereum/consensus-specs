"""Materialize Gloas ``process_eth1_data_reset`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class Eth1DataResetMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "eth1_data_reset"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )

        reset = bool(getattr(solution, "at_reset_boundary", True))
        votes_nonempty = bool(getattr(solution, "votes_nonempty", True))
        period = int(spec.EPOCHS_PER_ETH1_VOTING_PERIOD)
        current_epoch = period - 1 if reset else 0
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        if votes_nonempty:
            pre.eth1_data_votes.append(spec.Eth1Data())

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
