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
TARGET_INDEX = 0
ABSENT_PUBKEY = pubkeys[NUM_VALIDATORS]  # not in a NUM_VALIDATORS-validator genesis
CURRENT_EPOCH = 70  # > SHARD_COMMITTEE_PERIOD (64), for old-enough headroom
ADDRESS = b"\x22" * 20
OTHER_ADDRESS = b"\x33" * 20
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

    def _target_index(self) -> int:
        """Select a target validator without changing the canonical no-seed case."""
        if self.seed is None:
            return TARGET_INDEX
        return self.rng.randrange(NUM_VALIDATORS)

    def _absent_pubkey(self) -> Any:
        """Select a pubkey outside the genesis state for a not-found request."""
        if self.seed is None:
            return ABSENT_PUBKEY
        index = NUM_VALIDATORS + self.rng.randrange(len(pubkeys) - NUM_VALIDATORS)
        return pubkeys[index]

    def _addresses(self) -> tuple[bytes, bytes]:
        """Return distinct credential and source addresses for one vector."""
        if self.seed is None:
            return ADDRESS, OTHER_ADDRESS
        credential_address = self.rng.getrandbits(160).to_bytes(20, "big")
        other_address = bytes([credential_address[0] ^ 1]) + credential_address[1:]
        return credential_address, other_address

    def _base_state(self) -> Any:
        spec = self.spec
        state = create_genesis_state(
            spec,
            validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * NUM_VALIDATORS,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.slot = spec.Slot(CURRENT_EPOCH * spec.SLOTS_PER_EPOCH)
        return state

    def _epochs(self, active: bool, exiting: bool, old_enough: bool) -> tuple[int, int]:
        """(activation_epoch, exit_epoch) realizing the lifecycle triple at CURRENT_EPOCH."""
        spec = self.spec
        far = int(spec.FAR_FUTURE_EPOCH)
        activation = 0 if old_enough else CURRENT_EPOCH - 10  # <= C-64 vs in (C-64, C]
        if active:
            exit_epoch = (CURRENT_EPOCH + 10) if exiting else far  # future exit still active
        elif exiting:
            exit_epoch = CURRENT_EPOCH - 1  # exited (epoch >= exit)
        else:
            activation = CURRENT_EPOCH + 10  # not yet activated
            exit_epoch = far
        return activation, exit_epoch

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        found = _b(sol, "validator_pubkey_found")
        is_full = _b(sol, "is_full_exit_request")
        target_index = self._target_index()
        credential_address, other_address = self._addresses()

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
                _s(sol, "validator_active") == "T",
                _s(sol, "validator_exiting") == "T",
                _s(sol, "validator_old_enough") == "T",
            )
            v.activation_epoch = spec.Epoch(activation)
            v.exit_epoch = spec.Epoch(exit_epoch)
            effective_balance_relation = _s(sol, "effective_balance_to_min_activation")
            effective_balance = int(spec.MIN_ACTIVATION_BALANCE)
            if effective_balance_relation == "LT":
                effective_balance -= 1
            elif effective_balance_relation == "GT":
                effective_balance += int(spec.EFFECTIVE_BALANCE_INCREMENT)
            v.effective_balance = spec.Gwei(effective_balance)

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
                    amount=spec.Gwei(1),
                    withdrawable_epoch=spec.Epoch(CURRENT_EPOCH),
                )
            )
        if queue_length:
            filler_index = (
                self.rng.randrange(NUM_VALIDATORS - 1) if self.seed is not None else 0
            )
            if filler_index >= target_index:
                filler_index += 1
            while len(entries) < queue_length:
                entries.append(
                    spec.PendingPartialWithdrawal(
                        validator_index=spec.ValidatorIndex(filler_index),
                        amount=spec.Gwei(1),
                        withdrawable_epoch=spec.Epoch(CURRENT_EPOCH),
                    )
                )
        pre.pending_partial_withdrawals = spec.PendingPartialWithdrawals(data=entries)

        if found:
            pending_amount = 1 if pending_for_target else 0
            required_balance = int(spec.MIN_ACTIVATION_BALANCE) + pending_amount
            balance_relation = _s(sol, "balance_to_required")
            if balance_relation == "LT":
                balance = required_balance - 1
            elif balance_relation == "GT":
                balance = required_balance + PARTIAL_AMOUNT
            else:
                balance = required_balance
            pre.balances[target_index] = spec.Gwei(balance)

        request = spec.WithdrawalRequest(
            source_address=spec.ExecutionAddress(source_address),
            validator_pubkey=spec.BLSPubkey(
                pre.validators[target_index].pubkey if found else self._absent_pubkey()
            ),
            amount=spec.Gwei(0) if is_full else spec.Gwei(PARTIAL_AMOUNT),
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
