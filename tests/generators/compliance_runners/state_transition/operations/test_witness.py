"""Check that partial coverage obligations produce distinct concrete witnesses."""

from types import SimpleNamespace

import pytest

from eth_consensus_specs.gloas import minimal as spec

from .coverage import build_profile
from .materializer import OperationsMaterializer
from .witness import complete_obligation, GATES


@pytest.mark.parametrize("profile", ["smoke", "normal", "exceptional", "standard"])
def test_completed_witnesses_cover_each_obligation_once(profile):
    obligations, witnesses = build_profile(profile, spec=spec)
    signatures = [tuple(witness.items()) for witness in witnesses]
    assert len(signatures) == len(set(signatures))
    assert all(witness["accepted"] is all(witness[gate] for gate in GATES) for witness in witnesses)
    assert all(
        any(
            all(witness[key] == value for key, value in obligation.items()) for witness in witnesses
        )
        for obligation in obligations
    )


def test_rejection_completion_preserves_explicit_true_gate():
    witness = complete_obligation({"accepted": False, "deposits_empty": True})
    assert witness["deposits_empty"] is True
    assert witness["proposer_slashings_within_limit"] is False


def test_smoke_materialization_has_no_duplicate_inputs(tmp_path):
    _, witnesses = build_profile("smoke", spec=spec)
    materializer = OperationsMaterializer(spec)
    materializer.test_provider = "process_operations"
    materializer.materialize_reps(tmp_path, [SimpleNamespace(**witness) for witness in witnesses])
    cases = sorted((tmp_path / "minimal/gloas/sanity/blocks/main").glob("case_*"))
    inputs = [
        ((case / "pre.ssz_snappy").read_bytes(), (case / "blocks_0.ssz_snappy").read_bytes())
        for case in cases
    ]
    assert len(inputs) == len(set(inputs)) == len(witnesses)
