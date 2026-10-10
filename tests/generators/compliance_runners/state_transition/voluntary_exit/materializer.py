"""Materialize Gloas ``process_voluntary_exit`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.voluntary_exits import sign_voluntary_exit
from tests.generators.compliance_runners.state_transition.materializer import Materializer

from .cases import cmp5_bucket, epoch_witness

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
    "current_ge_message_epoch",
    "current_ge_seasoned",
    "balance_gt_consumable",
    "churn_additional_epochs",
]
_VALIDATOR_COUNT = 64


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
        validator_index = self.rng.randrange(_VALIDATOR_COUNT)
        message_bucket = getattr(
            solution,
            "current_ge_message_epoch",
            "LT_1" if scenario == "FUTURE_EXIT_EPOCH" else "EQ",
        )
        seasoned_bucket = getattr(
            solution,
            "current_ge_seasoned",
            "LT_FAR" if scenario in ("INACTIVE", "TOO_YOUNG") else "GT_1",
        )
        current_epoch, exit_epoch, activation_epoch = epoch_witness(
            int(spec.config.SHARD_COMMITTEE_PERIOD),
            scenario,
            message_bucket,
            seasoned_bucket,
        )
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        validator = pre.validators[validator_index]
        validator.activation_epoch = spec.Epoch(activation_epoch)

        if scenario == "ALREADY_EXITED":
            validator.exit_epoch = spec.Epoch(current_epoch + 1)
        elif scenario == "PENDING_WITHDRAWAL":
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(validator_index),
                    amount=spec.Gwei(1),
                    withdrawable_epoch=spec.Epoch(current_epoch + 1),
                )
            )
        elif scenario not in {
            "VALID",
            "VALID_CARRIED_CHURN",
            "VALID_EXHAUSTED_CHURN",
            "INVALID_SIGNATURE",
            "INACTIVE",
            "FUTURE_EXIT_EPOCH",
            "TOO_YOUNG",
        }:
            raise ValueError(f"unknown voluntary-exit scenario: {scenario}")

        balance = int(getattr(solution, "effective_balance", spec.MAX_EFFECTIVE_BALANCE))
        increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
        if balance % increment or not 0 <= balance <= int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA):
            raise ValueError("exit effective balance must be aligned and within the validator cap")
        validator.effective_balance = spec.Gwei(balance)
        pre.balances[validator_index] = spec.Gwei(max(balance, int(pre.balances[validator_index])))
        if balance > int(spec.MAX_EFFECTIVE_BALANCE):
            validator.withdrawal_credentials = spec.Bytes32(
                spec.COMPOUNDING_WITHDRAWAL_PREFIX + bytes(validator.withdrawal_credentials)[1:]
            )
        fresh = getattr(
            solution,
            "churn_fresh",
            scenario not in {"VALID_CARRIED_CHURN", "VALID_EXHAUSTED_CHURN"},
        )
        new_exit_epoch = int(spec.compute_activation_exit_epoch(spec.Epoch(current_epoch)))
        churn = int(spec.get_exit_churn_limit(pre))
        budget = (
            churn
            if fresh
            else int(
                getattr(
                    solution,
                    "churn_budget",
                    increment if scenario == "VALID_EXHAUSTED_CHURN" else churn,
                )
            )
        )
        if not 0 <= budget <= churn:
            raise ValueError("exit churn witness budget must be within the current churn limit")
        pre.earliest_exit_epoch = spec.Epoch(new_exit_epoch - 1)
        pre.exit_balance_to_consume = spec.Gwei(0)
        if not fresh:
            consumed = churn - budget
            if consumed:
                # A foreign partial withdrawal leaves the requested carried
                # residual, including non-aligned one-Gwei boundary cases.
                foreign_index = (validator_index + 1) % len(pre.validators)
                foreign = pre.validators[foreign_index]
                foreign.withdrawal_credentials = spec.Bytes32(
                    spec.COMPOUNDING_WITHDRAWAL_PREFIX + bytes(foreign.withdrawal_credentials)[1:]
                )
                pre.balances[foreign_index] = spec.Gwei(int(spec.MIN_ACTIVATION_BALANCE) + consumed)
                request = spec.WithdrawalRequest(
                    source_address=spec.ExecutionAddress(
                        bytes(foreign.withdrawal_credentials)[12:]
                    ),
                    validator_pubkey=foreign.pubkey,
                    amount=spec.Gwei(consumed),
                )
                spec.process_withdrawal_request(pre, request)
                if (
                    int(pre.exit_balance_to_consume) != budget
                    or int(pre.earliest_exit_epoch) != new_exit_epoch
                ):
                    raise ValueError(
                        "partial withdrawal did not realize the requested carried budget"
                    )
            else:
                pre.earliest_exit_epoch = spec.Epoch(new_exit_epoch)
                pre.exit_balance_to_consume = spec.Gwei(budget)
        delta = balance - budget
        additional = 0 if delta <= 0 else (delta - 1) // churn + 1
        churn_claims = {
            "balance_gt_consumable": cmp5_bucket(delta),
            "churn_additional_epochs": "ZERO"
            if additional == 0
            else "ONE"
            if additional == 1
            else "MANY",
        }

        message = spec.VoluntaryExit(
            epoch=exit_epoch,
            validator_index=spec.ValidatorIndex(validator_index),
        )
        signed_exit = sign_voluntary_exit(spec, pre, message, privkeys[validator_index])
        if scenario == "INVALID_SIGNATURE":
            signed_exit.signature = spec.BLSSignature()

        post = pre.copy()
        try:
            spec.process_voluntary_exit(post, signed_exit)
        except (AssertionError, IndexError):
            post = None

        claimed = {
            name: bool(value)
            if isinstance(value := getattr(solution, name, churn_claims.get(name)), bool)
            else str(value)
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
