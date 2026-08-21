"""Independent validation of process_builder_exit_request vectors.

Recovers every applicable coverage dimension from the decoded pre state and
BuilderExitRequest via the real spec predicates, compares to the serialized
solution, recomputes the outcome, and runs the handler as an oracle (post is
always present; it must equal spec re-execution). Imports neither the
materializer nor the model.
"""
from __future__ import annotations

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


def _tri(x: bool) -> str:
    return "T" if x else "F"


def _cmp(a: int, b: int) -> str:
    return "LT" if a < b else ("EQ" if a == b else "GT")


def recover(pre: Any, request: Any) -> dict[str, Any]:
    pubkeys = [b.pubkey for b in pre.builders]
    found = request.pubkey in pubkeys
    r: dict[str, Any] = {"builder_pubkey_found": found}

    if found:
        idx = spec.BuilderIndex(pubkeys.index(request.pubkey))
        b = pre.builders[idx]
        finalized = int(pre.finalized_checkpoint.epoch)
        pending = int(spec.get_pending_balance_to_withdraw_for_builder(pre, idx))
        r["builder_deposit_to_finalized_epoch"] = _cmp(int(b.deposit_epoch), finalized)
        r["builder_withdrawable_epoch_set"] = _tri(b.withdrawable_epoch != spec.FAR_FUTURE_EPOCH)
        r["builder_has_pending_withdrawal"] = _tri(
            any(w.builder_index == idx and int(w.amount) > 0 for w in pre.builder_pending_withdrawals)
        )
        r["builder_has_pending_payment"] = _tri(
            any(p.withdrawal.builder_index == idx and int(p.withdrawal.amount) > 0
                for p in pre.builder_pending_payments)
        )
        r["source_address_matches"] = _tri(b.execution_address == request.source_address)
        r["builder_active"] = bool(spec.is_active_builder(pre, idx))
        r["builder_has_pending_balance"] = pending != 0
    else:
        for n in ("builder_deposit_to_finalized_epoch", "builder_withdrawable_epoch_set",
                  "builder_has_pending_withdrawal", "builder_has_pending_payment",
                  "source_address_matches"):
            r[n] = "NA"
        r["builder_active"] = False
        r["builder_has_pending_balance"] = False

    if not r["builder_pubkey_found"]:
        outcome = "IGNORED_PUBKEY_NOT_FOUND"
    elif not r["builder_active"]:
        outcome = "IGNORED_NOT_ACTIVE"
    elif r["source_address_matches"] != "T":
        outcome = "IGNORED_ADDRESS_MISMATCH"
    elif r["builder_has_pending_balance"]:
        outcome = "IGNORED_PENDING_NONZERO"
    else:
        outcome = "EXIT_INITIATED"
    r["outcome"] = outcome
    r["exit_initiated"] = outcome == "EXIT_INITIATED"
    return r


def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = _decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    post = _decode(case_dir / "post.ssz_snappy", spec.BeaconState)
    request = _decode(case_dir / "builder_exit_request.ssz_snappy", spec.BuilderExitRequest)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, request)

    checks = [Check(d, c, actual.get(d, "<none>"), "ok" if actual.get(d, "<none>") == c else "mismatch")
              for d, c in claimed.items()]

    errors: list[str] = []
    oracle = pre.copy()
    spec.process_builder_exit_request(oracle, request)
    if oracle.hash_tree_root() != post.hash_tree_root():
        errors.append("post does not match spec re-execution")
    changed = pre.hash_tree_root() != post.hash_tree_root()
    if changed != bool(claimed.get("exit_initiated")):
        errors.append(f"state_changed={changed} but exit_initiated={claimed.get('exit_initiated')}")
    return checks, errors
