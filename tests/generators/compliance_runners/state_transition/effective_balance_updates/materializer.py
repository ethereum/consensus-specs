"""Materialize Gloas ``process_effective_balance_updates`` epoch vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_DIMS = ["scenario", "credential_type", "hysteresis_result", "balance_alignment", "outcome"]
_GENESIS_VALIDATOR_COUNT = 64
_VALIDATOR_INDEX = 0


class EffectiveBalanceUpdatesBodyMaterializer(Materializer):
    runner_name = "epoch_processing"
    handler_name = "effective_balance_updates"

    def _base_state(self) -> Any:
        state = create_genesis_state(
            self.spec,
            validator_balances=[self.spec.MAX_EFFECTIVE_BALANCE] * _GENESIS_VALIDATOR_COUNT,
            activation_threshold=self.spec.MAX_EFFECTIVE_BALANCE,
        )
        # Genesis construction needs a larger active set for the Gloas PTC
        # window. The processor under test reads only these lists, so retain a
        # single validator to isolate the loop-body behaviour.
        validator = state.validators[_VALIDATOR_INDEX]
        balance = state.balances[_VALIDATOR_INDEX]
        state.validators = type(state.validators)()
        state.validators.append(validator)
        state.balances = type(state.balances)()
        state.balances.append(balance)
        return state

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        validator = pre.validators[_VALIDATOR_INDEX]
        increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
        scenario = str(solution.scenario)

        if scenario == "STABLE_STANDARD":
            effective_balance = int(spec.MAX_EFFECTIVE_BALANCE)
            balance = effective_balance
        elif scenario == "DOWNWARD_STANDARD":
            effective_balance = int(spec.MAX_EFFECTIVE_BALANCE)
            balance = effective_balance - increment - 1
        elif scenario == "UPWARD_STANDARD":
            effective_balance = 29 * increment
            balance = 31 * increment + 1
        elif scenario == "CAPPED_STANDARD":
            effective_balance = 30 * increment
            balance = 34 * increment
        elif scenario == "UPWARD_COMPOUNDING":
            validator.withdrawal_credentials = spec.Bytes32(
                spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
            )
            effective_balance = 31 * increment
            balance = 33 * increment + 1
        else:
            raise ValueError(f"unknown effective-balance scenario: {scenario}")

        validator.effective_balance = spec.Gwei(effective_balance)
        pre.balances[_VALIDATOR_INDEX] = spec.Gwei(balance)
        post = pre.copy()
        spec.process_effective_balance_updates(post)

        claimed = {
            name: bool(value) if isinstance(value := getattr(solution, name), bool) else str(value)
            for name in _DIMS
            if name != "scenario"
        }
        meta = {
            "description": f"process_effective_balance_updates: {claimed['outcome']}",
            "claimed": claimed,
        }
        return meta, [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
