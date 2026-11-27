"""Domain, feasibility, and provider contracts for uniform declarations."""

from types import SimpleNamespace

import pytest

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
    materializer_record,
    profile_records,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    NA,
    score,
)
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    Bytes,
    choose,
    comparison,
    constant,
    coverage_spec,
    coverage_value,
    derived,
    dimension,
    each,
    exhaustive,
    factor,
    Finite,
    fix,
    identity,
    implies,
    Integer,
    present,
)
from tests.generators.compliance_runners.state_transition.materializer import Materializer
from tests.generators.compliance_runners.state_transition.provider import load_provider
from tests.generators.compliance_runners.tools.coverage_model import expression


def target(
    attributes, factors, *, constraints=(), constants=(), bindings=None, applicable_when=True
):
    definition = coverage_spec(
        "uniform",
        focus="declaration semantics",
        record="one observation",
        attributes=attributes,
        constants=constants,
        aspects=(aspect("values", *factors),),
        profiles={"all": exhaustive(factors)},
        constraints=constraints,
        applicable_when=applicable_when,
    )
    return bind(definition, observe_attributes=lambda ctx: ctx.pre, constants=bindings)


def test_union_preserves_the_gap_and_covers_the_sentinel_exactly():
    sentinel = 2**64 - 1
    domain = Integer(0, 255) | Finite((sentinel,))
    x = attribute("x", domain)
    d = dimension("covered_x", x)
    t = target((x,), (d,)).for_spec(object(), backend="python")
    assert t.profiles["all"].run() == {
        frozenset({("covered_x", v)}) for v in (*range(256), sentinel)
    }
    membership = domain.contains(x)
    for value in (0, 255, sentinel):
        domain.validate(value)
        assert membership.evaluate({"x": value}, {}) is True
        observation = t.observation(Context(t._bound_spec, {"x": value}, None, None, {}))
        assert t.record(observation) == {"covered_x": value}
    for value in (-1, 256, sentinel - 1, True):
        with pytest.raises(ValueError, match="outside"):
            domain.validate(value)
    # Use an unrestricted input to check the lowered formula outside the domain.
    free = attribute("free", Integer())
    assert domain.contains(free).evaluate({"free": 256}, {}) is False
    assert (domain | Integer(254, 256)).values() == (*range(256), sentinel, 256)


def test_finite_domains_separate_scalar_types_and_reject_large_enumeration():
    with pytest.raises(TypeError):
        _ = Integer(0, 1) | Boolean()
    with pytest.raises(TypeError):
        Finite((1, True))
    with pytest.raises(ValueError, match="partition"):
        dimension("unbounded", attribute("x", Integer(min=0)))
    with pytest.raises(ValueError, match="partition"):
        dimension("large", attribute("x", Integer(0, 1024)))
    flag = attribute("flag", Boolean())
    label = attribute("label", Finite(("first", "last")))
    t = target((flag, label), (dimension("flag_value", flag), dimension("label_value", label)))
    assert len(t.for_spec(object(), backend="python").profiles["all"].run()) == 4


def test_constraints_use_predicate_truth_and_explicit_bucket_values():
    x = attribute("x", Integer(-2, 2))
    accepted = attribute("accepted_input", Boolean())
    cmp = comparison("positive", x, 0, op=">", granularity="cmp5")
    outcome = factor("accepted", accepted)
    t = target(
        (x, accepted),
        (cmp, outcome),
        constraints=(outcome == cmp, coverage_value(cmp) != "GT_1"),
    ).for_spec(object(), backend="python")
    assert t.profiles["all"].run() == {
        frozenset({("positive", bucket), ("accepted", truth)})
        for bucket, truth in (("LT_FAR", False), ("LT_1", False), ("EQ", False), ("GT_FAR", True))
    }
    assert not t.feasible({"positive": "GT_FAR", "accepted": False})
    report = score(t, [{"positive": "GT_1", "accepted": True}], t.profiles["all"])
    assert report.unexpected == [{"accepted": True, "positive": "GT_1"}]
    assert "constraint:" in t.review()


