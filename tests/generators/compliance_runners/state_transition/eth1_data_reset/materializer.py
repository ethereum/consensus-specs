"""Materialize Gloas ``process_eth1_data_reset`` epoch vectors."""

from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_to
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .concretization import STRATEGY
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class Eth1DataResetMaterializer(ConcretizingMaterializer):
    runner_name = "epoch_processing"
    handler_name = "eth1_data_reset"

    strategy = STRATEGY

    @cached_property
    def _epoch_starts(self):
        spec = self.spec
        # Fully funded compounding validators keep PTC sampling fast over a voting period.
        balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
        return [create_genesis_state(spec, [balance] * 64, balance)]

    def _state_at_epoch_start(self, epoch):
        spec = self.spec
        # Reuse the skipped-slot history across voting rounds and case orderings.
        checkpoints = self._epoch_starts
        while len(checkpoints) <= epoch:
            state = checkpoints[-1].copy()
            spec.process_slots(state, state.slot + spec.SLOTS_PER_EPOCH)
            checkpoints.append(state)
        return checkpoints[epoch].copy()

    def materialize_concrete_attributes(
        self, solution: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        next_epoch = spec.Epoch(attributes["next_epoch"])
        final_slot = spec.compute_start_slot_at_epoch(next_epoch) - 1
        pre = self._state_at_epoch_start(next_epoch - 1)
        vote_count = int(attributes["vote_count"])
        with bls_enabled():
            for slot in range(int(final_slot) - vote_count + 1, int(final_slot) + 1):
                spec.process_slots(pre, spec.Slot(slot))
                block = build_empty_block(spec, pre)
                block.body.eth1_data = pre.eth1_data.copy()
                # Use both execution block hashes so a populated list can contain
                # votes for different blocks at the same deposit count.
                if slot % 2:
                    block.body.eth1_data.block_hash = pre.latest_block_hash
                spec.process_block(pre, block)
        run_epoch_processing_to(spec, pre, "process_eth1_data_reset")

        post = pre.copy()
        spec.process_eth1_data_reset(post)
        claimed = self.claimed_record(TARGET, solution)
        meta = {
            "description": "process_eth1_data_reset",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = Eth1DataResetMaterializer
