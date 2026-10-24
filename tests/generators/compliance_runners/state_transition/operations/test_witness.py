"""Check that partial coverage obligations produce distinct concrete witnesses."""

from types import SimpleNamespace

import pytest

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import score
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    BoundFormula,
    fix,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider

from .materializer import OperationsMaterializer
from .target import LIMITS, TARGET

build_profile = load_provider("operations").build_profile

GATES = tuple(f.name for f in LIMITS.factors)


@pytest.mark.parametrize("profile", ["smoke", "normal", "exceptional", "standard", "max"])
def test_completed_witnesses_cover_each_obligation_once(profile):
    witnesses = build_profile(profile, spec=spec)
    signatures = [tuple(witness.items()) for witness in witnesses]
    assert len(signatures) == len(set(signatures))
    assert all(set(witness) == {*GATES, "accepted"} for witness in witnesses)
    assert all(witness["accepted"] is all(witness[gate] for gate in GATES) for witness in witnesses)
    target = TARGET.for_spec(spec)
    report = score(target, witnesses, target.profiles[profile])
    assert report.covered == report.total
    assert not report.unexpected
    assert not report.outcome_mismatches


def test_rejection_completion_preserves_explicit_true_gate():
    target = TARGET.for_spec(spec)
    completed = BoundFormula(
        target, fix(accepted=False, deposits_empty=True)
    ).generation_obligations()
    assert len(completed) == 1
    witness = dict(next(iter(completed)))
    assert witness["deposits_empty"] is True
    assert target.assertion_result(witness).fault_count == 1
    assert witness["accepted"] is False


def test_smoke_materialization_has_no_duplicate_inputs(tmp_path):
    witnesses = build_profile("smoke", spec=spec)
    materializer = OperationsMaterializer(spec)
    materializer.test_provider = "process_operations"
    materializer.materialize_reps(tmp_path, [SimpleNamespace(**witness) for witness in witnesses])
    cases = sorted((tmp_path / "minimal/gloas/sanity/blocks/pyspec_tests").glob("case_*"))
    inputs = [
        ((case / "pre.ssz_snappy").read_bytes(), (case / "blocks_0.ssz_snappy").read_bytes())
        for case in cases
    ]
    assert len(inputs) == len(set(inputs)) == len(witnesses)