def test_inactive_unknown_does_not_hide_a_known_violation():
    flag = attribute("flag", Boolean())
    parent = factor("parent", flag)
    child = factor("child", flag, when=parent)
    t = target((flag,), (parent, child), constraints=(all_of(child, parent),)).for_spec(
        object(), backend="python"
    )
    assert t.profiles["all"].run() == {frozenset({("parent", True), ("child", True)})}
    assert not t.feasible({"parent": False})
    # Presence tests distinguish omission from an ordinary false value.
    t = target((flag,), (parent, child), constraints=(implies(~parent, ~present(child)),))
    assert t.for_spec(object(), backend="python").feasible({"parent": False})


def test_bound_constant_constraints_and_lazy_branches():
    flag = attribute("flag", Boolean())
    f = factor("flag_value", flag)
    period = constant("period", Integer(min=0))
    t = target(
        (flag,),
        (f,),
        constants=(period,),
        bindings={"period": lambda spec: spec.period},
        constraints=(
            implies(period > 1, f),
            choose(period == 0, yes=True, no=(expression(1) % period) == 0),
        ),
    )
    zero = t.for_spec(SimpleNamespace(period=0), backend="python")
    two = t.for_spec(SimpleNamespace(period=2), backend="python")
    assert zero.feasible({"flag_value": False})
    assert not two.feasible({"flag_value": False})
    assert not two.feasible({"flag_value": True})


@pytest.mark.parametrize("invalid", ["attribute", "factor", "constant", "nonboolean"])
def test_invalid_feasibility_declarations_fail_early(invalid):
    flag = attribute("flag", Boolean())
    f = factor("flag_value", flag)
    bad = {
        "attribute": flag,
        "factor": factor("undeclared", flag),
        "constant": constant("undeclared", Boolean()),
        "nonboolean": expression(1),
    }[invalid]
    with pytest.raises((TypeError, ValueError)):
        target((flag,), (f,), constraints=(bad,))


def test_provider_adapter_has_stable_records_and_inferred_empty_exceptional_profile():
    x = attribute("x", Integer(0, 2))
    t = target((x,), (dimension("value", x),))
    spec = object()
    build_profile = coverage_profiles(t, backend="python")
    expected = [{"value": n} for n in range(3)]
    assert build_profile("all", spec=spec) == expected
    assert profile_records(t.for_spec(spec, backend="python"), "all") == expected
    assert build_profile("exceptional", spec=spec) == []
    with pytest.raises(KeyError):
        build_profile("typo", spec=spec)
    with pytest.raises(KeyError):
        build_profile("normal", spec=spec)
    value = dimension("value", x)
    declared = bind(
        coverage_spec(
            "declared_exceptional",
            focus="declared profiles take precedence",
            record="one observation",
            aspects=(aspect("values", value),),
            profiles={"exceptional": exhaustive((value,))},
        ),
        observe_attributes=lambda ctx: ctx.pre,
    )
    assert coverage_profiles(declared, backend="python")("exceptional", spec=spec) == expected


def test_inputs_are_inferred_from_values_availability_applicability_and_constraints():
    x = attribute("x", Integer(0, 2))
    enabled = attribute("enabled", Boolean())
    available = attribute("available", Boolean())
    applicable = attribute("applicable", Boolean())
    offset = constant("offset", Integer(0, 1))
    permitted = constant("permitted", Boolean())
    gate = dimension("gate", enabled)
    value = dimension(
        "value",
        derived("shifted", x + x + offset),
        when=gate,
        available_when=available,
    )
    definition = coverage_spec(
        "inferred",
        focus="input traversal",
        record="one observation",
        aspects=(aspect("values", gate, value),),
        profiles={"all": exhaustive((gate, value))},
        applicable_when=applicable,
        constraints=(permitted,),
    )
    assert [a.name for a in definition.attributes] == ["applicable", "enabled", "x", "available"]
    assert [c.name for c in definition.constants] == ["offset", "permitted"]
    observed = {"x": 1, "enabled": True, "available": True, "applicable": True}
    t = bind(
        definition,
        observe_attributes=lambda ctx: observed,
        constants={"offset": lambda spec: 1, "permitted": lambda spec: True},
    ).for_spec(object(), backend="python")
    assert t.record(t.observation(Context(t._bound_spec, None, None, None, {}))) == {
        "gate": True,
        "value": 3,
    }
    with pytest.raises(ValueError, match="constant bindings"):
        bind(definition, observe_attributes=lambda ctx: observed)


