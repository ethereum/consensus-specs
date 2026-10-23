"""Regression checks for process_operations coverage claims."""

from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    BoundFormula,
    fix,
)
from tests.generators.compliance_runners.state_transition.provider import load_provider

from .materializer import OperationsMaterializer
from .target import TARGET

validate_case = load_provider("operations").validate_case


def _write_case(tmp_path, **obligation):
    target = TARGET.for_spec(spec)
    completed = BoundFormula(target, fix(**obligation)).generation_obligations()
    assert len(completed) == 1
    materializer = OperationsMaterializer(spec)
    materializer.test_provider = "process_operations"
    materializer.materialize_reps(tmp_path, [SimpleNamespace(**dict(next(iter(completed))))])
    return tmp_path / "minimal/gloas/sanity/blocks/pyspec_tests/case_0000"


def test_requested_acceptance_survives_failed_materialization(tmp_path, monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("simulated transition failure")

    monkeypatch.setattr(spec, "state_transition", reject)
    case_dir = _write_case(tmp_path, accepted=True)

    checks = validate_case(case_dir)
    assert any(
        check.dimension == "accepted" and check.claimed is True and check.actual is False
        for check in checks
    )


def test_validator_checks_post_state_presence(tmp_path):
    case_dir = _write_case(tmp_path, accepted=True)
    (case_dir / "post.ssz_snappy").unlink()

    checks = validate_case(case_dir)
    assert any(check.dimension == "accepted" and check.status == "mismatch" for check in checks)


def test_unspecified_acceptance_follows_requested_failed_gate(tmp_path):
    case_dir = _write_case(tmp_path, deposits_empty=False)

    checks = validate_case(case_dir)
    assert all(check.status == "ok" for check in checks)
