"""Materialize Gloas ``process_slashings`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_DIMS = ["scenario", "validator_status", "total_slashings", "penalty_outcome", "outcome"]
_VALIDATOR_COUNT = 64


class SlashingsMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "slashings"

    def _base_state(self) -> Any:
        return create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * _VALIDATOR_COUNT,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        scenario = str(solution.scenario)
        validator_index = self.rng.randrange(_VALIDATOR_COUNT)
        validator = pre.validators[validator_index]
        # Mark the selected validator without changing its active status. This
        # lets the independent validator locate it after serialization.
        validator.activation_eligibility_epoch = spec.Epoch(spec.GENESIS_EPOCH + 1)
        current_epoch = spec.get_current_epoch(pre)
        penalty_epoch = spec.Epoch(current_epoch + spec.EPOCHS_PER_SLASHINGS_VECTOR // 2)
        total_active_balance = spec.get_total_active_balance(pre)

        if scenario != "UNSLASHED":
            validator.slashed = True
            validator.withdrawable_epoch = penalty_epoch
        if scenario == "SLASHED_NOT_DUE":
            validator.withdrawable_epoch = spec.Epoch(penalty_epoch + 1)
        slashing_total = 0
        if scenario in {"PARTIAL", "FULL", "UNDERFLOW", "SLASHED_NOT_DUE", "UNSLASHED"}:
            slashing_total = int(total_active_balance)
        if scenario == "PARTIAL":
            slashing_total = int(spec.EFFECTIVE_BALANCE_INCREMENT)
        elif scenario == "UNDERFLOW":
            pre.balances[validator_index] = spec.Gwei(1)
        elif scenario not in {"ZERO", "FULL", "SLASHED_NOT_DUE", "UNSLASHED"}:
            raise ValueError(f"unknown slashings scenario: {scenario}")

        self._set_slashing_total(pre, slashing_total)

        post = pre.copy()
        spec.process_slashings(post)
        claimed = {
            name: bool(value) if isinstance(value := getattr(solution, name), bool) else str(value)
            for name in _DIMS
            if name != "scenario"
        }
        meta = {"description": f"process_slashings: {claimed['outcome']}", "claimed": claimed}
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]

    def _set_slashing_total(self, state: Any, total: int) -> None:
        if total == 0:
            return

        # Spread the same modeled total over a seeded subset of vector slots.
        slot_count = self.rng.randint(1, min(len(state.slashings), total))
        cuts = sorted(self.rng.sample(range(1, total), slot_count - 1)) if slot_count > 1 else []
        amounts = [right - left for left, right in zip([0, *cuts], [*cuts, total])]
        for index in self.rng.sample(range(len(state.slashings)), slot_count):
            state.slashings[index] = self.spec.Gwei(amounts.pop())