def test_inferred_inputs_preserve_identity_and_reject_name_collisions():
    shared = attribute("shared", Boolean())
    factors = (dimension("first", shared), dimension("second", shared))
    definition = coverage_spec(
        "inferred",
        focus="input identity",
        record="one observation",
        aspects=(aspect("values", *factors),),
        profiles={"all": exhaustive(factors)},
    )
    assert len(definition.attributes) == 1
    assert definition.attributes[0] is shared
    other = attribute("shared", Boolean())
    with pytest.raises(ValueError, match="duplicate input"):
        coverage_spec(
            "conflict",
            focus="input identity",
            record="one observation",
            aspects=(aspect("values", factors[0], dimension("second", other)),),
            profiles={},
        )


@pytest.mark.parametrize("explicit", ["attributes", "constants"])
def test_explicit_input_lists_still_reject_omitted_references(explicit):
    flag = attribute("flag", Boolean())
    limit = constant("limit", Boolean())
    f = dimension("value", flag & limit)
    with pytest.raises(ValueError, match="undeclared input"):
        coverage_spec(
            "explicit",
            focus="explicit input validation",
            record="one observation",
            aspects=(aspect("values", f),),
            profiles={},
            **{explicit: ()},
        )


def materializer_target():
    age = attribute("age", Integer(0, 2))
    ok = attribute("ok", Boolean())
    flag = attribute("flag", Boolean())
    gate = comparison("gate", age, 1, op=">=", granularity="cmp5")
    check = assertion("check", ok, when=gate)
    raw = dimension("raw", flag)
    definition = coverage_spec(
        "materializer",
        focus="generic adaptation",
        record="one vector",
        aspects=(aspect("a", gate, check, raw),),
        profiles={"each": each((gate, check, raw))},
        assertions=assertion_set(check),
    )
    return bind(definition, observe_attributes=lambda ctx: {})


def test_generic_materializer_record_uses_comparison_activation():
    bound = materializer_target().for_spec(object(), backend="python")
    assert materializer_record(bound, {"gate": "LT_1", "raw": False}) == {
        "gate": "LT_1",
        "check": "NA",
        "raw": False,
    }
    assert materializer_record(bound, {"gate": "EQ", "check": False, "raw": True}) == {
        "gate": "EQ",
        "check": False,
        "raw": True,
    }
    assert materializer_record(
        bound,
        {"gate": "GT_1", "check": True, "raw": False},
    ) == {"gate": "GT_1", "check": True, "raw": False}
    # An active missing observation must not be encoded as inactive.
    for record in ({"gate": "EQ", "raw": False}, {"gate": "EQ", "check": NA, "raw": False}):
        with pytest.raises(ValueError, match="missing active dimension: check"):
            materializer_record(bound, record)


def test_provider_profiles_always_complete_unscoped_obligations():
    template = materializer_target()
    spec = object()
    bound = template.for_spec(spec, backend="python")
    records = coverage_profiles(template, backend="python")("each", spec=spec)
    assert records == profile_records(bound, "each")
    configurations = bound._configurations(filtered=True)[1]
    assert all(
        frozenset((k, v) for k, v in r.items() if not k.startswith("_") and v != "NA")
        in configurations
        for r in records
    )
    assert all({"gate", "raw"} <= r.keys() for r in records)
    assert all(bound.assertion_result(r).fault_count is not None for r in records)
    # Coverage requirements retain their projections, independent of witnesses.
    assert frozenset({("raw", False)}) in bound.profiles["each"].run()
    report = score(bound, records, bound.profiles["each"])
    assert report.covered == report.total
    assert not report.unexpected


