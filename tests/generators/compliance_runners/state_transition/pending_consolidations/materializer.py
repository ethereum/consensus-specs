"""Materialize Gloas ``process_pending_consolidations`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import (
    ConcretizingMaterializer,
)

from .concretization import STRATEGY
from .target import TARGET

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_VALIDATOR_COUNT = 8


class PendingConsolidationsMaterializer(ConcretizingMaterializer):
    runner_name = "epoch_processing"
    handler_name = "pending_consolidations"
    strategy = STRATEGY

    def _base_state(self) -> Any:
        return create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * _VALIDATOR_COUNT,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )

    def materialize_concrete_attributes(
        self, solution: Any, attributes: dict[str, Any]
    ) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        next_epoch = spec.Epoch(spec.get_current_epoch(pre) + 1)
        for entry in attributes["entries"]:
            source_index = entry["source_index"]
            target_index = entry["target_index"]
            role = entry["role"]
            source = pre.validators[source_index]
            if role == "SLASHED":
                source.slashed = True
            elif role == "BLOCKED":
                source.withdrawable_epoch = spec.Epoch(next_epoch + 1)
            elif role == "PROCESSABLE":
                source.withdrawable_epoch = next_epoch
                pre.balances[source_index] = spec.Gwei(entry["source_balance"])
            else:
                raise ValueError(f"unknown consolidation role: {role}")
            pre.pending_consolidations.append(
                spec.PendingConsolidation(
                    source_index=spec.ValidatorIndex(source_index),
                    target_index=spec.ValidatorIndex(target_index),
                )
            )

        post = pre.copy()
        spec.process_pending_consolidations(post)
        claimed = self.claimed_record(TARGET, solution)
        meta = {
            "description": f"process_pending_consolidations: {claimed['outcome']}",
            "claimed": claimed,
        }
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        return meta, parts


MATERIALIZER = PendingConsolidationsMaterializer
