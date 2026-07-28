"""Independent validation of process_builder_deposit_request vectors.

Recovers every applicable coverage dimension from the decoded pre state and
BuilderDepositRequest via the real spec predicates, recomputes the outcome, and
runs the handler as an oracle (post is always present; it must equal spec
re-execution). Imports neither the materializer nor the model.
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
_ACCEPT = {"ADDED_NEW_BUILDER", "TOPPED_UP", "TOPPED_UP_AFTER_RESET"}


@dataclass
class Check:
    dimension: str
    claimed: Any
    actual: Any
    status: str


def _decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


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


def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = _decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    post = _decode(case_dir / "post.ssz_snappy", spec.BeaconState)
    request = _decode(case_dir / "builder_deposit_request.ssz_snappy", spec.BuilderDepositRequest)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, request)

    checks = [Check(d, c, actual.get(d, "<none>"), "ok" if actual.get(d, "<none>") == c else "mismatch")
              for d, c in claimed.items()]

    # Oracle: post must equal spec re-execution. (Note: `builder_credited` means
    # the credit branch was reached, not that state changed — a zero-amount
    # top-up credits nothing — so it is not a state-change predicate.)
    errors: list[str] = []
    oracle = pre.copy()
    spec.process_builder_deposit_request(oracle, request)
    if oracle.hash_tree_root() != post.hash_tree_root():
        errors.append("post does not match spec re-execution")
    return checks, errors


def main() -> int:
    default = Path(__file__).parent / "reftests"
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    case_dirs = sorted(root.glob("**/operations/builder_deposit_request/**/case_*"))
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
            print(f"    oracle: {e}")

    print()
    if total_mm or total_err:
        print(f"FAILED: {total_mm} dimension mismatch(es), {total_err} oracle error(s)")
        return 1
    print(f"PASSED: {len(case_dirs)} cases, all dimensions and oracle checks consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
