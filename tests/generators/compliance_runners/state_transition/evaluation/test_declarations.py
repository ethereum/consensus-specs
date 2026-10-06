"""Explicit expected obligations, independent of the enumeration implementation."""

from types import SimpleNamespace

import pytest

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Cmp,
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
    modulo,
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
    assert t.profiles["a"].run() == {obligation(A=False), obligation(A=True)}
    assert t.profiles["b"].run() == {
        obligation(A=True, B=False),
        obligation(A=True, B=True),
    }
    assert t.profiles["all"].run() == {
        obligation(A=False),
        obligation(A=True, B=False),
        obligation(A=True, B=True),
    }
    assert t.profiles["fixed"].run() == {obligation(A=True, B=True)}
    assert t.profiles["conflict"].run() == set()


@pytest.mark.parametrize("granularity", GRANULARITIES)
@pytest.mark.parametrize("condition_style", ["negation", "equality", "inequality"])
def test_comparison_activation_includes_every_valid_prerequisite_bucket(
    granularity, condition_style
):
    x = attribute("x", Integer())
    A = comparison("positive", x, 0, granularity=granularity)
    false, true = expression(value=False), expression(value=True)
    condition = {"negation": ~A, "equality": false == A, "inequality": true != A}[condition_style]
    B = factor("child", x == 0, when=condition)
    t = bound(definition((x,), (A, B), {"child": each([B]), "all": exhaustive([A, B])}))
    positives = {v for v in t.factors[0].domain() if t.factors[0].holds(v)}
    negatives = set(t.factors[0].domain()) - positives
    assert t.profiles["child"].run() == {
        obligation(positive=v, child=b) for v in negatives for b in (False, True)
    }
    # No arithmetic solver yet: relationships beyond activation need explicit feasibility.
    assert {obligation(positive=v) for v in positives} <= t.profiles["all"].run()


def test_mixed_comparison_granularities_preserve_activation_and_profile_domains():
    x, y = attribute("x", Integer()), attribute("y", Integer())
    A = comparison("positive", x, 0, granularity="cmp3")
    B = comparison("zero", y, 0, op="==", granularity="cmp5")
    C = comparison("nonnegative", x, 0, op=">=")
    child = factor("child", x > 1, when=A & ~B)
    t = bound(
        definition(
            (x, y),
            (A, B, C, child),
            {"smoke": each([A, B, C, child]), "max": exhaustive([A, B, C, child])},
        )
    )
    expected = {"positive": "GT", "zero": "GT_1", "nonnegative": True, "child": True}
    assert (
        t.record(t.observation(Context(t._bound_spec, {"x": 2, "y": 1}, None, None, {})))
        == expected
    )
    assert (
        t.record(t.observation(Context(t._bound_spec, {"x": 2, "y": 0}, None, None, {})))["child"]
        is NA
    )
    assert (
        t.record(t.observation(Context(t._bound_spec, {"x": 0, "y": 1}, None, None, {})))["child"]
        is NA
    )
    for formula in t.profiles.values():
        obligations = formula.run()
        for f in t.factors[:3]:
            assert {dict(o)[f.name] for o in obligations if f.name in dict(o)} == set(f.domain())
    assert obligation(positive="GT", zero="GT_1", child=True) in t.profiles["smoke"].run()
    report = score(t, [expected], t.profiles["max"])
    assert report.covered == 1
    assert report.comparison_granularities == {
        "positive": "cmp3",
        "zero": "cmp5",
        "nonnegative": "predicate",
    }
    assert "granularity=cmp5" in t.review()
    with pytest.raises(TypeError):
        t.profiles["smoke"].run("cmp3")


def test_comparison_granularity_is_validated_at_declaration_time():
    x = attribute("x", Integer())
    with pytest.raises(ValueError, match="unknown granularity"):
        comparison("invalid", x, 0, granularity="cmp4")
    with pytest.raises(ValueError, match="unknown granularity"):
        Cmp("invalid", op=">", granularity="cmp4")


def test_nested_and_mutually_exclusive_activation():
    a = attribute("a", Boolean())
    A = factor("A", a)
    B = factor("B", a, when=A)
    C = factor("C", a, when=B)
    D = factor("D", a, when=~A)
    t = bound(definition((a,), (D, C, B, A), {"c": each([C]), "branches": exhaustive([B, D])}))
    assert t.profiles["c"].run() == {obligation(A=True, B=True, C=v) for v in (False, True)}
    assert t.profiles["branches"].run() == {obligation(A=True, B=v) for v in (False, True)} | {
        obligation(A=False, D=v) for v in (False, True)
    }
    ctx = Context(t._bound_spec, {"a": False}, None, None, {})
    record = t.record(t.observation(ctx))
    assert record == {"A": False, "B": NA, "C": NA, "D": False}


def test_categorical_activation():
    a = attribute("a", Boolean())
    A = categorical("A", choose(a, "ON", "OFF"), ("ON", "OFF"))
    B = factor("B", a, when=A == "ON")
    t = bound(definition((a,), (A, B), {"b": each([B])}))
    assert t.profiles["b"].run() == {obligation(A="ON", B=v) for v in (False, True)}