def test_generic_materializer_profiles_encode_inactive_dimensions():
    template = materializer_target()
    spec = object()
    bound = template.for_spec(spec, backend="python")
    build_profile = coverage_profiles(template, backend="python")
    records = build_profile("each", spec=spec)
    assert all(bound.assertion_result(r).fault_count is not None for r in records)
    assert {r["check"] for r in records} == {"NA", True, False}
    assert all(type(r["raw"]) is bool for r in records)
    report = score(bound, records, bound.profiles["each"])
    assert report.covered == report.total
    assert not report.unexpected
    flag = attribute("flag", Boolean())
    ordinary = target((flag,), (dimension("raw", flag),)).for_spec(object(), backend="python")
    assert materializer_record(ordinary, {"raw": False}) == {
        "raw": False,
    }


def test_generic_materializer_rejects_unknown_fault_count():
    flag = attribute("flag", Boolean())
    parent = dimension("parent", flag)
    child = dimension("child", flag, when=parent)
    check = assertion("check", flag, when=child)
    definition = coverage_spec(
        "unknown",
        focus="unknown assertion activation",
        record="one vector",
        aspects=(aspect("a", parent, child, check),),
        profiles={"each": each((parent, child, check))},
        assertions=assertion_set(check),
    )
    template = bind(definition, observe_attributes=lambda ctx: {})
    with pytest.raises(ValueError, match="unknown assertions"):
        Materializer(object()).claimed_record(template, SimpleNamespace(parent=False))


@pytest.mark.parametrize(
    "provider",
    [
        "eth1_data_reset",
        "slot_processing",
        "historical_summaries_update",
        "randao_mixes_reset",
        "slashings_reset",
        "sync_committee_updates",
        "participation_flag_updates",
        "inactivity_updates",
        "inactivity_updates_loop",
        "justification_and_finalization",
        "registry_updates",
        "rewards_and_penalties",
        "proposer_lookahead",
    ],
)
def test_nonrejecting_declaration_providers_share_the_empty_exceptional_profile(provider):
    module = load_provider(provider)
    assert module.build_profile("exceptional", spec=object()) == []


@pytest.mark.parametrize(
    ("domain", "value"),
    [
        (Integer(0, 4), 2),
        (Boolean(), True),
        (Boolean(), False),
        (Finite(("first", "last")), "last"),
        (Integer(0, 4) | Finite((2**64 - 1,)), 2**64 - 1),
    ],
)
@pytest.mark.parametrize("form", ["direct", "identity", "identity_domain"])
def test_constant_dimensions_refine_to_the_bound_value(domain, value, form):
    k = constant("k", domain)
    value_expression = (
        k if form == "direct" else identity(k, domain=domain if form == "identity_domain" else None)
    )
    d = dimension("constant_value", value_expression)
    template = target((), (d,), constants=(k,), bindings={"k": lambda spec: spec.k})
    t = template.for_spec(SimpleNamespace(k=value), backend="python")
    assert t.profiles["all"].run() == {frozenset({("constant_value", value)})}
    observation = t.observation(Context(t._bound_spec, {}, None, None, {}))
    report = score(t, [t.record(observation)], t.profiles["all"])
    assert report.percent == 100
    assert d.values == (() if d.kind == "boolean" else domain.values())


def test_identity_boolean_domain_supports_predicate_activation():
    flag = attribute("flag", Boolean())
    enabled = dimension("enabled", identity(flag, domain=Boolean()))
    child = dimension("child", identity(~flag, domain=Boolean()), when=enabled)
    t = target((flag,), (enabled, child)).for_spec(object(), backend="python")
    assert t.profiles["all"].run() == {
        frozenset({("enabled", False)}),
        frozenset({("enabled", True), ("child", False)}),
        frozenset({("enabled", True), ("child", True)}),
    }
    for value in (True, False):
        obs = t.observation(Context(t._bound_spec, {"flag": value}, None, None, {}))
        assert t.record(obs) == {"enabled": value, "child": False if value else NA}


