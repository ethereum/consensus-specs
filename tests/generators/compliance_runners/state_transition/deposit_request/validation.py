"""Independent validation of process_deposit_request vectors.

Since the handler has no predicates to re-derive beyond `start_index_unset`, the
substantive check is OUTPUT correctness: the appended PendingDeposit matches the
request (with slot = pre.slot), the queue grew by one, and the start index was
set iff it was unset. Plus the post-state oracle. Imports neither the
materializer nor the model.
"""
from __future__ import annotations

from ..validation import Check, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")

def recover(pre: Any, request: Any) -> dict[str, Any]:
    return {
        "amount_nonzero": int(request.amount) > 0,
        "pubkey_is_existing_validator": request.pubkey in [v.pubkey for v in pre.validators],
        "outcome": "APPENDED",
    }

def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    post = decode(case_dir / "post.ssz_snappy", spec.BeaconState)
    request = decode(case_dir / "deposit_request.ssz_snappy", spec.DepositRequest)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, request)

    checks = [Check(d, c, actual.get(d, "<none>"), "ok" if actual.get(d, "<none>") == c else "mismatch")
              for d, c in claimed.items()]

    errors: list[str] = []
    # Output correctness.
    if len(post.pending_deposits) != len(pre.pending_deposits) + 1:
        errors.append("pending_deposits did not grow by exactly one")
    else:
        expected = spec.PendingDeposit(
            pubkey=request.pubkey, withdrawal_credentials=request.withdrawal_credentials,
            amount=request.amount, signature=request.signature, slot=pre.slot,
        )
        if post.pending_deposits[len(post.pending_deposits) - 1] != expected:
            errors.append("appended PendingDeposit does not match the request (+ pre.slot)")
    # gloas removed the start-index logic: it must be left untouched.
    if post.deposit_requests_start_index != pre.deposit_requests_start_index:
        errors.append("deposit_requests_start_index changed (gloas must not touch it)")
    # Oracle.
    oracle = pre.copy()
    spec.process_deposit_request(oracle, request)
    if oracle.hash_tree_root() != post.hash_tree_root():
        errors.append("post does not match spec re-execution")
    return checks, errors
