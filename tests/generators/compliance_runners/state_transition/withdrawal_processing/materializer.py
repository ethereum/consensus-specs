"""Materialize builder_pending_withdrawal_processing and withdrawal_processing
aspect-model solutions into process_withdrawals cases.

Solves both aspect models (all feasible BuilderPendingWithdrawalProcessing and
WithdrawalProcessing records), materializes each solution into a concrete
pre/post BeaconState vector, and verifies each via the corresponding validator.

Spec: specs/gloas/beacon-chain.md get_builder_withdrawals / process_withdrawals.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.withdrawal_processing.materializer
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import minizinc

from eth_consensus_specs.test.helpers.keys import builder_pubkeys
from tests.generators.compliance_runners.state_transition.aspects.base import (
    Bool,
    Cmp,
    OpBool,
    OpCmp,
    ValidatorCredentialKind,
)
from tests.generators.compliance_runners.state_transition.aspects.builder.builder import (
    Builder as BuilderSolution,
    is_self_builder,
    is_sweep_eligible,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.builder_sweep import (
    BuilderSweep,
)
from tests.generators.compliance_runners.state_transition.aspects.builder_withdrawals.pending_withdrawal import (
    BuilderPendingWithdrawal,
)
from tests.generators.compliance_runners.state_transition.aspects.validator.validator import (
    Validator,
)
from tests.generators.compliance_runners.state_transition.aspects.validator_withdrawals.pending_partial_withdrawal import (
    ValidatorPendingPartialWithdrawal,
)
from tests.generators.compliance_runners.state_transition.aspects.withdrawal_processing.builder_pending_withdrawal_processing import (
    BuilderPendingWithdrawalProcessing,
)
from tests.generators.compliance_runners.state_transition.aspects.withdrawal_processing.builder_pending_withdrawal_processing_validator import (
    builder_pending_withdrawal_processing_validator,
)
from tests.generators.compliance_runners.state_transition.aspects.withdrawal_processing.withdrawal_processing import (
    WithdrawalProcessing,
)
from tests.generators.compliance_runners.state_transition.aspects.withdrawal_processing.withdrawal_processing_validator import (
    withdrawal_processing_validator,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.materializer.common import (
    BIG,
    BOOL,
    CMP,
    make_base_state,
    OP_BOOL,
    OP_CMP,
    set_parent_block,
    to_builder_solution,
)

BUILDER_ADDRESS = b"\x42" * 20
VALIDATOR_ADDRESS = b"\x43" * 20

_cred = {
    "BLS": ValidatorCredentialKind.BLS,
    "ETH1": ValidatorCredentialKind.ETH1,
    "COMPOUNDING": ValidatorCredentialKind.COMPOUNDING,
}

PENDING_WITHDRAWAL_DIMS = [
    "state_latest_block_hash_match",
    "cmp_pending_amount_zero",
    "cmp_builder_balance_amount",
    # embedded builder sub-dimensions
    "payload_builder_version",
    "cmp_state_epoch_deposit_epoch",
    "cmp_state_epoch_withdrawal_epoch",
    "cmp_finalized_epoch_deposit_epoch",
    "withdrawable_epoch_set",
    "cmp_balance_zero",
    "cmp_balance_min_deposit",
    "has_pending_payments",
    "has_pending_withdrawals",
]

WITHDRAWAL_PROCESSING_DIMS = [
    "state_latest_block_hash_match",
    "builder_pending_withdrawals_exist",
    "builder_pending_withdrawals_hit_limit",
    "validator_pending_withdrawals_exist",
    "eligible_validator_pending_withdrawals_exist",
    "validator_pending_withdrawals_hit_limit",
    "validators_eligible_for_sweep_exist",
    "swept_validators_hit_limit",
    "cmp_builder_count_withdrawals_limit",
    "cmp_builder_count_max_per_sweep",
    "cmp_eligible_builder_count_zero",
    "cmp_swept_count_zero",
    "cmp_swept_count_max_per_sweep",
    "cmp_next_index_zero",
    "cmp_next_index_last_builder_index",
    "swept_builders_hit_withdrawals_limit",
]


# --- builder_pending_withdrawal_processing helpers ---


def _normalize_pending_withdrawal(sol: Any) -> dict[str, Any]:
    """Flatten a MiniZinc solution into a {field: value} dict."""
    p = sol.p
    entry = p["pending_withdrawal"]
    rec: dict[str, Any] = {
        "state_latest_block_hash_match": str(p["state_latest_block_hash_match"]),
        "cmp_pending_amount_zero": str(entry["cmp_pending_amount_zero"]),
        "cmp_builder_balance_amount": str(entry["cmp_builder_balance_amount"]),
    }
    for k, v in entry["builder"].items():
        rec[k] = str(v)
    return rec


def _to_pending_withdrawal_solution(rec: dict[str, Any]) -> BuilderPendingWithdrawalProcessing:
    entry = BuilderPendingWithdrawal(
        builder=to_builder_solution(rec),
        cmp_pending_amount_zero=OP_CMP[rec["cmp_pending_amount_zero"]],
        cmp_builder_balance_amount=OP_CMP[rec["cmp_builder_balance_amount"]],
    )
    return BuilderPendingWithdrawalProcessing(
        state_latest_block_hash_match=BOOL[rec["state_latest_block_hash_match"]],
        pending_withdrawal=entry,
    )


def _builder_params_from_dims(spec: Any, state_epoch: int, rec: dict[str, Any]) -> dict[str, Any]:
    """Pick concrete Builder container fields from the entry's builder dims."""
    min_deposit = int(spec.MIN_DEPOSIT_AMOUNT)

    version = (
        spec.PAYLOAD_BUILDER_VERSION
        if rec["payload_builder_version"] == "T"
        else spec.Uint8(spec.PAYLOAD_BUILDER_VERSION + 1)
    )

    if rec["cmp_state_epoch_deposit_epoch"] == "EQ":
        deposit_epoch = state_epoch
    elif rec["cmp_state_epoch_deposit_epoch"] == "GT":
        deposit_epoch = max(0, state_epoch - 2)
    else:  # LT
        deposit_epoch = state_epoch + 2

    if rec["withdrawable_epoch_set"] == "F":
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


