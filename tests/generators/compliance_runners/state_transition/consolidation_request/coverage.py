"""Coverage profiles for process_consolidation_request.

Handler-specific instantiation of the shared ``..aspect_coverage`` engine.
Reuses the validator family for the SOURCE validator + source_authorization, and
a compact target_validator aspect for the target.

Run:
    uv run python -m ...consolidation_request.coverage
    uv run python -m ...consolidation_request.coverage standard --materialize
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import cover, dedup, enumerate_signatures
from .materializer import ConsolidationRequestMaterializer, _DIMS

# Fine-grained input aspects. These remain available through the detailed
# profile; the default profiles use the composite validator_state factor.
FINE_INPUT_ASPECTS = {
    "consolidation_pair": ["same_source_target"],
    "pending_consolidations_capacity": ["pending_consolidations_full"],
    "consolidation_churn": ["sufficient_consolidation_churn"],
    "validator_membership": ["validator_pubkey_found"],
    "validator_credential": ["validator_credential"],
    "source_authorization": ["source_address_matches"],
    "validator_lifecycle": ["validator_active", "validator_exiting", "validator_old_enough"],
    "validator_pending_withdrawal": ["has_pending_partial_withdrawal"],
    "target_validator": ["target_found", "target_credential", "target_active", "target_exiting"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
INPUT_ASPECTS = {
    "consolidation_pair": ["same_source_target"],
    "pending_consolidations_capacity": ["pending_consolidations_full"],
    "consolidation_churn": ["sufficient_consolidation_churn"],
    "validator_state": [
        "validator_pubkey_found",
        "validator_credential",
        "source_address_matches",
        "validator_active",
        "validator_exiting",
        "validator_old_enough",
        "has_pending_partial_withdrawal",
        "target_found",
        "target_credential",
        "target_active",
        "target_exiting",
    ],
}
FINE_ALL_ASPECTS = {**FINE_INPUT_ASPECTS, **OUTCOME_ASPECT}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
ACCEPT = {"SWITCHED_TO_COMPOUNDING", "CONSOLIDATED"}
MODEL = Path(__file__).parent / "models" / "handler_consolidation_request.mzn"


def _nfaults(r: dict) -> int:
    return 0 if r["outcome"] in ACCEPT else 1


PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "normal": (INPUT_ASPECTS, 2, "normal"),
    "exceptional": (OUTCOME_ASPECT, 1, "exceptional"),
    "detailed": (FINE_ALL_ASPECTS, 2, None),
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
    return enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    from eth_consensus_specs.gloas import minimal as spec
    _, chosen = build_profile(_recs(), name)
    reps = [SimpleNamespace(**r) for r in chosen]
    out = output_dir or (Path(__file__).parent / "reftests")
    return ConsolidationRequestMaterializer(spec, MODEL).materialize_reps(out, reps)
