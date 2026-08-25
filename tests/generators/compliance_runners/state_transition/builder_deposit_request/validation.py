"""Independent validation of process_builder_deposit_request vectors.

Recovers every applicable coverage dimension from the decoded pre state and
BuilderDepositRequest via the real spec predicates, recomputes the outcome, and
Imports neither the materializer nor the model.
"""
from __future__ import annotations

from ..validation import Check, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")
_ACCEPT = {"ADDED_NEW_BUILDER", "TOPPED_UP", "TOPPED_UP_AFTER_RESET"}

def _tri(x: bool) -> str:
    return "T" if x else "F"

def recover(pre: Any, request: Any) -> dict[str, Any]:
    pubkeys = [b.pubkey for b in pre.builders]
    found = request.pubkey in pubkeys
    r: dict[str, Any] = {
        "wc_is_builder_prefix": bool(spec.is_builder_withdrawal_credential(request.withdrawal_credentials)),
        "builder_pubkey_found": found,
        "builder_signature_valid": _tri(bool(spec.is_valid_builder_deposit_signature(request))),
        "amount_nonzero": int(request.amount) > 0,
    }

    if found:
        b = pre.builders[pubkeys.index(request.pubkey)]
        wset = b.withdrawable_epoch != spec.FAR_FUTURE_EPOCH
        bzero = int(b.balance) == 0
        r["builder_withdrawable_epoch_set"] = _tri(wset)
        r["builder_balance_zero"] = _tri(bzero)
        r["reset_applies"] = bool(wset and bzero)
    else:
        r["builder_withdrawable_epoch_set"] = "NA"
        r["builder_balance_zero"] = "NA"
        r["reset_applies"] = False

    if not r["wc_is_builder_prefix"]:
        outcome = "IGNORED_BAD_PREFIX"
    elif not found:
        outcome = "ADDED_NEW_BUILDER" if r["builder_signature_valid"] == "T" else "IGNORED_BAD_SIGNATURE"
    else:
        outcome = "TOPPED_UP_AFTER_RESET" if r["reset_applies"] else "TOPPED_UP"
    r["outcome"] = outcome
    r["builder_credited"] = outcome in _ACCEPT
    return r

def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    request = decode(case_dir / "builder_deposit_request.ssz_snappy", spec.BuilderDepositRequest)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, request)

    checks = [Check(d, c, actual.get(d, "<none>"), "ok" if actual.get(d, "<none>") == c else "mismatch")
              for d, c in claimed.items()]

    return checks