def _normalize_withdrawal_processing(sol: Any) -> dict[str, Any]:
    p = sol.p
    rec: dict[str, Any] = {
        "state_latest_block_hash_match": str(p["state_latest_block_hash_match"]),
        "builder_pending_withdrawals_exist": str(p["builder_pending_withdrawals_exist"]),
        "builder_pending_withdrawals_hit_limit": str(p["builder_pending_withdrawals_hit_limit"]),
        "validator_pending_withdrawals_exist": str(p["validator_pending_withdrawals_exist"]),
        "eligible_validator_pending_withdrawals_exist": str(
            p["eligible_validator_pending_withdrawals_exist"]
        ),
        "validator_pending_withdrawals_hit_limit": str(
            p["validator_pending_withdrawals_hit_limit"]
        ),
        "validators_eligible_for_sweep_exist": str(p["validators_eligible_for_sweep_exist"]),
        "swept_validators_hit_limit": str(p["swept_validators_hit_limit"]),
        "builder_sweep": {k: str(v) for k, v in p["builder_sweep"].items()},
    }
    return rec


def _to_sweep(bs: dict[str, str]) -> BuilderSweep:
    return BuilderSweep(
        cmp_builder_count_withdrawals_limit=CMP[bs["cmp_builder_count_withdrawals_limit"]],
        cmp_builder_count_max_per_sweep=CMP[bs["cmp_builder_count_max_per_sweep"]],
        cmp_eligible_builder_count_zero=CMP[bs["cmp_eligible_builder_count_zero"]],
        cmp_swept_count_zero=CMP[bs["cmp_swept_count_zero"]],
        cmp_swept_count_max_per_sweep=CMP[bs["cmp_swept_count_max_per_sweep"]],
        cmp_next_index_zero=CMP[bs["cmp_next_index_zero"]],
        cmp_next_index_last_builder_index=CMP[bs["cmp_next_index_last_builder_index"]],
        swept_builders_hit_withdrawals_limit=BOOL[bs["swept_builders_hit_withdrawals_limit"]],
    )


