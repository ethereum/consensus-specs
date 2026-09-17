"""Materialize Gloas ``process_pending_consolidations`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.aspects_helpers.comparison_witness import (
    value_for_comparison,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_DIMS = ["queue_layout", "source_balance_to_effective", "outcome"]
_VALIDATOR_COUNT = 8


class PendingConsolidationsMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "pending_consolidations"

    def _base_state(self) -> Any:
        return create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * _VALIDATOR_COUNT,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        next_epoch = spec.Epoch(spec.get_current_epoch(pre) + 1)
        layout = str(solution.queue_layout)
        relation = str(solution.source_balance_to_effective)

        def append(source_index: int, target_index: int, role: str) -> None:
            source = pre.validators[source_index]
            if role == "SLASHED":
                source.slashed = True
            elif role == "BLOCKED":
                source.withdrawable_epoch = spec.Epoch(next_epoch + 1)
            elif role == "PROCESSABLE":
                source.withdrawable_epoch = next_epoch
                pre.balances[source_index] = spec.Gwei(
                    value_for_comparison(
                        self.rng,
                        relation,
                        int(source.effective_balance),
                        lower_bound=1,
                    )
                )
            else:
                raise ValueError(f"unknown consolidation role: {role}")
            pre.pending_consolidations.append(
                spec.PendingConsolidation(
                    source_index=spec.ValidatorIndex(source_index),
                    target_index=spec.ValidatorIndex(target_index),
                )
            )

        if layout == "EMPTY":
            pass
        elif layout == "SLASHED_ONLY":
            append(0, 1, "SLASHED")
        elif layout == "BLOCKED_ONLY":
            append(0, 1, "BLOCKED")
        elif layout == "PROCESS_ONE":
            append(0, 1, "PROCESSABLE")
        elif layout == "SLASHED_THEN_PROCESS":
            append(0, 1, "SLASHED")
            append(2, 3, "PROCESSABLE")
        elif layout == "PROCESS_THEN_BLOCKED":
            append(0, 1, "PROCESSABLE")
            append(2, 3, "BLOCKED")
        else:
            raise ValueError(f"unknown queue layout: {layout}")

        post = pre.copy()
        spec.process_pending_consolidations(post)
        claimed = {
            name: bool(value) if isinstance(value := getattr(solution, name), bool) else str(value)
            for name in _DIMS
        }
        meta = {
            "description": f"process_pending_consolidations: {claimed['outcome']}",
            "claimed": claimed,
        }
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        return meta, parts
