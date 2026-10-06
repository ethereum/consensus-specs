"""Materialize Gloas ``process_historical_summaries_update`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)

from .concretization import STRATEGY

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


class HistoricalSummariesUpdateMaterializer(ConcretizingMaterializer):
    runner_name = "epoch_processing"
    handler_name = "historical_summaries_update"

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
        root_count = int(spec.SLOTS_PER_HISTORICAL_ROOT)
        for index in range(root_count):
            pre.block_roots[index] = spec.Root(self.rng.getrandbits(256).to_bytes(32, "big"))
            pre.state_roots[index] = spec.Root(self.rng.getrandbits(256).to_bytes(32, "big"))
        for _ in range(int(attributes["summary_count"])):
            pre.historical_summaries.append(
                spec.HistoricalSummary(
                    block_summary_root=spec.Root(self.rng.getrandbits(256).to_bytes(32, "big")),
                    state_summary_root=spec.Root(self.rng.getrandbits(256).to_bytes(32, "big")),
                )
            )

        post = pre.copy()
        spec.process_historical_summaries_update(post)
        claimed = {
            name: getattr(solution, name)
            for name in ("update_remainder", "summaries_nonempty")
            if hasattr(solution, name)
        }
        meta = {
            "description": "process_historical_summaries_update",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]


MATERIALIZER = HistoricalSummariesUpdateMaterializer