def _to_withdrawal_processing_solution(rec: dict[str, Any]) -> WithdrawalProcessing:
    builder_sweep_dims = rec.get(
        "builder_sweep",
        {
            name: rec[name]
            for name in (
                "cmp_builder_count_withdrawals_limit",
                "cmp_builder_count_max_per_sweep",
                "cmp_eligible_builder_count_zero",
                "cmp_swept_count_zero",
                "cmp_swept_count_max_per_sweep",
                "cmp_next_index_zero",
                "cmp_next_index_last_builder_index",
                "swept_builders_hit_withdrawals_limit",
            )
        },
    )
    return WithdrawalProcessing(
        state_latest_block_hash_match=BOOL[rec["state_latest_block_hash_match"]],
        builder_pending_withdrawals_exist=BOOL[rec["builder_pending_withdrawals_exist"]],
        builder_pending_withdrawals_hit_limit=BOOL[rec["builder_pending_withdrawals_hit_limit"]],
        validator_pending_withdrawals_exist=BOOL[rec["validator_pending_withdrawals_exist"]],
        eligible_validator_pending_withdrawals_exist=BOOL[
            rec["eligible_validator_pending_withdrawals_exist"]
        ],
        validator_pending_withdrawals_hit_limit=BOOL[
            rec["validator_pending_withdrawals_hit_limit"]
        ],
        validators_eligible_for_sweep_exist=BOOL[rec["validators_eligible_for_sweep_exist"]],
        swept_validators_hit_limit=BOOL[rec["swept_validators_hit_limit"]],
        builder_sweep=_to_sweep(builder_sweep_dims),
    )


def _to_validator_solution(rec: dict[str, str]) -> Validator:
    return Validator(
        withdrawal_credential=_cred[rec["withdrawal_credential"]],
        cmp_state_epoch_activation_epoch=CMP[rec["cmp_state_epoch_activation_epoch"]],
        cmp_state_epoch_exit_epoch=CMP[rec["cmp_state_epoch_exit_epoch"]],
        cmp_state_epoch_withdrawal_epoch=CMP[rec["cmp_state_epoch_withdrawal_epoch"]],
        cmp_finalized_epoch_activation_eligibility_epoch=CMP[
            rec["cmp_finalized_epoch_activation_eligibility_epoch"]
        ],
        withdrawable_epoch_set=BOOL[rec["withdrawable_epoch_set"]],
        exit_epoch_set=BOOL[rec["exit_epoch_set"]],
        cmp_balance_zero=CMP[rec["cmp_balance_zero"]],
        cmp_effective_balance_min_activation_balance=CMP[
            rec["cmp_effective_balance_min_activation_balance"]
        ],
        has_pending_withdrawal=BOOL[rec["has_pending_withdrawal"]],
    )


def _enumerate_all_builder_solutions(model_path: Path) -> list[BuilderSolution]:
    model = minizinc.Model(str(model_path))
    inst = minizinc.Instance(minizinc.Solver.lookup("gecode"), model)
    result = inst.solve(all_solutions=True)
    solutions = []
    for sol in result:
        b = sol.b
        solutions.append(
            BuilderSolution(
                payload_builder_version=OP_BOOL[str(b["payload_builder_version"])],
                cmp_state_epoch_deposit_epoch=OP_CMP[str(b["cmp_state_epoch_deposit_epoch"])],
                cmp_state_epoch_withdrawal_epoch=OP_CMP[str(b["cmp_state_epoch_withdrawal_epoch"])],
                cmp_finalized_epoch_deposit_epoch=OP_CMP[
                    str(b["cmp_finalized_epoch_deposit_epoch"])
                ],
                withdrawable_epoch_set=OP_BOOL[str(b["withdrawable_epoch_set"])],
                cmp_balance_zero=OP_CMP[str(b["cmp_balance_zero"])],
                cmp_balance_min_deposit=OP_CMP[str(b["cmp_balance_min_deposit"])],
                has_pending_payments=OP_BOOL[str(b["has_pending_payments"])],
                has_pending_withdrawals=OP_BOOL[str(b["has_pending_withdrawals"])],
            )
        )
    return solutions


def _enumerate_all_pending_withdrawal_solutions(model_path: Path) -> list[BuilderPendingWithdrawal]:
    model = minizinc.Model(str(model_path))
    inst = minizinc.Instance(minizinc.Solver.lookup("gecode"), model)
    result = inst.solve(all_solutions=True)
    solutions = []
    for sol in result:
        w = sol.p["pending_withdrawal"]
        builder = to_builder_solution({k: str(v) for k, v in w["builder"].items()})
        solutions.append(
            BuilderPendingWithdrawal(
                builder=builder,
                cmp_pending_amount_zero=OP_CMP[str(w["cmp_pending_amount_zero"])],
                cmp_builder_balance_amount=OP_CMP[str(w["cmp_builder_balance_amount"])],
            )
        )
    return solutions


