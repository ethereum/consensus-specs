"""Materialize Gloas ``process_historical_summaries_update`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class HistoricalSummariesUpdateMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "historical_summaries_update"

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        at_update_boundary = bool(getattr(solution, "at_update_boundary", True))
        summaries_nonempty = bool(getattr(solution, "summaries_nonempty", True))
        period = int(spec.SLOTS_PER_HISTORICAL_ROOT) // int(spec.SLOTS_PER_EPOCH)
        current_epoch = period - 1 if at_update_boundary else 0
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        if summaries_nonempty:
            pre.historical_summaries.append(spec.HistoricalSummary())

        post = pre.copy()
        spec.process_historical_summaries_update(post)
        claimed = {
            name: bool(getattr(solution, name))
            for name in ("at_update_boundary", "summaries_nonempty")
            if hasattr(solution, name)
        }
        meta = {
            "description": "process_historical_summaries_update",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = HistoricalSummariesUpdateMaterializer