def test_constant_expression_dimensions_refine_independently_per_binding():
    k = constant("k", Integer(0, 4))
    d = dimension("next_value", k + 1)
    template = target((), (d,), constants=(k,), bindings={"k": lambda spec: spec.k})
    for value in (0, 2, 4):
        t = template.for_spec(SimpleNamespace(k=value), backend="python")
        assert t.profiles["all"].run() == {frozenset({("next_value", value + 1)})}
    assert d.values == (1, 2, 3, 4, 5)


@pytest.mark.parametrize("size", [512, 1024])
def test_large_finite_membership_and_conjunctions_use_balanced_trees(size):
    x = attribute("x", Integer())
    membership = Finite(range(size)).contains(x)
    conjunction = all_of(*(x >= value for value in range(size)))
    for value in (0, size // 2, size - 1):
        assert membership.evaluate({"x": value}, {}) is True
    for value in (-1, size):
        assert membership.evaluate({"x": value}, {}) is False
    assert conjunction.evaluate({"x": size - 1}, {}) is True
    assert conjunction.evaluate({"x": size - 2}, {}) is False
    # Validation and review traversal must also handle the full-size tree.
    t = target((x,), (factor("member", membership),)).for_spec(object(), backend="python")
    assert "attribute x" in t.review()


@pytest.mark.parametrize("same", [True, False])
def test_bytes_constants_preserve_operands_in_feasibility(same):
    flag = attribute("flag", Boolean())
    f = factor("flag_value", flag)
    left = constant("left", Bytes(32))
    right = constant("right", Bytes(32))
    bindings = {
        "left": lambda spec: b"\x00" * 32,
        "right": lambda spec: (b"\x00" if spec.same else b"\x01") * 32,
    }
    for condition, allowed in ((left == right, same), (left != right, not same)):
        t = target(
            (flag,),
            (f,),
            constants=(left, right),
            bindings=bindings,
            constraints=(condition,),
        ).for_spec(SimpleNamespace(same=same), backend="python")
        assert t.feasible({"flag_value": True}) is allowed
        assert len(t.profiles["all"].run()) == (2 if allowed else 0)


@pytest.mark.parametrize("k_value", [0, 1, 2])
def test_constant_refinement_preserves_lazy_activation_and_nested_dependencies(k_value):
    k = constant("k", Integer(0, 2))
    enabled = dimension("enabled", k > 0)
    remainder = dimension("remainder", expression(1) % k, domain=Integer(0, 1), when=enabled)
    nested = dimension(
        "nested",
        expression(2) % k,
        domain=Integer(0, 1),
        when=remainder == 0,
    )
    template = target(
        (),
        (enabled, remainder, nested),
        constants=(k,),
        bindings={"k": lambda spec: spec.k},
    )
    t = template.for_spec(SimpleNamespace(k=k_value), backend="python")
    observation = t.observation(Context(t._bound_spec, {}, None, None, {}))
    if k_value == 0:
        assert observation == {"enabled": False, "remainder": NA, "nested": NA}
        expected = {"enabled": False}
    elif k_value == 1:
        expected = {"enabled": True, "remainder": 0, "nested": 0}
    else:
        assert observation["nested"] is NA
        expected = {"enabled": True, "remainder": 1}
    assert t.profiles["all"].run() == {frozenset(expected.items())}
    assert score(t, [t.record(observation)], t.profiles["all"]).percent == 100
    assert "target uniform" in t.review()


def test_constant_refinement_defers_unknown_activation_until_observation():
    flag = attribute("flag", Boolean())
    k = constant("k", Integer(0, 1))
    enabled = factor("enabled", flag)
    remainder = dimension("remainder", expression(1) % k, domain=Integer(0, 0), when=enabled)
    t = target(
        (flag,),
        (enabled, remainder),
        constants=(k,),
        bindings={"k": lambda spec: 0},
    ).for_spec(object(), backend="python")
    observation = t.observation(Context(t._bound_spec, {"flag": False}, None, None, {}))
    assert observation["remainder"] is NA
    with pytest.raises(ZeroDivisionError):
        t.observation(Context(t._bound_spec, {"flag": True}, None, None, {}))


def test_constant_refinement_preserves_lazy_availability():
    k = constant("k", Integer(0, 1))
    remainder = dimension(
        "remainder",
        expression(1) % k,
        domain=Integer(0, 0),
        available_when=k > 0,
    )
    t = target((), (remainder,), constants=(k,), bindings={"k": lambda spec: 0}).for_spec(
        object(), backend="python"
    )
    observation = t.observation(Context(t._bound_spec, {}, None, None, {}))
    assert observation["remainder"] is NA
    # Availability still suppresses observation, rather than coverage obligations.
    assert t.profiles["all"].run() == {frozenset({("remainder", 0)})}


@pytest.mark.parametrize("k_value", [0, 1])
def test_constant_refinement_honors_target_applicability(k_value):
    k = constant("k", Integer(0, 1))
    remainder = dimension("remainder", expression(1) % k, domain=Integer(0, 0))
    definition = coverage_spec(
        "applicability",
        focus="constant applicability guard",
        record="one observation",
        attributes=(),
        constants=(k,),
        aspects=(aspect("values", remainder),),
        profiles={"all": exhaustive((remainder,)), "fixed": fix(remainder=0)},
        applicable_when=k > 0,
    )
    t = bind(
        definition,
        observe_attributes=lambda ctx: {},
        constants={"k": lambda spec: spec.k},
    ).for_spec(SimpleNamespace(k=k_value), backend="python")
    observation = t.observation(Context(t._bound_spec, {}, None, None, {}))
    assert observation == {"remainder": NA if k_value == 0 else 0}
    for formula in t.profiles.values():
        assert formula.run() == {frozenset({("remainder", 0)})}
        assert formula.run(filtered=False) == {frozenset({("remainder", 0)})}
    assert "target applicability" in t.review()
    assert t.feasible({"remainder": 0})


def test_constant_refinement_defers_unknown_target_applicability():
    flag = attribute("flag", Boolean())
    k = constant("k", Integer(0, 1))
    remainder = dimension("remainder", expression(1) % k, domain=Integer(0, 0))
    t = target(
        (flag,),
        (remainder,),
        constants=(k,),
        bindings={"k": lambda spec: 0},
        applicable_when=flag,
    ).for_spec(object(), backend="python")
    observation = t.observation(Context(t._bound_spec, {"flag": False}, None, None, {}))
    assert observation["remainder"] is NA
    assert "target uniform" in t.review()
    with pytest.raises(ZeroDivisionError):
        t.observation(Context(t._bound_spec, {"flag": True}, None, None, {}))


def test_known_applicability_still_refines_constant_dimensions():
    flag = attribute("flag", Boolean())
    k = constant("k", Integer(0, 4))
    d = dimension("constant_value", k)
    t = target(
        (flag,),
        (d,),
        constants=(k,),
        bindings={"k": lambda spec: 2},
        applicable_when=(k > 0) | flag,
    ).for_spec(object(), backend="python")
    assert t.profiles["all"].run() == {frozenset({("constant_value", 2)})}


@pytest.mark.parametrize(("gate", "faults"), [("LT_1", 0), ("EQ", 1)])
def test_claimed_record_uses_target_dimensions_activation_and_assertions(gate, faults):
    solution = SimpleNamespace(gate=gate, raw=False, balance=123, _nfaults=99, _rank=99)
    if gate == "EQ":
        solution.check = False
    claimed = Materializer(object()).claimed_record(materializer_target(), solution)
    assert claimed == {
        "gate": gate,
        "raw": False,
        "check": False if gate == "EQ" else "NA",
        "fault_count": faults,
    }
    del solution.raw
    with pytest.raises(ValueError, match="missing active dimension: raw"):
        Materializer(object()).claimed_record(materializer_target(), solution)


def test_claimed_record_without_assertions_omits_fault_metadata():
    flag = attribute("flag", Boolean())
    template = target((flag,), (dimension("raw", flag),))
    assert Materializer(object()).claimed_record(
        template, SimpleNamespace(raw=False, balance=123, _nfaults=99)
    ) == {"raw": False}
