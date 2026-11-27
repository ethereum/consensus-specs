"""Materialize Gloas ``process_historical_summaries_update`` epoch vectors."""

from __future__ import annotations

from functools import cached_property
from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_to
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)

from .concretization import STRATEGY
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class HistoricalSummariesUpdateMaterializer(ConcretizingMaterializer):
    runner_name = "epoch_processing"
    handler_name = "historical_summaries_update"

    strategy = STRATEGY

    @cached_property
    def _checkpoints(self) -> list:
        spec = self.spec
        return [
            create_genesis_state(
                spec,
                validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
                activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
            )
        ]

    def _state_at_final_slot(self, slot):
        # Cases share a chain of skipped slots until their final block. Keep sparse
        # snapshots so later cases can reuse that history in any generation order.
        spec = self.spec
        stride = 8 * spec.SLOTS_PER_EPOCH
        index = slot // stride
        checkpoints = self._checkpoints
        while len(checkpoints) <= index:
            state = checkpoints[-1].copy()
            spec.process_slots(state, state.slot + stride)
            checkpoints.append(state)
        pre = checkpoints[index].copy()
        spec.process_slots(pre, slot)
        return pre

    def materialize_concrete_attributes(
        self, solution: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        final_slot = spec.compute_start_slot_at_epoch(spec.Epoch(attributes["next_epoch"])) - 1
        pre = self._state_at_final_slot(final_slot)
        spec.process_block(pre, build_empty_block(spec, pre))
        run_epoch_processing_to(spec, pre, "process_historical_summaries_update")
        post = pre.copy()
        spec.process_historical_summaries_update(post)
        claimed = self.claimed_record(TARGET, solution)
        meta = {
            "description": "process_historical_summaries_update",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = HistoricalSummariesUpdateMaterializer
