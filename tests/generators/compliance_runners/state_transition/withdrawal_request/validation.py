"""Independent validation of process_withdrawal_request vectors.

Recovers every applicable coverage dimension from the decoded pre state and
WithdrawalRequest via the real spec predicates, recomputes the outcome, and runs
recomputes the outcome. Imports neither the materializer nor the model.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspects.base import _to_bool, _to_cmp
from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_capacity import (
    queue_capacity_profile,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_churn import (
    queue_churn_variant,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_profile,
)
from tests.generators.compliance_runners.state_transition.provider import check_dimensions, decode

if TYPE_CHECKING:
    from pathlib import Path

    from tests.generators.compliance_runners.state_transition.provider import Check

_YAML = YAML(typ="safe")
_ACCEPT = {"FULL_EXIT_INITIATED", "PARTIAL_QUEUED"}


def recover(pre: Any, request: Any) -> dict[str, Any]:
    current_epoch = spec.get_current_epoch(pre)
    pubkeys = [v.pubkey for v in pre.validators]
    found = request.validator_pubkey in pubkeys

    r: dict[str, Any] = {
        "is_full_exit_request": int(request.amount) == int(spec.FULL_EXIT_REQUEST_AMOUNT),
        "partial_queue_capacity": queue_capacity_profile(
            len(pre.pending_partial_withdrawals), int(spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT)
        ),
        "validator_pubkey_found": found,
        "churn_variant": "QUEUE_CHURN_NA",
    }

    if found:
        idx = spec.ValidatorIndex(pubkeys.index(request.validator_pubkey))
        v = pre.validators[idx]
        pending = int(spec.get_pending_balance_to_withdraw(pre, idx))
        r["validator_credential"] = withdrawal_credentials_profile(spec, v.withdrawal_credentials)
        r["validator_has_execution_credential"] = bool(spec.has_execution_withdrawal_credential(v))
        r["validator_has_compounding_credential"] = bool(
            spec.has_compounding_withdrawal_credential(v)
        )
        r["source_address_matches"] = _to_bool(
            v.withdrawal_credentials[12:] == request.source_address
        ).name
        r["validator_active"] = _to_bool(bool(spec.is_active_validator(v, current_epoch))).name
        r["validator_exiting"] = _to_bool(v.exit_epoch != spec.FAR_FUTURE_EPOCH).name
        r["validator_old_enough"] = _to_bool(
            int(current_epoch) >= int(v.activation_epoch) + int(spec.config.SHARD_COMMITTEE_PERIOD)
        ).name
        r["has_pending_partial_withdrawal"] = _to_bool(pending > 0).name
        r["effective_balance_to_min_activation"] = _to_cmp(
            int(v.effective_balance), int(spec.MIN_ACTIVATION_BALANCE)
        ).name
        r["balance_to_required"] = _to_cmp(
            int(pre.balances[idx]), int(spec.MIN_ACTIVATION_BALANCE) + pending
        ).name
    else:
        r["validator_credential"] = "CRED_NA"
        r["validator_has_execution_credential"] = False
        r["validator_has_compounding_credential"] = False
        for n in (
            "source_address_matches",
            "validator_active",
            "validator_exiting",
            "validator_old_enough",
            "has_pending_partial_withdrawal",
            "effective_balance_to_min_activation",
            "balance_to_required",
        ):
            r[n] = "NA"

    r["outcome"] = _derive(r)
    if r["outcome"] == "FULL_EXIT_INITIATED":
        r["churn_variant"] = queue_churn_variant(
            spec.compute_activation_exit_epoch(current_epoch),
            pre.earliest_exit_epoch,
            v.effective_balance,
            pre.exit_balance_to_consume,
        )
    r["withdrawal_effected"] = r["outcome"] in _ACCEPT
    return r


def _derive(r: dict) -> str:
    if r["partial_queue_capacity"] == "FULL" and not r["is_full_exit_request"]:
        return "REJECTED_QUEUE_FULL"
    if not r["validator_pubkey_found"]:
        return "REJECTED_NOT_FOUND"
    if not (r["validator_has_execution_credential"] and r["source_address_matches"] == "T"):
        return "REJECTED_CREDENTIALS"
    if r["validator_active"] != "T":
        return "REJECTED_INACTIVE"
    if r["validator_exiting"] != "F":
        return "REJECTED_EXITING"
    if r["validator_old_enough"] != "T":
        return "REJECTED_TOO_YOUNG"
    if r["is_full_exit_request"]:
        return (
            "FULL_EXIT_NOOP_PENDING"
            if r["has_pending_partial_withdrawal"] == "T"
            else "FULL_EXIT_INITIATED"
        )
    if not r["validator_has_compounding_credential"]:
        return "PARTIAL_NOOP_NOT_COMPOUNDING"
    if r["effective_balance_to_min_activation"] not in {"EQ", "GT"}:
        return "PARTIAL_NOOP_INSUFFICIENT_EFFECTIVE_BALANCE"
    if r["balance_to_required"] != "GT":
        return "PARTIAL_NOOP_NO_EXCESS_BALANCE"
    return "PARTIAL_QUEUED"


def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    request = decode(case_dir / "withdrawal_request.ssz_snappy", spec.WithdrawalRequest)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, request)
    return check_dimensions(claimed, actual)
