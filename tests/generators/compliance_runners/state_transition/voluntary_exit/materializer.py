"""Materialize Gloas ``process_voluntary_exit`` operation vectors."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.voluntary_exits import sign_voluntary_exit
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .target import TARGET
from .witness import BUCKET_DELTAS, churn_witness

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart


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
        validator_index = self.rng.randrange(_VALIDATOR_COUNT)
        message_bucket = solution.current_ge_message_epoch
        seasoned_bucket = solution.current_ge_seasoned
        period = int(spec.config.SHARD_COMMITTEE_PERIOD)
        current_epoch = period + 4
        exit_epoch = current_epoch - BUCKET_DELTAS[message_bucket]
        activation_epoch = (
            current_epoch - period - BUCKET_DELTAS[seasoned_bucket]
            if solution.activation_le_current
            else current_epoch + 1
        )
        pre.slot = spec.Slot(current_epoch * int(spec.SLOTS_PER_EPOCH))
        validator = pre.validators[validator_index]
        validator.activation_epoch = spec.Epoch(activation_epoch)
        if not solution.exit_not_initiated:
            validator.exit_epoch = spec.Epoch(
                current_epoch + 1 if solution.current_lt_exit else current_epoch
            )
        pending_count = {"ZERO": 0, "ONE": 1, "MANY": 2}[solution.matching_pending_entries]
        for _ in range(pending_count):
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(validator_index),
                    amount=spec.Gwei(0 if solution.pending_balance_zero else 1),
                    withdrawable_epoch=spec.Epoch(current_epoch + 1),
                )
            )
        balance, budget = churn_witness(spec, solution)
        increment = int(spec.EFFECTIVE_BALANCE_INCREMENT)
        if balance % increment or not 0 <= balance <= int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA):
            raise ValueError("exit effective balance must be aligned and within the validator cap")
        validator.effective_balance = spec.Gwei(balance)
        pre.balances[validator_index] = spec.Gwei(max(balance, int(pre.balances[validator_index])))
        if balance > int(spec.MAX_EFFECTIVE_BALANCE):
            validator.withdrawal_credentials = spec.Bytes32(
                spec.COMPOUNDING_WITHDRAWAL_PREFIX + bytes(validator.withdrawal_credentials)[1:]
            )
        fresh = solution.earliest_lt_new
        new_exit_epoch = int(spec.compute_activation_exit_epoch(spec.Epoch(current_epoch)))
        churn = int(spec.get_exit_churn_limit(pre))
        if fresh and budget != churn:
            raise ValueError("fresh churn witness differs from the current churn limit")
        if not 0 <= budget <= churn:
            raise ValueError("exit churn witness budget must be within the current churn limit")
        pre.earliest_exit_epoch = spec.Epoch(new_exit_epoch - 1)
        pre.exit_balance_to_consume = spec.Gwei(0)
        if not fresh:
            consumed = churn - budget
            if consumed and solution.foreign_pending_entries == "SOME":
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
        if solution.foreign_pending_entries == "SOME" and not any(
            w.validator_index != validator_index for w in pre.pending_partial_withdrawals
        ):
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex((validator_index + 1) % _VALIDATOR_COUNT),
                    amount=spec.Gwei(0),
                    withdrawable_epoch=spec.Epoch(current_epoch + 1),
                )
            )
        message = spec.VoluntaryExit(
            epoch=exit_epoch,
            validator_index=spec.ValidatorIndex(validator_index),
        )
        with bls_enabled():
            signed_exit = sign_voluntary_exit(spec, pre, message, privkeys[validator_index])
        if not solution.signature_ok:
            signed_exit.signature = spec.BLSSignature()

        post = pre.copy()
        try:
            with bls_enabled():
                spec.process_voluntary_exit(post, signed_exit)
        except (AssertionError, IndexError):
            post = None

        claimed = self.claimed_record(TARGET, solution)
        meta = {
            "description": f"process_voluntary_exit: {'ACCEPT' if claimed['accepted'] else 'REJECT'}",
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


MATERIALIZER = VoluntaryExitMaterializer
