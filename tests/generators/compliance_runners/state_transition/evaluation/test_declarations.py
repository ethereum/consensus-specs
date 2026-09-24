"""Explicit expected obligations, independent of the enumeration implementation."""

from types import SimpleNamespace

import pytest

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    describe,
    GRANULARITIES,
    NA,
    score,
)
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    Bytes,
    categorical,
    choose,
    comparison,
    constant,
    coverage_spec,
    derived,
    each,
    exhaustive,
    factor,
    fix,
    Integer,
    maximum,
    nwise,
)
from tests.generators.compliance_runners.tools.coverage_model import Expr, expression


def obligation(**values):
    return frozenset(values.items())


def definition(attributes, factors, profiles, **kwargs):
    return coverage_spec(
        "example",
        focus="test focus",
        record="one vector",
        attributes=attributes,
        aspects=(aspect("test", *factors),),
        profiles=profiles,
        **kwargs,
    )


def bound(definition, **kwargs):
    return bind(definition, observe_attributes=lambda ctx: ctx.pre, **kwargs).for_spec(
        SimpleNamespace()
    )


def test_conditional_selection_and_exhaustive_shorter_branch():
    a, b = attribute("a", Boolean()), attribute("b", Boolean())
    A = factor("A", a)
    B = factor("B", b, when=A)
    d = definition(
        (a, b),
        (A, B),
        {
            "a": each([A]),
            "b": each([B]),
            "all": exhaustive([A, B]),
            "fixed": fix(B=True),
            "conflict": fix(A=False) * fix(B=True),
        },
    )
    t = bound(d)
    assert t.profiles["a"].run("predicate") == {obligation(A=False), obligation(A=True)}
    assert t.profiles["b"].run("predicate") == {
        obligation(A=True, B=False),
        obligation(A=True, B=True),
    }
    assert t.profiles["all"].run("predicate") == {
        obligation(A=False),
        obligation(A=True, B=False),
        obligation(A=True, B=True),
    }
    assert t.profiles["fixed"].run("predicate") == {obligation(A=True, B=True)}
    assert t.profiles["conflict"].run("predicate") == set()


@pytest.mark.parametrize("granularity", GRANULARITIES)
@pytest.mark.parametrize("condition_style", ["negation", "equality", "inequality"])
def test_comparison_activation_includes_every_valid_prerequisite_bucket(
    granularity, condition_style
):
    x = attribute("x", Integer())
    A = comparison("positive", x, 0)
    false, true = expression(value=False), expression(value=True)
    condition = {"negation": ~A, "equality": false == A, "inequality": true != A}[condition_style]
    B = factor("child", x == 0, when=condition)
    t = bound(definition((x,), (A, B), {"child": each([B]), "all": exhaustive([A, B])}))
    positives = {v for v in t.factors[0].domain(granularity) if t.factors[0].holds(v, granularity)}
    negatives = set(t.factors[0].domain(granularity)) - positives
    assert t.profiles["child"].run(granularity) == {
        obligation(positive=v, child=b) for v in negatives for b in (False, True)
    }
    # No arithmetic solver yet: relationships beyond activation need explicit feasibility.
    assert {obligation(positive=v) for v in positives} <= t.profiles["all"].run(granularity)


def test_nested_and_mutually_exclusive_activation():
    a = attribute("a", Boolean())
    A = factor("A", a)
    B = factor("B", a, when=A)
    C = factor("C", a, when=B)
    D = factor("D", a, when=~A)
    t = bound(definition((a,), (D, C, B, A), {"c": each([C]), "branches": exhaustive([B, D])}))
    assert t.profiles["c"].run("predicate") == {
        obligation(A=True, B=True, C=v) for v in (False, True)
    }
    assert t.profiles["branches"].run("predicate") == {
        obligation(A=True, B=v) for v in (False, True)
    } | {obligation(A=False, D=v) for v in (False, True)}
    ctx = Context(t._bound_spec, {"a": False}, None, None, {})
    record = t.record(t.observation(ctx), "predicate")
    assert record == {"A": False, "B": NA, "C": NA, "D": False}


def test_categorical_activation():
    a = attribute("a", Boolean())
    A = categorical("A", choose(a, "ON", "OFF"), ("ON", "OFF"))
    B = factor("B", a, when=A == "ON")
    t = bound(definition((a,), (A, B), {"b": each([B])}))
    assert t.profiles["b"].run("predicate") == {obligation(A="ON", B=v) for v in (False, True)}


def test_feasibility_checks_complete_extensions_and_preserves_unexpected():
    a = attribute("a", Boolean())
    A, B = factor("A", a), factor("B", a)

    # A=True has no extension, despite neither individual conflict mentioning A alone.
    def feasible(assignment, granularity):
        return not (assignment.get("A") is True and "B" in assignment)

    t = bound(definition((a,), (A, B), {"a": each([A])}, feasible=feasible))
    assert t.profiles["a"].run("predicate") == {obligation(A=False)}
    assert t.profiles["a"].run("predicate", filtered=False) == {
        obligation(A=False),
        obligation(A=True),
    }
    report = score(t, [{"A": True, "B": False}], t.profiles["a"], "predicate")
    assert report.unexpected == [{"A": True}]


