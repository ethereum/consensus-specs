"""Independent validation for Gloas proposer-slashing compliance vectors."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import snappy
from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec
from eth_consensus_specs.utils import bls

_YAML = YAML(typ="safe")


@dataclass
class Check:
    dimension: str
    claimed: Any
    actual: Any
    status: str


def _decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


def recover(pre: Any, slashing: Any) -> dict[str, Any]:
    h1, h2 = slashing.signed_header_1, slashing.signed_header_2
    m1, m2 = h1.message, h2.message
    current, proposer = spec.get_current_epoch(pre), pre.validators[m1.proposer_index]

    def valid(signed: Any) -> bool:
        domain = spec.get_domain(
            pre,
            spec.DOMAIN_BEACON_PROPOSER,
            spec.compute_epoch_at_slot(signed.message.slot),
        )
        return bool(
            bls.Verify(
                pre.validators[signed.message.proposer_index].pubkey,
                spec.compute_signing_root(signed.message, domain),
                signed.signature,
            )
        )

    epoch = spec.compute_epoch_at_slot(m1.slot)
    if epoch == current:
        window, payment_index = (
            "CURRENT",
            int(spec.SLOTS_PER_EPOCH) + int(m1.slot) % int(spec.SLOTS_PER_EPOCH),
        )
    elif epoch == spec.get_previous_epoch(pre):
        window, payment_index = "PREVIOUS", int(m1.slot) % int(spec.SLOTS_PER_EPOCH)
    else:
        window, payment_index = "OLD", None
    payment_matches = (
        "NA"
        if payment_index is None
        else (
            "T"
            if pre.builder_pending_payments[payment_index].proposer_index == m1.proposer_index
            else "F"
        )
    )
    r = {
        "slots_match": m1.slot == m2.slot,
        "proposers_match": m1.proposer_index == m2.proposer_index,
        "headers_different": m1 != m2,
        "signature_1_valid": "T" if valid(h1) else "F",
        "signature_2_valid": "T" if valid(h2) else "F",
        "proposer_slashed": bool(proposer.slashed),
        "proposer_activated": proposer.activation_epoch <= current,
        "proposer_withdrawable": proposer.withdrawable_epoch <= current,
        "proposer_exited": proposer.exit_epoch <= current,
        "payment_window": window,
        "payment_proposer_matches": payment_matches,
    }
    slashable = spec.is_slashable_validator(proposer, current)
    if not r["slots_match"]:
        outcome = "REJECT_SLOT_MISMATCH"
    elif not r["proposers_match"]:
        outcome = "REJECT_PROPOSER_MISMATCH"
    elif not r["headers_different"]:
        outcome = "REJECT_HEADERS_EQUAL"
    elif not slashable:
        if r["proposer_slashed"]:
            outcome = "REJECT_NOT_SLASHABLE_SLASHED"
        elif not r["proposer_activated"]:
            outcome = "REJECT_NOT_ACTIVATED"
        else:
            outcome = "REJECT_NOT_SLASHABLE_WITHDRAWABLE"
    elif r["signature_1_valid"] != "T":
        outcome = "REJECT_SIGNATURE_1"
    elif r["signature_2_valid"] != "T":
        outcome = "REJECT_SIGNATURE_2"
    elif window == "OLD":
        outcome = "ACCEPT_OLD"
    else:
        outcome = f"ACCEPT_{window}_PAYMENT_{'CLEARED' if payment_matches == 'T' else 'RETAINED'}"
    r.update(
        outcome=outcome,
        pending_payment_cleared=outcome.endswith("CLEARED"),
        state_effected=outcome.startswith("ACCEPT_"),
    )
    return r


def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = _decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    operation = _decode(case_dir / "proposer_slashing.ssz_snappy", spec.ProposerSlashing)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, operation)
    checks = [
        Check(k, v, actual.get(k), "ok" if actual.get(k) == v else "mismatch")
        for k, v in claimed.items()
    ]
    post_path, errors = case_dir / "post.ssz_snappy", []
    if not actual["state_effected"]:
        if post_path.exists():
            errors.append("rejected operation must not have a post state")
        return checks, errors
    if not post_path.exists():
        return checks, ["accepted operation is missing post state"]
    post, oracle = _decode(post_path, spec.BeaconState), pre.copy()
    spec.process_proposer_slashing(oracle, operation)
    if oracle.hash_tree_root() != post.hash_tree_root():
        errors.append("post state does not match spec re-execution")
    if not post.validators[operation.signed_header_1.message.proposer_index].slashed:
        errors.append("proposer was not slashed")
    return checks, errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "reftests"
    cases = sorted(root.glob("**/operations/proposer_slashing/**/case_*"))
    if not cases:
        print(f"No cases found under {root}")
        return 1
    bad = 0
    for case in cases:
        checks, errors = validate_case(case)
        mismatches = [c for c in checks if c.status == "mismatch"]
        bad += len(mismatches) + len(errors)
        print(f"{case.name}: {'OK' if not mismatches and not errors else 'FAIL'}")
        for check in mismatches:
            print(f"    {check.dimension}: claimed={check.claimed!r} actual={check.actual!r}")
        for error in errors:
            print(f"    {error}")
    print(f"{'PASSED' if not bad else 'FAILED'}: {len(cases)} cases")
    return int(bool(bad))


if __name__ == "__main__":
    raise SystemExit(main())
