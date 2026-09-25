"""Materialize Gloas ``process_voluntary_exit`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.voluntary_exits import sign_voluntary_exit
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


_DIMS = [
    "scenario",
    "validator_active",
    "exit_not_initiated",
    "exit_epoch_valid",
    "active_long_enough",
    "exit_churn_state",
    "no_pending_withdrawal",
    "signature_valid",
    "outcome",
]
_VALIDATOR_INDEX = 0


class VoluntaryExitMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "voluntary_exit"

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * 64,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.slot = spec.Slot((int(spec.config.SHARD_COMMITTEE_PERIOD) + 1) * spec.SLOTS_PER_EPOCH)
        return state

    def materialize_solution(self, solution: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        scenario = str(solution.scenario)
        current_epoch = spec.get_current_epoch(pre)
        validator = pre.validators[_VALIDATOR_INDEX]
        exit_epoch = current_epoch

        if scenario == "INACTIVE":
            validator.activation_epoch = spec.Epoch(current_epoch + 1)
        elif scenario == "ALREADY_EXITED":
            validator.exit_epoch = spec.Epoch(current_epoch + 1)
        elif scenario == "FUTURE_EXIT_EPOCH":
            exit_epoch = spec.Epoch(current_epoch + 1)
        elif scenario == "TOO_YOUNG":
            validator.activation_epoch = current_epoch
        elif scenario == "PENDING_WITHDRAWAL":
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(_VALIDATOR_INDEX),
                    amount=spec.Gwei(1),
                    withdrawable_epoch=spec.Epoch(current_epoch + 1),
                )
            )
        elif scenario in {"VALID_CARRIED_CHURN", "VALID_EXHAUSTED_CHURN"}:
            pre.earliest_exit_epoch = spec.compute_activation_exit_epoch(current_epoch)
            pre.exit_balance_to_consume = spec.Gwei(
                spec.get_exit_churn_limit(pre) if scenario == "VALID_CARRIED_CHURN" else 1
            )
        elif scenario not in {"VALID", "INVALID_SIGNATURE"}:
            raise ValueError(f"unknown voluntary-exit scenario: {scenario}")

        message = spec.VoluntaryExit(
            epoch=exit_epoch,
            validator_index=spec.ValidatorIndex(_VALIDATOR_INDEX),
        )
        signed_exit = sign_voluntary_exit(spec, pre, message, privkeys[_VALIDATOR_INDEX])
        if scenario == "INVALID_SIGNATURE":
            signed_exit.signature = spec.BLSSignature()

        post = pre.copy()
        try:
            spec.process_voluntary_exit(post, signed_exit)
        except (AssertionError, IndexError):
            post = None

        claimed = {
            name: bool(value) if isinstance(value := getattr(solution, name), bool) else str(value)
            for name in _DIMS
            if name != "scenario"
        }
        meta = {
            "description": f"process_voluntary_exit: {claimed['outcome']}",
            "bls_setting": 1,
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("voluntary_exit", "ssz", signed_exit.encode_bytes()),
        ]
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        return meta, parts
