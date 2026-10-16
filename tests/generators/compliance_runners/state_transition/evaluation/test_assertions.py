"""Assertion truth, scoped coverage, and independent outcome diagnostics."""

from types import SimpleNamespace

import pytest

from .coverage_dsl import Context, NA, score
from .declarations import (
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    cmp5,
    coverage_spec,
    dimension,
    each,
    fix,
    Integer,
    union,
)


def example(*, complete=True):
    x = attribute("x", Integer(-2, 2))
    y = attribute("y", Boolean())
    post = attribute("post", Boolean())
    a = assertion("positive", cmp5(x, 0, op=">"))
    b = assertion("valid", y)
    observed = dimension("accepted", post)
    checks = aspect("checks", a, b)
    assertions = assertion_set(checks, observed=observed, complete=complete)
    profiles = {
        "all": each((a, b, observed)),
        "normal": assertions.normal(each((a, b))),
        "single": assertions.exceptional(each((a, b)), faults=1),
        "double": assertions.exceptional(each((a, b)), faults=2),
        "range": assertions.exceptional(each((a, b)), faults=(1, 2)),
        "mixed": union(assertions.normal(each((a,))), assertions.exceptional(each((b,)), faults=2)),
        "product": assertions.normal(each((a,))) * assertions.exceptional(each((b,)), faults=1),
    }
    definition = coverage_spec(
        "example",
        focus="assertions",
        record="one vector",
        attributes=(x, y, post),
        aspects=(checks, aspect("outcome", observed)),
        profiles=profiles,
        assertions=assertions,
    )
    return bind(definition, observe_attributes=lambda ctx: ctx.pre).for_spec(
        SimpleNamespace(), backend="python"
    )


def test_assertion_summary_uses_predicate_truth_and_preserves_observed_outcome():
    target = example()
    obs = target.observation(
        Context(target._bound_spec, {"x": 2, "y": True, "post": False}, None, None, {})
    )
    record = target.record(obs)
    result = target.assertion_result(record)
    assert record == {"positive": "GT_FAR", "valid": True, "accepted": False}
    assert result.fault_count == 0
    assert result.expected_accepted is True
    assert result.failed == result.unknown == ()
    report = score(target, [record], target.profiles["all"])
    assert report.outcome_mismatches == [
        {"record": 0, "observed_accepted": False, "expected_accepted": True}
    ]
    assert report.as_dict()["outcome_mismatches"] == report.outcome_mismatches
    assert "assertion positive" in target.review()


def test_incomplete_slice_does_not_predict_whole_execution_success():
    target = example(complete=False)
    records = [{"positive": "GT_1", "valid": True, "accepted": False}]
    assert score(target, records, target.profiles["all"]).outcome_mismatches == []
    records = [{"positive": "EQ", "valid": True, "accepted": True}]
    assert (
        score(target, records, target.profiles["all"]).outcome_mismatches[0]["expected_accepted"]
        is False
    )


def test_fault_limits_restrict_records_even_when_projection_matches():
    target = example()
    double = {"positive": "EQ", "valid": False, "accepted": False}
    single = {"positive": "EQ", "valid": True, "accepted": False}
    obligation = frozenset({("positive", "EQ")})
    assert obligation in target.profiles["single"].run()
    assert score(target, [double], target.profiles["single"]).covered == 0
    assert score(target, [single], target.profiles["single"]).covered == 2
    assert score(target, [double], target.profiles["double"]).covered == 2
    assert score(target, [double, single], target.profiles["range"]).covered == 3
    assert target.profiles["product"].run() == set()


def test_union_keeps_branch_specific_fault_limits():
    target = example()
    single = {"positive": "GT_1", "valid": False, "accepted": False}
    # Each projection exists in one branch, but this record belongs to neither.
    assert score(target, [single], target.profiles["mixed"]).covered == 0
    assert (
        score(
            target, [{**single, "valid": True, "accepted": True}], target.profiles["mixed"]
        ).covered
        == 1
    )
    assert score(target, [{**single, "positive": "EQ"}], target.profiles["mixed"]).covered == 1


