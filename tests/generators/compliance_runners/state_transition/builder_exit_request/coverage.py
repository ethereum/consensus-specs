"""Coverage profiles for process_builder_exit_request.

Handler-specific instantiation of the shared ``..aspect_coverage`` engine —
the SAME engine execution_payload_bid uses. Two of the aspects
(builder_lifecycle, builder_pending_balance) are the shared aspect files bound
by both handlers.

Run:
    uv run python -m ...builder_exit_request.coverage                 # summary
    uv run python -m ...builder_exit_request.coverage standard --materialize
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import cover, dedup, enumerate_signatures
from .materializer import BuilderExitRequestMaterializer, _DIMS

INPUT_ASPECTS = {
    "builder_membership": ["builder_pubkey_found"],
    "builder_lifecycle": ["builder_deposit_to_finalized_epoch", "builder_withdrawable_epoch_set"],
    "builder_pending_balance": ["builder_has_pending_withdrawal", "builder_has_pending_payment"],
    "source_authorization": ["source_address_matches"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
ACCEPT = "EXIT_INITIATED"
MODEL = Path(__file__).parent / "models" / "handler_builder_exit_request.mzn"


def _nfaults(r: dict) -> int:
    if not r["builder_pubkey_found"]:
        return 1
    f = 0
    f += not r["builder_active"]
    f += r["source_address_matches"] != "T"
    f += r["builder_has_pending_balance"]
    return int(f)


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
    return BuilderExitRequestMaterializer(spec, MODEL).materialize_reps(out, reps)