def _enumerate_all_validator_pending_withdrawal_solutions(
    model_path: Path,
) -> list[ValidatorPendingPartialWithdrawal]:
    model = minizinc.Model(str(model_path))
    inst = minizinc.Instance(minizinc.Solver.lookup("gecode"), model)
    result = inst.solve(all_solutions=True)
    solutions = []
    for sol in result:
        w = sol.w
        validator = _to_validator_solution({k: str(v) for k, v in w["validator"].items()})
        solutions.append(
            ValidatorPendingPartialWithdrawal(
                validator=validator,
                withdrawable=BOOL[str(w["withdrawable"])],
                cmp_pending_amount_zero=CMP[str(w["cmp_pending_amount_zero"])],
                cmp_balance_amount=CMP[str(w["cmp_balance_amount"])],
            )
        )
    return solutions


def _pick_builder_queue_len(rec: dict[str, Any], limit: int) -> int:
    """Pick a concrete builder pending-withdrawal queue length from the bool dims."""
    if rec["builder_pending_withdrawals_exist"] == "F":
        return 0
    return limit if rec["builder_pending_withdrawals_hit_limit"] == "T" else 1


def _pick_validator_queue_len(rec: dict[str, Any], max_partials: int) -> int:
    """Pick a concrete validator pending-withdrawal queue length from the bool dims."""
    if rec["validator_pending_withdrawals_exist"] == "F":
        return 0
    # Queue non-empty; all entries are either withdrawable or not.
    if rec["eligible_validator_pending_withdrawals_exist"] == "F":
        return 1
    # Eligible entries exist; hitting the limit means the partial source reaches
    # MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, so the queue length equals that cap.
    if rec["validator_pending_withdrawals_hit_limit"] == "T":
        return max_partials
    return 1


def _pick_sweep(
    rec: dict[str, Any],
    limit: int,
    max_per_sweep: int,
    queue_len: int,
) -> tuple[int, int, list[int]]:
    """Pick (builders_count, next_index, eligible_positions) realizing the sweep dims."""
    bs = rec.get("builder_sweep", rec)
    bc = {
        "LT": limit + 1,
        "EQ": max_per_sweep,
        "GT": max_per_sweep + 1,
    }[bs["cmp_builder_count_max_per_sweep"]]

    if bs["cmp_next_index_zero"] == "EQ":
        ni = 0
    elif bs["cmp_next_index_last_builder_index"] == "EQ":
        ni = bc - 1
    else:
        ni = 1

    prior = queue_len
    eligible_zero = bs["cmp_eligible_builder_count_zero"]
    swept_zero = bs["cmp_swept_count_zero"]
    hit = bs["swept_builders_hit_withdrawals_limit"]

    if eligible_zero == "EQ":
        positions: list[int] = []
    elif swept_zero == "EQ":
        if prior >= limit:
            positions = [0]
        else:
            positions = [(ni - 1) % bc]
    elif hit == "T":
        k = limit - prior
        positions = [(ni + i) % bc for i in range(k)]
    else:
        positions = [ni % bc]

    return bc, ni, positions


def _builder_params(
    spec: Any,
    state_epoch: int,
    bs: BuilderSolution,
    builder_index: int,
    withdrawable_epoch: Any,
) -> dict[str, Any]:
    min_deposit = int(spec.MIN_DEPOSIT_AMOUNT)
    version = (
        spec.PAYLOAD_BUILDER_VERSION
        if bs.payload_builder_version == OpBool.T
        else spec.Uint8(spec.PAYLOAD_BUILDER_VERSION + 1)
    )
    deposit_epoch = (
        state_epoch if bs.cmp_state_epoch_deposit_epoch == OpCmp.EQ else max(0, state_epoch - 2)
    )
    balance = min_deposit if bs.cmp_balance_min_deposit == OpCmp.EQ else min_deposit + BIG
    return {
        "pubkey": spec.BLSPubkey(builder_pubkeys[builder_index % len(builder_pubkeys)]),
        "version": version,
        "execution_address": spec.ExecutionAddress(BUILDER_ADDRESS),
        "balance": spec.Gwei(balance),
        "deposit_epoch": spec.Epoch(deposit_epoch),
        "withdrawable_epoch": withdrawable_epoch,
    }


