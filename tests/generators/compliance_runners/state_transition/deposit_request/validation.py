"""Independent validation of process_deposit_request vectors.

Since the handler has no predicates to re-derive beyond `start_index_unset`, the
substantive check is OUTPUT correctness: the appended PendingDeposit matches the
request (with slot = pre.slot), the queue grew by one, and the start index was
set iff it was unset. Plus the post-state oracle. Imports neither the
materializer nor the model.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import snappy
from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")


@dataclass
class Check:
    dimension: str
    claimed: Any
    actual: Any
    status: str


def _decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


def recover(pre: Any, request: Any) -> dict[str, Any]:
    return {
        "amount_nonzero": int(request.amount) > 0,
        "pubkey_is_existing_validator": request.pubkey in [v.pubkey for v in pre.validators],
        "outcome": "APPENDED",
    }


def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = _decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    post = _decode(case_dir / "post.ssz_snappy", spec.BeaconState)
    request = _decode(case_dir / "deposit_request.ssz_snappy", spec.DepositRequest)
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


def main() -> int:
    default = Path(__file__).parent / "reftests"
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    case_dirs = sorted(root.glob("**/operations/deposit_request/**/case_*"))
    if not case_dirs:
        print(f"No cases found under {root}")
        return 1

    total_mm = total_err = 0
    for case_dir in case_dirs:
        checks, errors = validate_case(case_dir)
        mism = [c for c in checks if c.status == "mismatch"]
        total_mm += len(mism)
        total_err += len(errors)
        status = "OK" if not mism and not errors else "FAIL"
        outcome = next((c.claimed for c in checks if c.dimension == "outcome"), "?")
        print(f"{case_dir.name}: {status}  [{outcome}]")
        for c in mism:
            print(f"    dim {c.dimension}: claimed={c.claimed!r} actual={c.actual!r}")
        for e in errors:
            print(f"    output/oracle: {e}")

    print()
    if total_mm or total_err:
        print(f"FAILED: {total_mm} dimension mismatch(es), {total_err} output/oracle error(s)")
        return 1
    print(f"PASSED: {len(case_dirs)} cases, all dimensions and output/oracle checks consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
