"""Generic recovery preserves observation, activation, and assertion semantics."""

from types import SimpleNamespace

from tests.generators.compliance_runners.state_transition import declaration_validation, provider
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    recover_record,
    target_validator,
    validate_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context, NA
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    constant,
    coverage_spec,
    dimension,
    Integer,
)


def target(*, complete=True):
    enabled = attribute("enabled", Boolean())
    value = attribute("value", Boolean())
    limit = constant("bound_limit", Integer(0, 2))
    accepted = attribute("post_present", Boolean())
    gate = dimension("gate", enabled)
    check = assertion("check", value, when=gate)
    result = dimension("accepted", accepted)
    # Include a constant in coverage so bindings and projection use one spec.
    definition = coverage_spec(
        "validation",
        focus="shared validation",
        record="one vector",
        aspects=(aspect("a", gate, check, result, dimension("limit", limit)),),
        profiles={},
        assertions=assertion_set(check, observed=result, complete=complete),
    )
    return bind(
        definition,
        observe_attributes=lambda ctx: {**ctx.pre, "post_present": ctx.post is not None},
        constants={"bound_limit": lambda spec: spec.limit},
    )


def context(enabled=True, value=True, post=None):
    return Context(SimpleNamespace(limit=1), {"enabled": enabled, "value": value}, None, post, {})


def test_default_recovery_encodes_inactive_dimensions():
    _, record, actual = recover_record(target(), context(enabled=False, value=NA))
    assert record["check"] is NA
    assert actual == {"gate": False, "check": "NA", "accepted": False, "limit": 1}


def test_validation_checks_claims_fault_counts_and_actual_post_presence():
    checks = validate_record(target(), context(), {"check": False, "fault_count": 1, "bogus": True})
    assert {c.dimension for c in checks if c.status == "mismatch"} == {
        "check",
        "fault_count",
        "bogus",
        "assertion_outcome",
    }
    checks = validate_record(target(), context(value=False, post=object()), {"fault_count": 1})
    assert next(c for c in checks if c.dimension == "assertion_outcome").status == "mismatch"


def test_incomplete_assertion_set_does_not_predict_acceptance():
    checks = validate_record(target(complete=False), context(), {"fault_count": 0})
    assert all(c.status == "ok" for c in checks)
    assert not any(c.dimension == "assertion_outcome" for c in checks)


def test_unknown_assertions_remain_unknown():
    checks = validate_record(target(), context(value=NA), {"fault_count": 0, "check": "NA"})
    assert next(c for c in checks if c.dimension == "fault_count").actual is None
    assert not any(c.dimension == "assertion_outcome" for c in checks)


def test_factory_and_provider_follow_case_spec(tmp_path, monkeypatch):
    case = tmp_path / "operations" / "fake" / "main" / "case_0000"
    case.mkdir(parents=True)
    (case / "dimensions.yaml").write_text("claimed: {limit: 2, check: true}\n")
    (case / "post.ssz_snappy").touch()
    default = SimpleNamespace(limit=1, BeaconState=object(), Operation=object())
    alternate = SimpleNamespace(limit=2, BeaconState=object(), Operation=object())
    monkeypatch.setattr(
        declaration_validation,
        "decode",
        lambda path, sedes: (
            {"enabled": True, "value": True} if path.name == "pre.ssz_snappy" else object()
        ),
    )
    _, validator = target_validator(
        target(), operation_name="op", operation_type="Operation", spec=lambda: default
    )
    assert any(c.status == "mismatch" for c in validator(case))
    monkeypatch.setitem(provider.RUNNER_BY_HANDLER, "fake", "operations")
    monkeypatch.setattr(provider, "_spec_for_case", lambda path: alternate)
    assert provider.validate_cases(tmp_path, "fake", validator) == 0


def test_provider_rejects_missing_required_post_state(tmp_path, monkeypatch):
    case = tmp_path / "operations" / "fake" / "main" / "case_0000"
    case.mkdir(parents=True)
    (case / "dimensions.yaml").write_text("claimed: {}\n")
    case_spec = SimpleNamespace(limit=1, BeaconState=object())
    monkeypatch.setitem(provider.RUNNER_BY_HANDLER, "fake", "operations")
    monkeypatch.setattr(provider, "_spec_for_case", lambda path: case_spec)
    monkeypatch.setattr(
        declaration_validation,
        "decode",
        lambda path, sedes: {"enabled": True, "value": True},
    )
    _, validator = target_validator(
        target(complete=False), spec=lambda: case_spec, require_post=True
    )

    checks = validator(case)
    missing_post = next(check for check in checks if check.dimension == "post_state_present")
    assert (missing_post.claimed, missing_post.actual, missing_post.status) == (
        True,
        False,
        "mismatch",
    )
    assert provider.validate_cases(tmp_path, "fake", validator) == 1