def test_scoped_generation_preserves_fault_budget():
    target = example()
    for name, count in (("normal", 0), ("single", 1), ("double", 2)):
        formula = target.profiles[name]
        records = [dict(o) for o in formula.generation_obligations()]
        assert records
        assert all(target.assertion_result(r).fault_count == count for r in records)
        report = score(target, records, formula)
        assert report.covered == report.total
        assert report.unexpected == report.outcome_mismatches == []


def test_complete_generation_prefers_fewer_faults_and_retains_branch_scopes():
    target = example()
    for name in ("all", "mixed", "single", "double"):
        formula = target.profiles[name]
        records = [dict(o) for o in formula.generation_obligations()]
        assert all(set(r) == {"positive", "valid", "accepted"} for r in records)
        report = score(target, records, formula)
        assert report.covered == report.total
        assert report.unexpected == report.outcome_mismatches == []
        if name == "all":
            assert max(target.assertion_result(r).fault_count for r in records) == 1
        if name == "mixed":
            assert {target.assertion_result(r).fault_count for r in records} == {0, 2}


def test_unknown_is_not_zero_faults_but_known_failure_still_predicts_rejection():
    target = example()
    checks = target.definition.assertions
    record = {"positive": NA, "valid": True, "accepted": True}
    result = checks.evaluate(record)
    assert result.fault_count is None
    assert result.expected_accepted is None
    assert result.unknown == ("positive",)
    assert score(target, [record], target.profiles["normal"]).covered == 0
    record["valid"] = False
    assert checks.evaluate(record).expected_accepted is False
    assert checks.evaluate(record).failed == ("valid",)
    assert score(target, [record], target.profiles["single"]).covered == 0


def test_inactive_assertion_is_not_an_unknown_or_a_fault():
    active = attribute("active_input", Boolean())
    value = attribute("value_input", Boolean())
    gate = dimension("enabled", active)
    check = assertion("check", value, when=gate)
    checks = assertion_set(check)
    assert checks.evaluate({"enabled": False, "check": NA}).fault_count == 0
    assert checks.evaluate({"enabled": True, "check": NA}).fault_count is None
    assert checks.evaluate({"enabled": True, "check": False}).fault_count == 1
    assert checks.evaluate({"check": False}).fault_count is None


def test_unavailable_assertion_observation_remains_unknown():
    available = attribute("available", Boolean())
    value = attribute("value", Boolean())
    check = assertion("check", value, available_when=available)
    checks = assertion_set(check)
    definition = coverage_spec(
        "unavailable",
        focus="test",
        record="one",
        attributes=(available, value),
        aspects=(aspect("checks", check),),
        assertions=checks,
        profiles={"normal": checks.normal(each((check,)))},
    )
    target = bind(definition, observe_attributes=lambda ctx: ctx.pre).for_spec(
        SimpleNamespace(), backend="python"
    )
    obs = target.observation(
        Context(target._bound_spec, {"available": False, "value": True}, None, None, {})
    )
    assert target.assertion_result(target.record(obs)).expected_accepted is None


@pytest.mark.parametrize(("minimum", "maximum"), [(-1, None), (True, 1), (2, 1), (0, False)])
def test_invalid_fault_limits(minimum, maximum):
    target = example()
    with pytest.raises(ValueError, match="fault limits"):
        target.definition.assertions.faults(fix(), minimum=minimum, maximum=maximum)


def test_assertion_declarations_and_sets_are_validated():
    value = attribute("value", Integer(0, 2))
    with pytest.raises(TypeError, match="assertions require"):
        assertion("enum", value)
    with pytest.raises(ValueError, match="nonempty"):
        assertion_set(aspect("ordinary", dimension("ordinary", value)))
    check = assertion("check", value > 0)
    with pytest.raises(ValueError, match="unique"):
        assertion_set(check, check)
    with pytest.raises(TypeError, match="assertions and aspects"):
        assertion_set(check, dimension("ordinary", value))
    with pytest.raises(ValueError, match="at least one"):
        assertion_set(check).exceptional(each((check,)), faults=0)
