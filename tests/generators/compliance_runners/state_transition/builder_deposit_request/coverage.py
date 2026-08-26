"""Coverage profiles for process_builder_deposit_request.

Handler-specific instantiation of the shared ``..aspect_coverage`` engine.
Reuses the shared aspects builder_membership and signed_message (the SAME
signature aspect execution_payload_bid binds).

Run:
    uv run python -m ...builder_deposit_request.coverage
    uv run python -m ...builder_deposit_request.coverage standard --materialize
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..aspect_coverage import build_profile as _build_profile, enumerate_signatures
from .materializer import _DIMS, BuilderDepositRequestMaterializer

INPUT_ASPECTS = {
    "withdrawal_credential": ["withdrawal_credentials_profile"],
    "builder_membership": ["builder_pubkey_found"],
    "signed_message": ["builder_signature_valid"],
    "deposit_amount": ["amount_profile", "amount_nonzero"],
    "builder_reset": ["builder_withdrawable_epoch_set", "builder_balance_zero"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_builder_deposit_request.mzn"


def _nfaults(r: dict) -> int:
    is_builder = r["withdrawal_credentials_profile"] == "BUILDER"
    faults = int(not is_builder)
    # The signature is checked only for a new builder with the right prefix.
    if is_builder and not r["builder_pubkey_found"]:
        faults += int(r["builder_signature_valid"] != "T")
    return faults


def build_profile(recs, name):
    return _build_profile(recs, name, ALL_ASPECTS, INPUT_ASPECTS, OUTCOME_ASPECT)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    from eth_consensus_specs.gloas import minimal as spec

    _, chosen = build_profile(_recs(), name)
    reps = [SimpleNamespace(**r) for r in chosen]
    out = output_dir or (Path(__file__).parent / "reftests")
    return BuilderDepositRequestMaterializer(spec, MODEL).materialize_reps(out, reps)