def test_feasibility_checks_complete_extensions_and_preserves_unexpected():
    a = attribute("a", Boolean())
    A, B = factor("A", a), factor("B", a)

    # A=True has no extension, despite neither individual conflict mentioning A alone.
    def feasible(assignment):
        return not (assignment.get("A") is True and "B" in assignment)

    t = bound(definition((a,), (A, B), {"a": each([A])}, feasible=feasible))
    assert t.profiles["a"].run() == {obligation(A=False)}
    assert t.profiles["a"].run(filtered=False) == {
        obligation(A=False),
        obligation(A=True),
    }
    report = score(t, [{"A": True, "B": False}], t.profiles["a"])
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
    assert len(t.profiles["a"].run()) == 2  # Availability never erases obligations.
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


@pytest.mark.parametrize(
    ("domain", "expected"),
    [
        (Integer(min=0), ("EQ", "GT_1", "GT_FAR")),
        (Integer(min=0, max=1), ("EQ", "GT_1")),
        (Integer(min=2, max=4), ("GT_FAR",)),
        (Integer(min=-1, max=1), ("LT_1", "EQ", "GT_1")),
    ],
)
def test_comparison_domains_remove_impossible_buckets(domain, expected):
    x = attribute("x", domain)
    A = comparison("count", x, 0, granularity="cmp5")
    t = bound(definition((x,), (A,), {"all": each([A])}))
    assert t.factors[0].domain() == expected
    assert t.profiles["all"].run() == {obligation(count=v) for v in expected}
    assert t.profiles["all"].run(filtered=False) == t.profiles["all"].run()


@pytest.mark.parametrize("op", ["<", "<=", "==", "!=", ">=", ">"])
@pytest.mark.parametrize("granularity", GRANULARITIES)
def test_bounded_comparison_domains_match_concrete_values(op, granularity):
    for lo, hi in ((0, 0), (0, 1), (-4, -2), (-1, 3), (3, 4)):
        x = attribute("x", Integer(min=lo, max=hi))
        A = comparison("A", x, 0, op=op, granularity=granularity)
        t = bound(definition((x,), (A,), {"all": each([A])}))
        assert set(t.factors[0].domain()) == {t.factors[0].abstract(v) for v in range(lo, hi + 1)}


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        (1, ("ZERO",)),
        (2, ("ZERO", "ONE")),
        (3, ("ZERO", "ONE", "LAST")),
        (4, ("ZERO", "ONE", "LAST", "INTERIOR")),
        (8, ("ZERO", "ONE", "LAST", "INTERIOR")),
    ],
)
def test_modulo_domains_and_observations_follow_bound_constant(period, expected):
    x = attribute("x", Integer())
    c = constant("period", Integer(min=1))
    A = modulo("position", x, c)
    B = factor("child", x > 0, when=A == "ZERO")
    d = definition((x,), (A, B), {"all": each([A]), "child": each([B])}, constants=(c,))
    template = bind(
        d, observe_attributes=lambda ctx: ctx.pre, constants={"period": lambda spec: spec.period}
    )
    t = template.for_spec(SimpleNamespace(period=period))
    assert t.factors[0].domain() == expected
    assert t.profiles["all"].run() == {obligation(position=v) for v in expected}
    assert t.profiles["child"].run() == {
        obligation(position="ZERO", child=v) for v in (False, True)
    }
    records = [
        t.record(t.observation(Context(t._bound_spec, {"x": i}, None, None, {})))
        for i in range(-period, 2 * period)
    ]
    assert {r["position"] for r in records} == set(expected)
    assert records[period]["position"] == "ZERO"
    if period >= 2:
        assert records[period + 1]["position"] == "ONE"
    if period >= 3:
        assert records[2 * period - 1]["position"] == "LAST"
    if period >= 4:
        assert records[period + 2]["position"] == "INTERIOR"
    assert score(t, records, t.profiles["all"]).percent == 100
    assert str(expected) in t.review()
    assert t.observation(Context(t._bound_spec, {"x": NA}, None, None, {}))["position"] is NA


def test_modulo_literal_and_invalid_moduli():
    x = attribute("x", Integer(min=0))
    A = modulo("position", x, 2)
    assert bound(definition((x,), (A,), {"all": each([A])})).factors[0].domain() == ("ZERO", "ONE")
    for invalid in (0, -1, x, constant("period", Integer()), True):
        with pytest.raises(ValueError, match="modulus"):
            modulo("position", x, invalid)


def test_comparison_of_remainder_uses_implicit_bounds_and_bound_constants():
    x = attribute("x", Integer())
    c = constant("period", Integer(min=1))
    zero = comparison("zero", x % c, 0, op="==", granularity="cmp5")
    last = comparison("last", x % c, c - 1, op="==", granularity="cmp5")
    d = definition((x,), (zero, last), {"all": each([zero, last])}, constants=(c,))
    t = bound(d, constants={"period": lambda spec: 4})
    assert t.factors[0].domain() == ("EQ", "GT_1", "GT_FAR")
    assert t.factors[1].domain() == ("LT_FAR", "LT_1", "EQ")


def test_unreachable_modulo_activation_is_omitted_after_binding():
    x = attribute("x", Integer())
    c = constant("period", Integer(min=1))
    A = modulo("position", x, c)
    B = factor("child", x > 0, when=A == "LAST")
    d = definition((x,), (A, B), {"child": each([B])}, constants=(c,))
    t = bound(d, constants={"period": lambda spec: 2})
    assert t.profiles["child"].run() == set()
    assert t.record(t.observation(Context(t._bound_spec, {"x": 1}, None, None, {})))["child"] is NA
