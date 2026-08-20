"""Independent validation of process_execution_payload_bid vectors (bid_processing model).

Recovers every applicable coverage dimension directly from the decoded pre state
and SignedExecutionPayloadBid via the real spec predicates, compares to the
serialized solution in dimensions.yaml, recomputes the outcome, and runs the
handler as an oracle (post present + matching iff accepted). Imports neither the
materializer nor the model.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.bid_processing.validation [REFTESTS_DIR]
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
    status: str  # ok | mismatch


def _decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


def _cmp(a: int, b: int) -> str:
    return "LT" if a < b else ("EQ" if a == b else "GT")


def _tri(x: bool) -> str:
    return "T" if x else "F"


def recover(pre: Any, signed: Any) -> dict[str, Any]:
    bid = signed.message
    idx = bid.builder_index
    n_builders = len(pre.builders)

    if idx == spec.BUILDER_INDEX_SELF_BUILD:
        builder_type = "SELF"
    elif int(idx) < n_builders:
        builder_type = "EXTERNAL"
    else:
        builder_type = "NON_EXISTING"

    is_self = builder_type == "SELF"
    current_epoch = spec.get_current_epoch(pre)

    r: dict[str, Any] = {
        "builder_type": builder_type,
        "cmp_bid_value_zero": _cmp(int(bid.value), 0),
        "state_slot_past_genesis": int(pre.slot) > spec.GENESIS_SLOT,
        "parent_block_hash_match": _tri(bid.parent_block_hash == pre.latest_block_hash),
        "prev_randao_match": _tri(bid.prev_randao == spec.get_randao_mix(pre, current_epoch)),
    }

    max_blobs = spec.get_blob_parameters(current_epoch).max_blobs_per_block
    r["cmp_len_kzg_commitments_max_blobs"] = _cmp(len(bid.blob_kzg_commitments), max_blobs)
    r["cmp_state_slot_bid_slot"] = _cmp(int(pre.slot), int(bid.slot))
    r["amount_positive"] = int(bid.value) > 0

    # parent_block_root: only defined past genesis
    if int(pre.slot) > spec.GENESIS_SLOT:
        expected = spec.get_block_root_at_slot(pre, spec.Slot(int(pre.slot) - 1))
        r["parent_block_root_match"] = _tri(bid.parent_block_root == expected)
    else:
        r["parent_block_root_match"] = "NA"

    # Signature classification
    if signed.signature == spec.bls.G2_POINT_AT_INFINITY:
        r["bid_signature"] = "INF"
    elif is_self:
        r["bid_signature"] = "INVALID"
    elif spec.verify_execution_payload_bid_signature(pre, signed):
        r["bid_signature"] = "VALID"
    else:
        r["bid_signature"] = "INVALID"

    # EXTERNAL-only builder sub-dimensions
    if builder_type == "EXTERNAL":
        b = pre.builders[idx]
        finalized = int(pre.finalized_checkpoint.epoch)
        pending_amount = int(spec.get_pending_balance_to_withdraw_for_builder(pre, idx))
        min_balance = int(spec.MIN_DEPOSIT_AMOUNT) + pending_amount

        r["cmp_state_epoch_deposit_epoch"] = _cmp(int(current_epoch), int(b.deposit_epoch))
        r["cmp_state_epoch_withdrawal_epoch"] = _cmp(int(current_epoch), int(b.withdrawable_epoch))
        r["cmp_finalized_epoch_deposit_epoch"] = _cmp(finalized, int(b.deposit_epoch))
        r["withdrawable_epoch_set"] = _tri(b.withdrawable_epoch != spec.FAR_FUTURE_EPOCH)
        r["payload_builder_version"] = _tri(b.version == spec.PAYLOAD_BUILDER_VERSION)
        r["cmp_balance_zero"] = _cmp(int(b.balance), 0)
        r["cmp_balance_min_deposit"] = _cmp(int(b.balance), int(spec.MIN_DEPOSIT_AMOUNT))
        r["has_pending_payments"] = _tri(
            any(p.withdrawal.builder_index == idx and int(p.withdrawal.amount) > 0
                for p in pre.builder_pending_payments)
        )
        r["has_pending_withdrawals"] = _tri(
            any(w.builder_index == idx and int(w.amount) > 0 for w in pre.builder_pending_withdrawals)
        )
        r["cmp_builder_balance_to_bid_value_plus_min_balance"] = _cmp(
            int(b.balance), int(bid.value) + min_balance
        )
    else:
        for name in (
            "cmp_state_epoch_deposit_epoch", "cmp_state_epoch_withdrawal_epoch",
            "cmp_finalized_epoch_deposit_epoch", "withdrawable_epoch_set",
            "payload_builder_version", "cmp_balance_zero", "cmp_balance_min_deposit",
            "has_pending_payments", "has_pending_withdrawals",
        ):
            r[name] = "NA"
        # For SELF/NON_EXISTING: min_balance = 0, so cmp(0, bid.value)
        r["cmp_builder_balance_to_bid_value_plus_min_balance"] = _cmp(0, int(bid.value))

    # Normalize NA variants: the mzn model uses NA_CMP/NA_BOOL while recovery uses NA.
    _NA_MAP = {"NA_CMP": "NA", "NA_BOOL": "NA"}
    for k, v in r.items():
        if v in _NA_MAP:
            r[k] = _NA_MAP[v]

    r["outcome"] = _derive_outcome(r)
    return r


def _derive_outcome(r: dict[str, Any]) -> str:
    def common() -> str:
        if r["cmp_len_kzg_commitments_max_blobs"] not in ("LT", "EQ"):
            return "REJECT_KZG_OVER_LIMIT"
        if r["cmp_state_slot_bid_slot"] != "EQ":
            return "REJECT_WRONG_SLOT"
        if not r["state_slot_past_genesis"]:
            return "REJECT_NOT_PAST_GENESIS"
        if r["parent_block_hash_match"] != "T":
            return "REJECT_PARENT_HASH"
        if r["parent_block_root_match"] != "T":
            return "REJECT_PARENT_ROOT"
        if r["prev_randao_match"] != "T":
            return "REJECT_PREV_RANDAO"
        return "ACCEPT"

    if r["builder_type"] == "SELF":
        if r["cmp_bid_value_zero"] == "GT":
            return "REJECT_SELF_BUILD_NONZERO_AMOUNT"
        if r["bid_signature"] != "INF":
            return "REJECT_SELF_BUILD_BAD_SIGNATURE"
        return common()
    if r["builder_type"] == "NON_EXISTING":
        return "REJECT_BUILDER_NOT_FOUND"
    # EXTERNAL
    if r["cmp_finalized_epoch_deposit_epoch"] != "GT" or r["withdrawable_epoch_set"] != "F":
        return "REJECT_BUILDER_INACTIVE"
    if r["payload_builder_version"] != "T":
        return "REJECT_WRONG_VERSION"
    if r["cmp_builder_balance_to_bid_value_plus_min_balance"] == "LT":
        return "REJECT_UNDERFUNDED"
    if r["bid_signature"] != "VALID":
        return "REJECT_BAD_SIGNATURE"
    return common()


def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = _decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    signed = _decode(case_dir / "execution_payload_bid.ssz_snappy", spec.SignedExecutionPayloadBid)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    # Normalize NA variants: mzn uses NA_CMP/NA_BOOL, recovery uses NA.
    _NA_MAP = {"NA_CMP": "NA", "NA_BOOL": "NA"}
    claimed = {k: _NA_MAP.get(v, v) for k, v in claimed.items()}
    actual = recover(pre, signed)

    checks = [
        Check(dim, claim, actual.get(dim, "<none>"),
              "ok" if actual.get(dim, "<none>") == claim else "mismatch")
        for dim, claim in claimed.items()
    ]

    # Oracle: run the handler; accepted iff it does not raise.
    errors: list[str] = []
    post_path = case_dir / "post.ssz_snappy"
    oracle = pre.copy()
    accepted = True
    try:
        spec.process_execution_payload_bid(oracle, signed)
    except (AssertionError, IndexError):
        accepted = False

    if accepted and not post_path.exists():
        errors.append("handler accepted but no post recorded")
    if not accepted and post_path.exists():
        errors.append("handler rejected but post present")
    if accepted and post_path.exists():
        post = _decode(post_path, spec.BeaconState)
        if oracle.hash_tree_root() != post.hash_tree_root():
            errors.append("post does not match spec re-execution")
    if accepted != (claimed.get("outcome") == "ACCEPT"):
        errors.append(f"accepted={accepted} but outcome={claimed.get('outcome')}")
    return checks, errors


def main() -> int:
    default = Path(__file__).parent / "reftests"
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    case_dirs = sorted(root.glob("**/operations/execution_payload_bid/**/case_*"))
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