class WithdrawalProcessingMaterializer(Materializer):
    """Materializes each solution of both withdrawal-processing aspect models."""

    runner_name = "operations"
    handler_name = "withdrawals"

    def __init__(self, spec: Any, fork_name="gloas", preset_name="minimal"):
        aspects = Path(__file__).parent.parent / "aspects"
        self.pending_withdrawal_model_path = (
            aspects / "withdrawal_processing" / "builder_pending_withdrawal_processing.mzn"
        )
        self.withdrawal_processing_model_path = (
            aspects / "withdrawal_processing" / "withdrawal_processing.mzn"
        )
        super().__init__(spec, fork_name, preset_name)
        # Precompute the preprocessed base state once; each solution starts from a copy.
        self._base = make_base_state(spec)

        builder_enum_path = aspects / "builder" / "builder_enumerate.mzn"
        self.all_builder_solutions = _enumerate_all_builder_solutions(builder_enum_path)

        bpw_enum_path = (
            aspects / "withdrawal_processing" / "builder_pending_withdrawal_processing.mzn"
        )
        self.all_builder_pending_withdrawal_solutions = _enumerate_all_pending_withdrawal_solutions(
            bpw_enum_path
        )

        vpw_enum_path = (
            aspects / "validator_withdrawals" / "pending_partial_withdrawal_enumerate.mzn"
        )
        self.all_validator_pending_withdrawal_solutions = (
            _enumerate_all_validator_pending_withdrawal_solutions(vpw_enum_path)
        )

        # Eligible builder candidates: sweep-eligible with a uniform
        # finalized>deposit comparison, so a single global finalized epoch is
        # consistent for every builder.
        self._ref_candidates = [
            bs
            for bs in self.all_builder_solutions
            if not is_self_builder(bs)
            and is_sweep_eligible(bs)
            and bs.has_pending_payments == OpBool.F
            and bs.has_pending_withdrawals == OpBool.F
            and bs.cmp_finalized_epoch_deposit_epoch == OpCmp.GT
        ]

        # Active (pending-withdrawal) builder candidates with no pending payment.
        self._active_candidates = [
            bs
            for bs in self.all_builder_solutions
            if not is_self_builder(bs)
            and bs.has_pending_withdrawals == OpBool.T
            and bs.has_pending_payments == OpBool.F
            and bs.payload_builder_version == OpBool.T
        ]

    def _materialize_validator_partial(
        self,
        pre: Any,
        state_epoch: int,
        finalized_epoch: int,
        vs: Validator,
        template: ValidatorPendingPartialWithdrawal,
        queue_len: int,
    ) -> None:
        spec = self.spec
        min_act = int(spec.MIN_ACTIVATION_BALANCE)

        index = 0
        old = pre.validators[index]

        if vs.cmp_effective_balance_min_activation_balance == Cmp.EQ:
            effective_balance = min_act
        else:
            effective_balance = min_act + int(spec.EFFECTIVE_BALANCE_INCREMENT)

        if vs.cmp_state_epoch_activation_epoch == Cmp.EQ:
            activation_epoch = state_epoch
        elif vs.cmp_state_epoch_activation_epoch == Cmp.GT:
            activation_epoch = max(0, state_epoch - 1)
        else:
            activation_epoch = state_epoch + 1

        if vs.cmp_finalized_epoch_activation_eligibility_epoch == Cmp.EQ:
            eligibility_epoch = finalized_epoch
        elif vs.cmp_finalized_epoch_activation_eligibility_epoch == Cmp.GT:
            eligibility_epoch = max(0, finalized_epoch - 1)
        else:
            eligibility_epoch = finalized_epoch + 1

        new_validator = spec.Validator(
            pubkey=old.pubkey,
            withdrawal_credentials=spec.Bytes32(b"\x02" + b"\x00" * 11 + VALIDATOR_ADDRESS),
            effective_balance=spec.Gwei(effective_balance),
            slashed=False,
            activation_eligibility_epoch=spec.Epoch(eligibility_epoch),
            activation_epoch=spec.Epoch(activation_epoch),
            exit_epoch=spec.FAR_FUTURE_EPOCH,
            withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        )
        pre.validators[index] = new_validator

        balance = min_act + 1_000_000
        pre.balances[index] = spec.Gwei(balance)

        if template.cmp_balance_amount == CMP["LT"]:
            amount = balance + 1
        elif template.cmp_balance_amount == CMP["EQ"]:
            amount = balance
        else:
            amount = balance - 1

        withdrawable_epoch = (
            spec.Epoch(state_epoch)
            if template.withdrawable == Bool.T
            else spec.Epoch(state_epoch + 1)
        )

        for _ in range(queue_len):
            pre.pending_partial_withdrawals.append(
                spec.PendingPartialWithdrawal(
                    validator_index=spec.ValidatorIndex(index),
                    amount=spec.Gwei(amount),
                    withdrawable_epoch=withdrawable_epoch,
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

    def _record(self, sol: Any) -> dict[str, Any]:
        """Normalize a MiniZinc solution or a catalog representative."""
        if hasattr(sol, "p"):
            if "pending_withdrawal" in sol.p:
                return _normalize_pending_withdrawal(sol)
            rec = _normalize_withdrawal_processing(sol)
            rec.update(rec.pop("builder_sweep"))
            return rec
        return vars(sol).copy() if not isinstance(sol, dict) else sol.copy()

    def materialize_solution(self, sol: Any) -> tuple[dict, list]:
        random.seed(0)
        rec = self._record(sol)
        if "cmp_pending_amount_zero" in rec:
            pre, post, _verified, claimed, extra_parts = self._materialize_pending_withdrawal(rec)
        else:
            pre, post, _verified, claimed, extra_parts = self._materialize_withdrawal_processing(
                rec
            )

        parts = [("pre", "ssz", pre.encode_bytes())]
        parts.extend((name, "ssz", value.encode_bytes()) for name, value in extra_parts)
        if post is not None:
            parts.append(("post", "ssz", post.encode_bytes()))
        description = (
            "builder_pending_withdrawal_processing"
            if "cmp_pending_amount_zero" in claimed
            else "withdrawal_processing"
        )
        return {
            "description": f"{description}: {claimed}",
            "claimed": claimed,
            "verified": _verified,
        }, parts

    def _materialize_pending_withdrawal(self, sol: Any) -> tuple[Any, Any | None, bool, dict, list]:
        spec = self.spec
        rec = sol if isinstance(sol, dict) else self._record(sol)

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
        if rec["has_pending_payments"] == "T":
            pre.builder_pending_payments[0] = spec.BuilderPendingPayment(
                weight=spec.Gwei(1),
                withdrawal=spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                    amount=spec.Gwei(1000),
                    builder_index=spec.BuilderIndex(builder_index),
                ),
                proposer_index=spec.ValidatorIndex(0),
            )

        solution = _to_pending_withdrawal_solution(rec)
        verified = builder_pending_withdrawal_processing_validator(
            spec,
            pre,
            solution,
            0,
        )

        post = pre.copy()
        try:
            spec.process_withdrawals(post)
        except Exception:
            post = None

        claimed = {n: rec.get(n) for n in PENDING_WITHDRAWAL_DIMS}
        return pre, post, verified, claimed, []

    def _materialize_withdrawal_processing(
        self, sol: Any
    ) -> tuple[Any, Any | None, bool, dict, list]:
        spec = self.spec
        rec = sol if isinstance(sol, dict) else self._record(sol)

        limit = int(spec.MAX_WITHDRAWALS_PER_PAYLOAD) - 1
        max_per_sweep = int(spec.MAX_BUILDERS_PER_WITHDRAWALS_SWEEP)
        builder_queue_len = _pick_builder_queue_len(rec, limit)
        validator_queue_len = _pick_validator_queue_len(
            rec, int(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP)
        )
        eligible = rec["eligible_validator_pending_withdrawals_exist"] == "T"

        # Withdrawals drained by the builder pending and validator partial
        # sources before the builder sweep (get_builder_withdrawals +
        # get_pending_partial_withdrawals), which is the builder sweep's prior.
        processed_builder = min(builder_queue_len, limit)
        processed_partial = validator_queue_len if (eligible and processed_builder < limit) else 0
        sweep_prior = processed_builder + processed_partial

        bc, ni, positions = _pick_sweep(rec, limit, max_per_sweep, sweep_prior)

        pre = self._base.copy()
        state_epoch = int(spec.get_current_epoch(pre))

        set_parent_block(spec, pre, rec["state_latest_block_hash_match"])

        finalized_epoch = state_epoch + 1
        pre.finalized_checkpoint = spec.Checkpoint(
            epoch=spec.Epoch(finalized_epoch),
            root=spec.Root(b"\x01" * 32),
        )

        ref_bs = random.choice(self._ref_candidates)
        active_bs = random.choice(self._active_candidates)
        eligible_set = set(positions)
        active_indices = [i for i in range(bc) if i not in eligible_set][:builder_queue_len]
        active_set = set(active_indices)

        for i in range(bc):
            if i in eligible_set:
                wd = (
                    spec.Epoch(state_epoch)
                    if ref_bs.cmp_state_epoch_withdrawal_epoch == OpCmp.EQ
                    else spec.Epoch(max(0, state_epoch - 1))
                )
                params = _builder_params(spec, state_epoch, ref_bs, i, wd)
            elif i in active_set:
                params = _builder_params(spec, state_epoch, active_bs, i, spec.FAR_FUTURE_EPOCH)
            else:
                params = _builder_params(spec, state_epoch, ref_bs, i, spec.FAR_FUTURE_EPOCH)
            pre.builders.append(spec.Builder(**params))

        pre.next_withdrawal_builder_index = spec.BuilderIndex(ni)

        # Builder pending withdrawal queue entries.
        balance = int(spec.MIN_DEPOSIT_AMOUNT) + BIG
        amount_cmp = random.choice(["LT", "EQ", "GT"])
        if amount_cmp == "LT":
            amount = balance + 1
        elif amount_cmp == "EQ":
            amount = balance
        else:  # GT
            amount = balance - 1
        for idx in active_indices:
            pre.builder_pending_withdrawals.append(
                spec.BuilderPendingWithdrawal(
                    fee_recipient=spec.ExecutionAddress(BUILDER_ADDRESS),
                    amount=spec.Gwei(amount),
                    builder_index=spec.BuilderIndex(idx),
                )
            )

        # Validator pending partial withdrawal queue entries.
        if validator_queue_len > 0:
            template = random.choice(
                [
                    s
                    for s in self.all_validator_pending_withdrawal_solutions
                    if (s.withdrawable == Bool.T) == eligible
                ]
            )
            self._materialize_validator_partial(
                pre,
                state_epoch,
                finalized_epoch,
                template.validator,
                template,
                validator_queue_len,
            )

        # Validator sweep: control fully-withdrawable validators to realize
        # validators_eligible_for_sweep_exist / swept_validators_hit_limit.
        pre.next_withdrawal_validator_index = spec.ValidatorIndex(0)
        window_end = int(spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP)
        if rec["swept_validators_hit_limit"] == "T":
            # Fill the sweep window (skipping the pending-partial validator at 0)
            # so the validator sweep drains the remaining capacity to the limit.
            for idx in range(1, window_end):
                self._make_fully_withdrawable(pre, idx, state_epoch)
        elif rec["validators_eligible_for_sweep_exist"] == "T":
            # A single eligible validator outside the sweep window.
            self._make_fully_withdrawable(pre, window_end, state_epoch)

        solution = _to_withdrawal_processing_solution(rec)
        verified = withdrawal_processing_validator(
            spec,
            pre,
            solution,
            self.all_builder_solutions,
            self.all_builder_pending_withdrawal_solutions,
            self.all_validator_pending_withdrawal_solutions,
        )

        post = pre.copy()
        try:
            spec.process_withdrawals(post)
        except Exception:
            post = None

        claimed_dims: dict[str, Any] = {
            "state_latest_block_hash_match": rec["state_latest_block_hash_match"],
            "builder_pending_withdrawals_exist": rec["builder_pending_withdrawals_exist"],
            "builder_pending_withdrawals_hit_limit": rec["builder_pending_withdrawals_hit_limit"],
            "validator_pending_withdrawals_exist": rec["validator_pending_withdrawals_exist"],
            "eligible_validator_pending_withdrawals_exist": rec[
                "eligible_validator_pending_withdrawals_exist"
            ],
            "validator_pending_withdrawals_hit_limit": rec[
                "validator_pending_withdrawals_hit_limit"
            ],
            "validators_eligible_for_sweep_exist": rec["validators_eligible_for_sweep_exist"],
            "swept_validators_hit_limit": rec["swept_validators_hit_limit"],
        }
        claimed_dims.update({name: rec[name] for name in WITHDRAWAL_PROCESSING_DIMS if name in rec})
        claimed = {n: claimed_dims.get(n) for n in WITHDRAWAL_PROCESSING_DIMS}
        return pre, post, verified, claimed, []

    def describe(self, claimed: dict) -> str:
        if "cmp_builder_balance_amount" in claimed:
            return f"builder_pending_withdrawal_processing: {claimed}"
        return f"withdrawal_processing: {claimed}"
