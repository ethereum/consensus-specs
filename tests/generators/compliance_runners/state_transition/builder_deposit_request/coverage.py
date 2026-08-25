"""Coverage profiles for process_builder_deposit_request.

Handler-specific instantiation of the shared ``..aspect_coverage`` engine.
Reuses the shared aspects builder_membership and signed_message (the SAME
signature aspect execution_payload_bid binds).

Run:
    uv run python -m ...builder_deposit_request.coverage
    uv run python -m ...builder_deposit_request.coverage standard --materialize
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import cover, dedup, enumerate_signatures
from .materializer import BuilderDepositRequestMaterializer, _DIMS

INPUT_ASPECTS = {
    "withdrawal_credential": ["wc_is_builder_prefix"],
    "builder_membership": ["builder_pubkey_found"],
    "signed_message": ["builder_signature_valid"],
    "deposit_amount": ["amount_nonzero"],
    "builder_reset": ["builder_withdrawable_epoch_set", "builder_balance_zero"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
ACCEPT = {"ADDED_NEW_BUILDER", "TOPPED_UP", "TOPPED_UP_AFTER_RESET"}
MODEL = Path(__file__).parent / "models" / "handler_builder_deposit_request.mzn"


def _nfaults(r: dict) -> int:
    if not r["wc_is_builder_prefix"]:
        return 1
    if not r["builder_pubkey_found"] and r["builder_signature_valid"] != "T":
        return 1
    return 0


PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "normal": (INPUT_ASPECTS, 2, "normal"),
    "exceptional": (OUTCOME_ASPECT, 1, "exceptional"),
}


def build_profile(recs, name):
    if name == "all":
        return len(recs), recs
    if name == "standard":
        _, normal = cover(recs, *PROFILES["normal"], accept=ACCEPT)
        _, exc = cover(recs, *PROFILES["exceptional"], accept=ACCEPT)
        return -1, dedup(normal + exc, ALL_ASPECTS)
    aspects, t, filt = PROFILES[name]
    return cover(recs, aspects, t, filt, accept=ACCEPT)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    from eth_consensus_specs.gloas import minimal as spec
    _, chosen = build_profile(_recs(), name)
    reps = [SimpleNamespace(**r) for r in chosen]
    out = output_dir or (Path(__file__).parent / "reftests")
    return BuilderDepositRequestMaterializer(spec, MODEL).materialize_reps(out, reps)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    materialize = "--materialize" in sys.argv
    recs = _recs()
    print(f"distinct aspect-state signatures: {len(recs)}\n")

    if not args:
        print(f"{'profile':14} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "normal", "exceptional"):
            n_obl, chosen = build_profile(recs, name)
            print(f"{name:14} {n_obl:>12} {len(chosen):>7}")
        _, std = build_profile(recs, "standard")
        print(f"{'standard':14} {'(union)':>12} {len(std):>7}")
        return 0

    n_obl, chosen = build_profile(recs, args[0])
    print(f"profile '{args[0]}': {len(chosen)} cases"
          + (f" covering {n_obl} obligations" if n_obl >= 0 else ""))
    if materialize:
        materialize_profile(args[0])
        print("Validate with: python -m ...builder_deposit_request.validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
