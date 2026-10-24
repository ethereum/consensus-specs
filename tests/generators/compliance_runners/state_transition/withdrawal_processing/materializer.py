"""Materialize pending-builder and aggregate withdrawal TARGET witnesses."""

from __future__ import annotations

from functools import cache
from typing import Any

from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.state_transition.builder_pending_withdrawal_processing.target import (
    TARGET as PENDING_TARGET,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.materializer.common import (
    BIG,
    make_base_state,
    set_parent_block,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled

from .target import TARGET

BUILDER_ADDRESS = b"\x42" * 20
VALIDATOR_ADDRESS = b"\x43" * 20


@cache
def _padding_pubkey(index: int) -> bytes:
    # Separate these inactive registry entries from the helper signing keys.
    with bls_enabled():
        return bls.SkToPk(2**40 + index)


def _builder_params_from_dims(spec: Any, state_epoch: int, rec: dict[str, Any]) -> dict[str, Any]:
    """Pick concrete Builder container fields from the entry's builder dims."""
    min_deposit = int(spec.MIN_DEPOSIT_AMOUNT)

    version = (
        spec.PAYLOAD_BUILDER_VERSION
        if rec["payload_builder_version"]
        else spec.Uint8(spec.PAYLOAD_BUILDER_VERSION + 1)
    )

    if rec["cmp_state_epoch_deposit_epoch"] == "EQ":
        deposit_epoch = state_epoch
    elif rec["cmp_state_epoch_deposit_epoch"] == "GT":
        deposit_epoch = max(0, state_epoch - 2)
    else:  # LT
        deposit_epoch = state_epoch + 2

    if not rec["withdrawable_epoch_set"]:
        withdrawable_epoch = spec.FAR_FUTURE_EPOCH
    else:
        w_cmp = rec["cmp_state_epoch_withdrawal_epoch"]
        if w_cmp == "EQ":
            withdrawable_epoch = spec.Epoch(state_epoch)
        elif w_cmp == "GT":
            withdrawable_epoch = spec.Epoch(max(0, state_epoch - 1))
        else:  # LT
            withdrawable_epoch = spec.Epoch(state_epoch + 1)

    if rec["cmp_balance_zero"] == "EQ":
        balance = 0
    elif rec["cmp_balance_min_deposit"] == "LT":
        balance = max(1, min_deposit - 1)
    elif rec["cmp_balance_min_deposit"] == "EQ":
        balance = min_deposit
    else:  # GT
        balance = min_deposit + BIG

    return {
        "pubkey": spec.BLSPubkey(builder_pubkeys[0]),
        "version": version,
        "execution_address": spec.ExecutionAddress(BUILDER_ADDRESS),
        "balance": spec.Gwei(balance),
        "deposit_epoch": spec.Epoch(deposit_epoch),
        "withdrawable_epoch": withdrawable_epoch,
    }


def _pick_finalized_epoch(rec: dict[str, Any], deposit_epoch: int) -> int:
    if rec["cmp_finalized_epoch_deposit_epoch"] == "LT":
        return max(0, deposit_epoch - 1)
    elif rec["cmp_finalized_epoch_deposit_epoch"] == "EQ":
        return deposit_epoch
    else:  # GT
        return deposit_epoch + 1


# --- withdrawal_processing helpers ---


def _pick_builder_queue_len(rec: dict[str, Any], limit: int, max_partials: int) -> int:
    """Pick a concrete builder pending-withdrawal queue length from the bool dims."""
    if not rec["builder_pending_withdrawals_exist"]:
        return 0
    # Add one entry beyond the available capacity.  This makes
    # get_builder_withdrawals evaluate ``has_reached_limit`` as true and take
    # its ``break`` branch, rather than merely exhausting the queue at the
    # same count.
    if rec["builder_pending_withdrawals_hit_limit"]:
        return limit + 1
    if rec["validator_pending_withdrawals_hit_limit"]:
        # Leave exactly the partial-source capacity before the shared limit.
        return max(1, limit - max_partials)
    return 1


def _pick_validator_queue_len(rec: dict[str, Any], max_partials: int) -> int:
    """Pick a concrete validator pending-withdrawal queue length from the bool dims."""
    if not rec["validator_pending_withdrawals_exist"]:
        return 0
    # Queue non-empty; all entries are either withdrawable or not.
    if not rec["eligible_validator_pending_withdrawals_exist"]:
        return 1
    # Eligible entries exist; hitting the limit means the partial source reaches
    # MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, so the queue length equals that cap.
    if rec["validator_pending_withdrawals_hit_limit"]:
        return max_partials
    return 1


def _pick_sweep(
    rec: dict[str, Any],
    limit: int,
    max_per_sweep: int,
    queue_len: int,
) -> tuple[int, int, list[int]]:
    """Pick (builders_count, next_index, eligible_positions) realizing the sweep dims."""
    bc = {
        "LT": limit + 1,
        "EQ": max_per_sweep,
        "GT": max_per_sweep + 1,
    }[rec["cmp_builder_count_max_per_sweep"]]

    if rec["cmp_next_index_zero"] == "EQ":
        ni = 0
    elif rec["cmp_next_index_last_builder_index"] == "EQ":
        ni = bc - 1
    else:
        ni = 1

    prior = queue_len
    eligible_zero = rec["cmp_eligible_builder_count_zero"]
    swept_zero = rec["cmp_swept_count_zero"]
    hit = rec["swept_builders_hit_withdrawals_limit"]

    if eligible_zero == "EQ":
        positions: list[int] = []
    elif swept_zero == "EQ":
        if prior >= limit:
            positions = [0]
        else:
            positions = [(ni - 1) % bc]
    elif hit:
        k = limit - prior
        positions = [(ni + i) % bc for i in range(k)]
    else:
        positions = [ni % bc]

    return bc, ni, positions


def _builder_params(
    spec: Any, state_epoch: int, builder_index: int, withdrawable_epoch: Any
) -> dict[str, Any]:
    """Use a concrete ordinary builder; only sweep eligibility is projected."""
    return {
        "pubkey": spec.BLSPubkey(builder_pubkeys[builder_index % len(builder_pubkeys)]),
        "version": spec.PAYLOAD_BUILDER_VERSION,
        "execution_address": spec.ExecutionAddress(BUILDER_ADDRESS),
        "balance": spec.Gwei(int(spec.MIN_DEPOSIT_AMOUNT) + BIG),
        "deposit_epoch": spec.Epoch(max(0, state_epoch - 1)),
        "withdrawable_epoch": withdrawable_epoch,
    }


class WithdrawalProcessingMaterializer(Materializer):
    """Materialize the two separately registered withdrawal providers."""

    runner_name = "operations"
    handler_name = "withdrawals"

    def __init__(
        self,
        spec: Any,
        fork_name="gloas",
        preset_name="minimal",
        seed: int = 0,
    ):
        super().__init__(spec, fork_name, preset_name, seed)
        # Precompute the preprocessed base state once; each solution starts from a copy.
        self._base = make_base_state(spec)
        self._outside_sweep_base = None

    def _validator_sweep_base(self, *, outside_window: bool):
        """Provide an actual registry position beyond the preset's sweep window."""
        window = int(self.spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
        if not outside_window or len(self._base.validators) > window:
            return self._base.copy()
        if self._outside_sweep_base is None:
            state = self._base.copy()
            for index in range(len(state.validators), window + 1):
                pubkey = _padding_pubkey(index)
                self.spec.add_validator_to_registry(
                    state,
                    self.spec.BLSPubkey(pubkey),
                    self.spec.Bytes32(
                        self.spec.BLS_WITHDRAWAL_PREFIX + self.spec.sha256(pubkey)[1:]
                    ),
                    self.spec.MIN_DEPOSIT_AMOUNT,
                )
            self._outside_sweep_base = state
        return self._outside_sweep_base.copy()

    def _materialize_validator_partial(
        self, pre: Any, state_epoch: int, eligible: bool, queue_len: int
    ) -> None:
        spec = self.spec
        index = 0
        validator = pre.validators[index]
        validator.withdrawal_credentials = spec.Bytes32(b"\x02" + b"\x00" * 11 + VALIDATOR_ADDRESS)
        validator.effective_balance = spec.MIN_ACTIVATION_BALANCE
        validator.exit_epoch = spec.FAR_FUTURE_EPOCH
        validator.withdrawable_epoch = spec.FAR_FUTURE_EPOCH
        amount = 1_000_000
        # Each processed entry must emit a real withdrawal. Otherwise the
        # processed-entry count differs from the prior-output count for sweeps.
        pre.balances[index] = spec.Gwei(int(spec.MIN_ACTIVATION_BALANCE) + (queue_len + 1) * amount)
        for _ in range(queue_len):
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(index),
                    amount=spec.Gwei(amount),
                    withdrawable_epoch=spec.Epoch(state_epoch if eligible else state_epoch + 1),
                )
            )

    def _make_fully_withdrawable(self, pre: Any, idx: int, state_epoch: int) -> None:
        """Make the validator at `idx` fully withdrawable (execution credential,
        withdrawable_epoch <= current epoch, balance > 0)."""
        spec = self.spec
        old = pre.validators[idx]
        pre.validators[idx] = spec.Validator(
            pubkey=old.pubkey,
            withdrawal_credentials=spec.Bytes32(b"\x01" + b"\x00" * 11 + VALIDATOR_ADDRESS),
            effective_balance=old.effective_balance,
            slashed=False,
            activation_eligibility_epoch=old.activation_eligibility_epoch,
            activation_epoch=old.activation_epoch,
            exit_epoch=old.exit_epoch,
            withdrawable_epoch=spec.Epoch(state_epoch),
        )
        pre.balances[idx] = spec.Gwei(1_000_000)

    def _make_partially_withdrawable(self, pre: Any, idx: int) -> None:
        """Make the validator at ``idx`` sweepable for its excess balance."""
        spec = self.spec
        old = pre.validators[idx]
        pre.validators[idx] = spec.Validator(
            pubkey=old.pubkey,
            withdrawal_credentials=spec.Bytes32(b"\x02" + b"\x00" * 11 + VALIDATOR_ADDRESS),
            effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            slashed=False,
            activation_eligibility_epoch=old.activation_eligibility_epoch,
            activation_epoch=old.activation_epoch,
            exit_epoch=spec.FAR_FUTURE_EPOCH,
            withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        )
        pre.balances[idx] = spec.Gwei(int(spec.MAX_EFFECTIVE_BALANCE_ELECTRA) + BIG)

    def materialize_solution(self, sol: Any) -> tuple[dict, list]:
        rec = vars(sol)
        pending = "cmp_pending_amount_zero" in rec
        if pending:
            pre, post = self._materialize_pending_withdrawal(rec)
        else:
            pre, post = self._materialize_withdrawal_processing(rec)
        claimed = self.claimed_record(PENDING_TARGET if pending else TARGET, sol)
        parts = [("pre", "ssz", pre.encode_bytes()), ("post", "ssz", post.encode_bytes())]
        description = (
            "builder_pending_withdrawal_processing" if pending else "withdrawal_processing"
        )
        return {"description": f"{description}: {claimed}", "claimed": claimed}, parts

    def _materialize_pending_withdrawal(self, rec: dict) -> tuple[Any, Any]:
        spec = self.spec

        pre = self._base.copy()
        state_epoch = int(spec.get_current_epoch(pre))

        set_parent_block(spec, pre, rec["state_latest_block_hash_match"])

        # One real pending withdrawal: add the referenced builder and the
        # pending-withdrawal entry. The builder's computed Builder solution
        # must match the entry's embedded builder dims.
        params = _builder_params_from_dims(spec, state_epoch, rec)
        pre.builders.append(spec.Builder(**params))
        builder_index = len(pre.builders) - 1

        deposit_epoch = int(params["deposit_epoch"])
        finalized_epoch = _pick_finalized_epoch(rec, deposit_epoch)
        pre.finalized_checkpoint = spec.Checkpoint(
            epoch=spec.Epoch(finalized_epoch),
            root=spec.Root(b"\x01" * 32),
        )

        # Pending withdrawal amount per cmp_builder_balance_amount
        # (cmp_pending_amount_zero is GT: amount > 0 by construction).
        balance = int(params["balance"])
        cmp_bal_amount = rec["cmp_builder_balance_amount"]
        if cmp_bal_amount == "LT":
            amount = balance + 1
        elif cmp_bal_amount == "EQ":
            amount = balance
        else:  # GT
            amount = balance - 1

        pre.builder_pending_withdrawals.append(
            spec.BuilderPendingWithdrawal(
                fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                amount=spec.Gwei(amount),
                builder_index=spec.BuilderIndex(builder_index),
            )
        )

        # has_pending_payments == T requires a matching pending payment
        if rec["has_pending_payments"]:
            pre.builder_pending_payments[0] = spec.BuilderPendingPayment(
                weight=spec.Gwei(1),
                withdrawal=spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                    amount=spec.Gwei(1000),
                    builder_index=spec.BuilderIndex(builder_index),
                ),
                proposer_index=spec.ValidatorIndex(0),
            )

        post = pre.copy()
        spec.process_withdrawals(post)
        return pre, post

    def _materialize_withdrawal_processing(self, rec: dict) -> tuple[Any, Any]:
        spec = self.spec

        limit = int(spec.MAX_WITHDRAWALS_PER_PAYLOAD) - 1
        max_per_sweep = int(spec.MAX_BUILDERS_PER_WITHDRAWALS_SWEEP)
        builder_queue_len = _pick_builder_queue_len(
            rec, limit, int(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP)
        )
        validator_queue_len = _pick_validator_queue_len(
            rec, int(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP)
        )
        eligible = rec["eligible_validator_pending_withdrawals_exist"]

        # Withdrawals drained by the builder pending and validator partial
        # sources before the builder sweep (get_builder_withdrawals +
        # get_pending_partial_withdrawals), which is the builder sweep's prior.
        processed_builder = min(builder_queue_len, limit)
        processed_partial = min(validator_queue_len, limit - processed_builder) if eligible else 0
        sweep_prior = processed_builder + processed_partial

        bc, ni, positions = _pick_sweep(rec, limit, max_per_sweep, sweep_prior)

        pre = self._validator_sweep_base(
            outside_window=(
                rec["validators_eligible_for_sweep_exist"]
                and not rec["swept_validators_hit_limit"]
                and not rec["partial_validator_sweep_withdrawal"]
            )
        )
        state_epoch = int(spec.get_current_epoch(pre))

        set_parent_block(spec, pre, rec["state_latest_block_hash_match"])

        finalized_epoch = state_epoch + 1
        pre.finalized_checkpoint = spec.Checkpoint(
            epoch=spec.Epoch(finalized_epoch),
            root=spec.Root(b"\x01" * 32),
        )

        eligible_set = set(positions)
        active_indices = [i for i in range(bc) if i not in eligible_set][:builder_queue_len]

        for i in range(bc):
            wd = spec.Epoch(state_epoch) if i in eligible_set else spec.FAR_FUTURE_EPOCH
            pre.builders.append(spec.Builder(**_builder_params(spec, state_epoch, i, wd)))

        pre.next_withdrawal_builder_index = spec.BuilderIndex(ni)

        # Builder pending withdrawal queue entries.
        balance = int(spec.MIN_DEPOSIT_AMOUNT) + BIG
        amount_cmp = self.rng.choice(["LT", "EQ", "GT"])
        if amount_cmp == "LT":
            amount = balance + 1
        elif amount_cmp == "EQ":
            amount = balance
        else:  # GT
            amount = balance - 1
        # Pending withdrawals may refer to the same active builder.  Reuse
        # indices when the boundary vector needs more queue entries than the
        # minimal builder set has active builders.
        queue_builder_indices = [
            active_indices[i % len(active_indices)] for i in range(builder_queue_len)
        ]
        for idx in queue_builder_indices:
            pre.builder_pending_withdrawals.append(
                spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                    amount=spec.Gwei(amount),
                    builder_index=spec.BuilderIndex(idx),
                )
            )

        # Validator pending partial withdrawal queue entries.
        if validator_queue_len > 0:
            self._materialize_validator_partial(pre, state_epoch, eligible, validator_queue_len)

        # Validator sweep: control fully-withdrawable validators to realize
        # validators_eligible_for_sweep_exist / swept_validators_hit_limit.
        pre.next_withdrawal_validator_index = spec.ValidatorIndex(0)
        window_end = int(spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
        partial_sweep = rec["partial_validator_sweep_withdrawal"]
        partial_index = 1
        if partial_sweep:
            self._make_partially_withdrawable(pre, partial_index)
        if rec["swept_validators_hit_limit"]:
            # Fill the sweep window (skipping the pending-partial validator at 0)
            # so the validator sweep drains the remaining capacity to the limit.
            for idx in range(1, min(window_end, len(pre.validators))):
                if idx != partial_index:
                    self._make_fully_withdrawable(pre, idx, state_epoch)
        elif rec["validators_eligible_for_sweep_exist"]:
            if not partial_sweep:
                # A single eligible validator outside the sweep window.
                self._make_fully_withdrawable(pre, window_end, state_epoch)

        post = pre.copy()
        spec.process_withdrawals(post)
        return pre, post

    def describe(self, claimed: dict) -> str:
        if "cmp_builder_balance_amount" in claimed:
            return f"builder_pending_withdrawal_processing: {claimed}"
        return f"withdrawal_processing: {claimed}"


MATERIALIZER = WithdrawalProcessingMaterializer
