"""Materialize aspect-model solutions for Gloas ``process_withdrawals``.

The solver selects semantic source presence and the payload-capacity boundary.
This module only chooses the concrete builders and validators needed to realize
that assignment, then records the original solution with the vector.
"""

from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from eth_consensus_specs.test.helpers.withdrawals import prepare_process_withdrawals
from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart
from tests.generators.compliance_runners.state_transition.materializer import Materializer

_DIMS = [
    "parent_payload_revealed",
    "builder_pending_nonempty",
    "pending_partial_nonempty",
    "builder_sweep_nonempty",
    "validator_sweep_nonempty",
    "withdrawals_over_limit",
    "state_effected",
    "outcome",
]
_BUILDER_ADDRESS = b"\x42" * 20


def _b(solution: Any, name: str) -> bool:
    return bool(getattr(solution, name))


def _s(solution: Any, name: str) -> str:
    return str(getattr(solution, name))


class WithdrawalsMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "withdrawals"

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.builders = type(state.builders)()
        return state

    def _add_builders(self, state: Any, count: int) -> None:
        spec = self.spec
        epoch = spec.get_current_epoch(state)
        for index in range(count):
            state.builders.append(
                spec.Builder(
                    pubkey=spec.BLSPubkey(builder_pubkeys[index]),
                    version=spec.PAYLOAD_BUILDER_VERSION,
                    execution_address=spec.ExecutionAddress(bytes([0x42 + index]) * 20),
                    balance=spec.Gwei(1_000_000_000),
                    deposit_epoch=spec.Epoch(0),
                    withdrawable_epoch=spec.Epoch(epoch + 1),
                )
            )

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        parent_full = _b(solution, "parent_payload_revealed")
        builder_pending = _b(solution, "builder_pending_nonempty")
        pending_partial = _b(solution, "pending_partial_nonempty")
        builder_sweep = _b(solution, "builder_sweep_nonempty")
        validator_sweep = _b(solution, "validator_sweep_nonempty")
        at_limit = _b(solution, "withdrawals_over_limit")

        # Four sources can coexist. A Gloas full payload always has a validator
        # sweep withdrawal (the other source stages reserve its final slot).
        count = int(spec.MAX_WITHDRAWALS_PER_PAYLOAD) if at_limit else 1
        builder_count = (
            count
            if at_limit and (builder_pending or builder_sweep)
            else int(builder_pending or builder_sweep)
        )
        if builder_count:
            self._add_builders(pre, builder_count)

        kwargs: dict[str, Any] = {
            "parent_block_full": parent_full,
            "parent_block_empty": not parent_full,
        }
        if builder_pending:
            kwargs["builder_indices"] = list(range(count if at_limit else 1))
        if pending_partial:
            kwargs["pending_partial_indices"] = [8]
        if builder_sweep:
            # Keep pending-withdrawal builders separate from swept builders.
            start = count if builder_pending else 0
            needed = count if at_limit and not builder_pending else 1
            if start + needed > len(pre.builders):
                self._add_builders(pre, start + needed - len(pre.builders))
            kwargs["builder_sweep_indices"] = list(range(start, start + needed))
        if validator_sweep:
            kwargs["full_withdrawal_indices"] = list(range(count if at_limit else 1))

        prepare_process_withdrawals(spec, pre, **kwargs)
        post = pre.copy()
        spec.process_withdrawals(post)
        claimed = {
            name: (
                _b(solution, name)
                if isinstance(getattr(solution, name), bool)
                else _s(solution, name)
            )
            for name in _DIMS
        }
        meta = {"description": f"process_withdrawals: {claimed['outcome']}", "claimed": claimed}
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        return meta, parts
