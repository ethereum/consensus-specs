"""Materialize aspect-model solutions into process_withdrawal_request cases.

Realizes each applicable coverage dimension onto a genesis validator (or leaves
the request pubkey absent), constructs a WithdrawalRequest, and derives post.
No BLS, no churn gate. The operation never raises, so `post` is always present.

Spec: specs/electra/beacon-chain.md process_withdrawal_request (inherited by gloas).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkeys
from tests.generators.compliance_runners.state_transition.aspects_helpers.authorization import (
    credential_and_other_address,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.entity_reference import (
    distinct_indices,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_capacity import (
    queue_length_from_profile,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_from_profile,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer

if TYPE_CHECKING:
    from tests.generators.compliance_runners.gen_base.gen_typing import TestCasePart

NUM_VALIDATORS = 64
PARTIAL_AMOUNT = 10**9

_DIMS = [
    "is_full_exit_request",
    "partial_queue_capacity",
    "validator_pubkey_found",
    "validator_credential",
    "source_address_matches",
    "validator_active",
    "validator_exiting",
    "validator_old_enough",
    "has_pending_partial_withdrawal",
    "effective_balance_to_min_activation",
    "balance_to_required",
    "churn_variant",
    "validator_has_execution_credential",
    "validator_has_compounding_credential",
    "outcome",
    "withdrawal_effected",
]


def _s(sol: Any, n: str) -> str:
    return str(getattr(sol, n))


def _b(sol: Any, n: str) -> bool:
    return bool(getattr(sol, n))


class WithdrawalRequestMaterializer(Materializer):
    runner_name = "operations"
    handler_name = "withdrawal_request"

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * NUM_VALIDATORS,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        current_epoch = self.rng.randrange(
            int(spec.config.SHARD_COMMITTEE_PERIOD) + 10,
            int(spec.config.SHARD_COMMITTEE_PERIOD) + 101,
        )
        state.slot = spec.Slot(current_epoch * spec.SLOTS_PER_EPOCH)
        return state

    def _epochs(
        self, current_epoch: int, active: bool, exiting: bool, old_enough: bool
    ) -> tuple[int, int]:
        """Realize the lifecycle triple at ``current_epoch``."""
        spec = self.spec
        far = int(spec.FAR_FUTURE_EPOCH)
        committee_period = int(spec.config.SHARD_COMMITTEE_PERIOD)
        activation = (
            self.rng.randrange(current_epoch - committee_period + 1)
            if old_enough
            else self.rng.randrange(current_epoch - committee_period + 1, current_epoch + 1)
        )
        if active:
            exit_epoch = current_epoch + self.rng.randrange(1, 11) if exiting else far
        elif exiting:
            exit_epoch = self.rng.randrange(current_epoch + 1)
        else:
            activation = current_epoch + self.rng.randrange(1, 11)
            exit_epoch = far
        return activation, exit_epoch

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        current_epoch = int(spec.get_current_epoch(pre))
        found = _b(sol, "validator_pubkey_found")
        is_full = _b(sol, "is_full_exit_request")
        target_index = distinct_indices(self.rng, NUM_VALIDATORS, 1)[0]
        absent_index = (
            NUM_VALIDATORS + distinct_indices(self.rng, len(pubkeys) - NUM_VALIDATORS, 1)[0]
        )
        credential_address, other_address = credential_and_other_address(self.rng)

        source_address = credential_address
        if found:
            v = pre.validators[target_index]
            cred = _s(sol, "validator_credential")
            v.withdrawal_credentials = spec.Bytes32(
                withdrawal_credentials_from_profile(spec, cred, credential_address, self.rng)
            )
            source_address = (
                credential_address if _s(sol, "source_address_matches") == "T" else other_address
            )

            activation, exit_epoch = self._epochs(
                current_epoch,
                _s(sol, "validator_active") == "T",
                _s(sol, "validator_exiting") == "T",
                _s(sol, "validator_old_enough") == "T",
            )
            v.activation_epoch = spec.Epoch(activation)
            v.exit_epoch = spec.Epoch(exit_epoch)
            effective_balance_relation = _s(sol, "effective_balance_to_min_activation")
            effective_balance = int(spec.MIN_ACTIVATION_BALANCE)
            if effective_balance_relation == "LT":
                effective_balance = self.rng.randrange(effective_balance)
            elif effective_balance_relation == "GT":
                effective_balance += int(spec.EFFECTIVE_BALANCE_INCREMENT) * self.rng.randrange(
                    1, 11
                )
            v.effective_balance = spec.Gwei(effective_balance)

            # A carry-overflow vector must exceed the per-epoch exit churn by
            # several epochs.  Keep the declared balance relation (GT) true.
            if _s(sol, "churn_variant") == "CARRY_OVERFLOW":
                v.effective_balance = spec.Gwei(int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA))

        # Pending-partial-withdrawals queue: target entry (for has_pending) +
        # filler realizes the requested capacity profile.
        pending_for_target = found and _s(sol, "has_pending_partial_withdrawal") == "T"
        queue_capacity = _s(sol, "partial_queue_capacity")
        queue_length = queue_length_from_profile(
            queue_capacity, int(spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT), self.rng
        )
        entries = []
        if pending_for_target:
            entries.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(target_index),
                    amount=spec.Gwei(self.rng.randrange(1, PARTIAL_AMOUNT + 1)),
                    withdrawable_epoch=spec.Epoch(current_epoch + self.rng.randrange(11)),
                )
            )
        if queue_length:
            while len(entries) < queue_length:
                filler_index = self.rng.randrange(NUM_VALIDATORS - 1)
                if filler_index >= target_index:
                    filler_index += 1
                entries.append(
                    spec.PendingPartialWithdrawal(
                        validator_index=spec.ValidatorIndex(filler_index),
                        amount=spec.Gwei(self.rng.randrange(1, PARTIAL_AMOUNT + 1)),
                        withdrawable_epoch=spec.Epoch(current_epoch + self.rng.randrange(11)),
                    )
                )
        pre.pending_partial_withdrawals = spec.PendingPartialWithdrawals(data=entries)

        if found:
            pending_amount = (
                sum(int(entry.amount) for entry in entries if entry.validator_index == target_index)
                if pending_for_target
                else 0
            )
            required_balance = int(spec.MIN_ACTIVATION_BALANCE) + pending_amount
            balance_relation = _s(sol, "balance_to_required")
            if balance_relation == "LT":
                balance = self.rng.randrange(required_balance)
            elif balance_relation == "GT":
                balance = required_balance + self.rng.randrange(1, PARTIAL_AMOUNT + 1)
            else:
                balance = required_balance
            pre.balances[target_index] = spec.Gwei(balance)

        variant = _s(sol, "churn_variant")
        activation_epoch = int(spec.compute_activation_exit_epoch(spec.get_current_epoch(pre)))
        if variant == "RESET_FIT":
            pre.earliest_exit_epoch = spec.Epoch(max(0, activation_epoch - 1))
            pre.exit_balance_to_consume = spec.Gwei(0)
        elif variant == "CARRY_FIT":
            pre.earliest_exit_epoch = spec.Epoch(activation_epoch)
            pre.exit_balance_to_consume = pre.validators[target_index].effective_balance
        elif variant == "CARRY_OVERFLOW":
            # A later epoch and one-unit remainder force multi-epoch queueing.
            pre.earliest_exit_epoch = spec.Epoch(activation_epoch + 1)
            pre.exit_balance_to_consume = spec.Gwei(1)

        request = spec.WithdrawalRequest(
            source_address=spec.ExecutionAddress(source_address),
            validator_pubkey=spec.BLSPubkey(
                pre.validators[target_index].pubkey if found else pubkeys[absent_index]
            ),
            amount=spec.Gwei(0)
            if is_full
            else spec.Gwei(self.rng.randrange(1, PARTIAL_AMOUNT + 1)),
        )

        post = pre.copy()
        spec.process_withdrawal_request(post, request)  # never raises

        claimed = {
            n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS
        }
        meta = {
            "description": f"process_withdrawal_request: {claimed['outcome']}",
            "claimed": claimed,
        }
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("withdrawal_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        return meta, parts
