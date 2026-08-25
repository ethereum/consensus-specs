"""Independent validation of process_withdrawal_request vectors.

Recovers every applicable coverage dimension from the decoded pre state and
WithdrawalRequest via the real spec predicates, recomputes the outcome, and runs
recomputes the outcome. Imports neither the materializer nor the model.
"""
from __future__ import annotations

from ..validation import check_dimensions, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")
_ACCEPT = {"FULL_EXIT_INITIATED", "PARTIAL_QUEUED"}

def _tri(x: bool) -> str:
    return "T" if x else "F"

def _credential(v: Any) -> str:
    prefix = bytes(v.withdrawal_credentials[:1])
    if prefix == bytes(spec.COMPOUNDING_WITHDRAWAL_PREFIX):
        return "CRED_COMPOUNDING"
    if prefix == bytes(spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX):
        return "CRED_ETH1"
    return "CRED_BLS"

def recover(pre: Any, request: Any) -> dict[str, Any]:
    current_epoch = spec.get_current_epoch(pre)
    pubkeys = [v.pubkey for v in pre.validators]
    found = request.validator_pubkey in pubkeys

    r: dict[str, Any] = {
        "is_full_exit_request": int(request.amount) == int(spec.FULL_EXIT_REQUEST_AMOUNT),
        "partial_queue_full": len(pre.pending_partial_withdrawals) == int(spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT),
        "validator_pubkey_found": found,
    }

    if found:
        idx = spec.ValidatorIndex(pubkeys.index(request.validator_pubkey))
        v = pre.validators[idx]
        pending = int(spec.get_pending_balance_to_withdraw(pre, idx))
        r["validator_credential"] = _credential(v)
        r["validator_has_execution_credential"] = bool(spec.has_execution_withdrawal_credential(v))
        r["validator_has_compounding_credential"] = bool(spec.has_compounding_withdrawal_credential(v))
        r["source_address_matches"] = _tri(v.withdrawal_credentials[12:] == request.source_address)
        r["validator_active"] = _tri(bool(spec.is_active_validator(v, current_epoch)))
        r["validator_exiting"] = _tri(v.exit_epoch != spec.FAR_FUTURE_EPOCH)
        r["validator_old_enough"] = _tri(
            int(current_epoch) >= int(v.activation_epoch) + int(spec.config.SHARD_COMMITTEE_PERIOD)
        )
        r["has_pending_partial_withdrawal"] = _tri(pending > 0)
        r["sufficient_effective_balance"] = _tri(int(v.effective_balance) >= int(spec.MIN_ACTIVATION_BALANCE))
        r["has_excess_balance"] = _tri(int(pre.balances[idx]) > int(spec.MIN_ACTIVATION_BALANCE) + pending)
    else:
        r["validator_credential"] = "CRED_NA"
        r["validator_has_execution_credential"] = False
        r["validator_has_compounding_credential"] = False
        for n in ("source_address_matches", "validator_active", "validator_exiting",
                  "validator_old_enough", "has_pending_partial_withdrawal",
                  "sufficient_effective_balance", "has_excess_balance"):
            r[n] = "NA"

    r["outcome"] = _derive(r)
    r["withdrawal_effected"] = r["outcome"] in _ACCEPT
    return r

def _derive(r: dict) -> str:
    if r["partial_queue_full"] and not r["is_full_exit_request"]:
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
        return "FULL_EXIT_NOOP_PENDING" if r["has_pending_partial_withdrawal"] == "T" else "FULL_EXIT_INITIATED"
    if not r["validator_has_compounding_credential"]:
        return "PARTIAL_NOOP_NOT_COMPOUNDING"
    if r["sufficient_effective_balance"] != "T":
        return "PARTIAL_NOOP_INSUFFICIENT_EFFECTIVE_BALANCE"
    if r["has_excess_balance"] != "T":
        return "PARTIAL_NOOP_NO_EXCESS_BALANCE"
    return "PARTIAL_QUEUED"

def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    request = decode(case_dir / "withdrawal_request.ssz_snappy", spec.WithdrawalRequest)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, request)
    return check_dimensions(claimed, actual)