def test_applicability_availability_and_missing_values():
    active, post = attribute("active", Boolean()), attribute("post", Boolean())
    x = attribute("x", Integer(min=0))
    A = factor("A", x > 0, available_when=post)
    t = bound(definition((active, post, x), (A,), {"a": each([A])}, applicable_when=active))
    for attrs in (
        {"active": False, "post": True, "x": NA},
        {"active": True, "post": False, "x": NA},
        {"active": True, "post": True, "x": NA},
    ):
        assert t.observation(Context(t._bound_spec, attrs, None, None, {}))["A"] is NA
    assert len(t.profiles["a"].run("predicate")) == 2  # Availability never erases obligations.
    with pytest.raises(ValueError, match="attributes mismatch"):
        t.observation(Context(t._bound_spec, {"active": False, "post": False}, None, None, {}))


def test_derived_expressions_short_circuit_and_constant_validation():
    x, c = attribute("x", Integer(min=0)), constant("c", Integer(min=1))
    after = derived("after", choose(x > 0, maximum(0, x - 1), c))
    A = comparison("A", after, c)
    d = definition((x,), (A,), {"a": each([A])}, constants=(c,))
    template = bind(d, observe_attributes=lambda ctx: ctx.pre, constants={"c": lambda spec: spec.c})
    t = template.for_spec(SimpleNamespace(c=4))
    assert t.observation(Context(t._bound_spec, {"x": 0}, None, None, {}))["A"] == 0
    assert t.observation(Context(t._bound_spec, {"x": 7}, None, None, {}))["A"] == 2
    assert choose(condition=False, yes=expression(1) % x, no=9).evaluate({"x": 0}, {}) == 9
    with pytest.raises(ValueError, match="outside"):
        template.for_spec(SimpleNamespace(c=0))
    with pytest.raises(ValueError, match="attributes mismatch"):
        t.observation(Context(t._bound_spec, {"x": 1, "c": 99}, None, None, {}))


def test_review_displays_definitions_and_conditional_examples():
    a = attribute("a", Boolean())
    A = factor("A", a)
    B = factor("B", a, when=A, description="Exercise the active branch.")
    t = bound(definition((a,), (A, B), {"all": exhaustive([A, B])}))
    review = describe(t)
    assert "focus: test focus" in review
    assert "record: one vector" in review
    assert "when=A" in review
    assert "profile all: 3 obligations" in review
    assert "B included:" in review
    assert "B omitted:" in review
    assert "Exercise the active branch." in review


def test_declarations_reject_unsupported_or_ambiguous_operations():
    x, a = attribute("x", Integer()), attribute("a", Boolean())
    with pytest.raises(TypeError, match="no truth value"):
        bool(x > 0)
    with pytest.raises(TypeError, match="no truth value"):
        _ = 0 < x < 3
    with pytest.raises(TypeError, match="integer operands"):
        _ = a + 1
    with pytest.raises(TypeError, match="boolean expression"):
        factor("bad", x)
    with pytest.raises(TypeError, match="matching branch types"):
        choose(a, 1, "bad")
    with pytest.raises(TypeError, match="unsupported expression"):
        expression(lambda: True)
    with pytest.raises(ValueError, match="unsupported expression"):
        Expr("call", ())
    with pytest.raises(ValueError, match="empty integer domain"):
        Integer(min=3, max=1)


def test_undeclared_inputs_duplicate_names_and_invalid_activation():
    a, b = attribute("a", Boolean()), attribute("b", Boolean())
    A = factor("A", a)
    with pytest.raises(ValueError, match="undeclared input"):
        definition((b,), (A,), {"a": each([A])})
    with pytest.raises(ValueError, match="duplicate input"):
        definition((a, a), (A,), {"a": each([A])})
    B = factor("B", b, when=a)
    with pytest.raises(ValueError, match="activation supports"):
        definition((a, b), (A, B), {"a": each([A])})
    B = factor("B", b, when=A | ~A)
    with pytest.raises(ValueError, match="activation supports"):
        definition((a, b), (A, B), {"a": each([A])})
    with pytest.raises(ValueError, match="constant bindings"):
        bind(
            definition((a,), (A,), {"a": each([A])}),
            observe_attributes=lambda ctx: {},
            constants={"extra": lambda spec: 1},
        )
    with pytest.raises(ValueError, match="strength"):
        nwise([A], 2)


def test_bytes_domain_validates_roots_and_rejects_arithmetic():
    root = attribute("root", Bytes(length=32))
    zero = constant("zero", Bytes(length=32))
    A = factor("nonzero", root != zero)
    d = definition((root,), (A,), {"a": each([A])}, constants=(zero,))
    t = bound(d, constants={"zero": lambda spec: bytes(32)})
    assert (
        t.observation(Context(t._bound_spec, {"root": bytes(32)}, None, None, {}))["nonzero"]
        is False
    )
    assert (
        t.observation(Context(t._bound_spec, {"root": bytes([1]) * 32}, None, None, {}))["nonzero"]
        is True
    )
    for invalid in (bytes(31), bytearray(32), "root", 0):
        with pytest.raises(ValueError, match="expected Bytes"):
            t.observation(Context(t._bound_spec, {"root": invalid}, None, None, {}))
    with pytest.raises(TypeError, match="integer operands"):
        _ = root + zero
    with pytest.raises(TypeError, match="integer operands"):
        _ = root < zero
    with pytest.raises(ValueError, match="expected Bytes"):
        bound(d, constants={"zero": lambda spec: bytes(31)})
    with pytest.raises(ValueError, match="nonnegative"):
        Bytes(length=-1)
