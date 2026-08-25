"""Coverage profiles for process_deposit_request.

This handler has no rejections, so there is no normal/exceptional split — just a
combinatorial sweep over its input-shape dimensions. `standard` = pairwise over
all aspects.

Run:
    uv run python -m ...deposit_request.coverage
    uv run python -m ...deposit_request.coverage standard --materialize
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import cover, enumerate_signatures
from .materializer import DepositRequestMaterializer, _DIMS

INPUT_ASPECTS = {
    "deposit_amount": ["amount_profile", "amount_nonzero"],
    "withdrawal_credentials": ["withdrawal_credentials_profile"],
    "signature": ["signature_profile"],
    "deposit_pubkey": ["pubkey_is_existing_validator"],
}
ALL_ASPECTS = INPUT_ASPECTS
MODEL = Path(__file__).parent / "models" / "handler_deposit_request.mzn"


def _nfaults(_r: dict) -> int:
    return 0  # no failing gates in this handler


PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "standard": (ALL_ASPECTS, 2, None),
}


def build_profile(recs, name):
    if name == "all":
        return len(recs), recs
    aspects, t, filt = PROFILES[name]
    return cover(recs, aspects, t, filt)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    from eth_consensus_specs.gloas import minimal as spec
    _, chosen = build_profile(_recs(), name)
    reps = [SimpleNamespace(**r) for r in chosen]
    out = output_dir or (Path(__file__).parent / "reftests")
    return DepositRequestMaterializer(spec, MODEL).materialize_reps(out, reps)
