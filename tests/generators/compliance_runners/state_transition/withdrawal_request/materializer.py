"""Materialize aspect-model solutions into process_withdrawal_request cases.

Realizes each applicable coverage dimension onto a genesis validator (or leaves
the request pubkey absent), constructs a WithdrawalRequest, and derives post.
No BLS, no churn gate. The operation never raises, so `post` is always present.

Spec: specs/electra/beacon-chain.md process_withdrawal_request (inherited by gloas).
"""
from __future__ import annotations

from typing import Any

from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkeys

from ...gen_base.gen_typing import TestCasePart
from tests.generators.compliance_runners.state_transition.materializer import Materializer

NUM_VALIDATORS = 64
TARGET_INDEX = 0
ABSENT_PUBKEY = pubkeys[NUM_VALIDATORS]         # not in a NUM_VALIDATORS-validator genesis
CURRENT_EPOCH = 70                              # > SHARD_COMMITTEE_PERIOD (64), for old-enough headroom
ADDRESS = b"\x22" * 20
OTHER_ADDRESS = b"\x33" * 20
PARTIAL_AMOUNT = 10 ** 9

_PREFIX = {"CRED_BLS": b"\x00", "CRED_ETH1": b"\x01", "CRED_COMPOUNDING": b"\x02"}

_DIMS = [
    "is_full_exit_request", "partial_queue_full",
    "validator_pubkey_found", "validator_credential", "source_address_matches",
    "validator_active", "validator_exiting", "validator_old_enough",
    "has_pending_partial_withdrawal", "sufficient_effective_balance", "has_excess_balance",
    "validator_has_execution_credential", "validator_has_compounding_credential",
    "outcome", "withdrawal_effected",
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
            spec, validator_balances=[spec.MAX_EFFECTIVE_BALANCE] * NUM_VALIDATORS,
            activation_threshold=spec.MAX_EFFECTIVE_BALANCE,
        )
        state.slot = spec.Slot(CURRENT_EPOCH * spec.SLOTS_PER_EPOCH)
        return state

    def _epochs(self, active: bool, exiting: bool, old_enough: bool) -> tuple[int, int]:
        """(activation_epoch, exit_epoch) realizing the lifecycle triple at CURRENT_EPOCH."""
        spec = self.spec
        far = int(spec.FAR_FUTURE_EPOCH)
        activation = 0 if old_enough else CURRENT_EPOCH - 10   # <= C-64 vs in (C-64, C]
        if active:
            exit_epoch = (CURRENT_EPOCH + 10) if exiting else far   # future exit still active
        else:
            if exiting:
                exit_epoch = CURRENT_EPOCH - 1                        # exited (epoch >= exit)
            else:
                activation = CURRENT_EPOCH + 10                       # not yet activated
                exit_epoch = far
        return activation, exit_epoch

    def materialize_solution(self, sol: Any) -> tuple[dict, list[TestCasePart]]:
        spec = self.spec
        pre = self._base_state()
        found = _b(sol, "validator_pubkey_found")
        is_full = _b(sol, "is_full_exit_request")

        source_address = ADDRESS
        if found:
            v = pre.validators[TARGET_INDEX]
            cred = _s(sol, "validator_credential")
            v.withdrawal_credentials = spec.Bytes32(_PREFIX[cred] + b"\x00" * 11 + ADDRESS)
            source_address = ADDRESS if _s(sol, "source_address_matches") == "T" else OTHER_ADDRESS

            activation, exit_epoch = self._epochs(
                _s(sol, "validator_active") == "T",
                _s(sol, "validator_exiting") == "T",
                _s(sol, "validator_old_enough") == "T",
            )
            v.activation_epoch = spec.Epoch(activation)
            v.exit_epoch = spec.Epoch(exit_epoch)
            v.effective_balance = spec.Gwei(
                spec.MIN_ACTIVATION_BALANCE if _s(sol, "sufficient_effective_balance") == "T"
                else spec.MIN_ACTIVATION_BALANCE - 1
            )

        # Pending-partial-withdrawals queue: target entry (for has_pending) + padding
        # for partial_queue_full, keeping the queue length exactly at the limit.
        pending_for_target = found and _s(sol, "has_pending_partial_withdrawal") == "T"
        entries = []
        if pending_for_target:
            entries.append(spec.PendingPartialWithdrawal(
                validator_index=spec.ValidatorIndex(TARGET_INDEX), amount=spec.Gwei(1),
                withdrawable_epoch=spec.Epoch(CURRENT_EPOCH),
            ))
        if _b(sol, "partial_queue_full"):
            filler_index = spec.ValidatorIndex(1)
            while len(entries) < int(spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT):
                entries.append(spec.PendingPartialWithdrawal(
                    validator_index=filler_index, amount=spec.Gwei(1),
                    withdrawable_epoch=spec.Epoch(CURRENT_EPOCH),
                ))
        pre.pending_partial_withdrawals = type(pre.pending_partial_withdrawals)(*entries)

        if found:
            pending_amount = 1 if pending_for_target else 0
            if _s(sol, "has_excess_balance") == "T":
                balance = spec.MIN_ACTIVATION_BALANCE + pending_amount + PARTIAL_AMOUNT
            else:
                balance = spec.MIN_ACTIVATION_BALANCE + pending_amount  # not strictly greater
            pre.balances[TARGET_INDEX] = spec.Gwei(balance)

        request = spec.WithdrawalRequest(
            source_address=spec.ExecutionAddress(source_address),
            validator_pubkey=spec.BLSPubkey(pre.validators[TARGET_INDEX].pubkey if found else ABSENT_PUBKEY),
            amount=spec.Gwei(0) if is_full else spec.Gwei(PARTIAL_AMOUNT),
        )

        post = pre.copy()
        spec.process_withdrawal_request(post, request)  # never raises

        claimed = {n: (_b(sol, n) if isinstance(getattr(sol, n), bool) else _s(sol, n)) for n in _DIMS}
        meta = {"description": f"process_withdrawal_request: {claimed['outcome']}", "claimed": claimed}
        parts = [
            ("pre", "ssz", pre.encode_bytes()),
            ("withdrawal_request", "ssz", request.encode_bytes()),
            ("post", "ssz", post.encode_bytes()),
        ]
        return meta, parts
