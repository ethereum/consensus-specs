"""Regression checks for abstraction and scoring through explicit declarations."""

from types import SimpleNamespace

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Cmp,
    Context,
    NA,
    score,
)
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    attribute,
    bind,
    Boolean,
    comparison,
    coverage_spec,
    factor,
    Integer,
    nwise,
)


def test_cmp_abstraction_and_truth_at_each_granularity():
    cmp = Cmp("a", op=">=")
    deltas = (-2, -1, 0, 1, 2)
    assert [cmp.abstract(d, "predicate") for d in deltas] == [False, False, True, True, True]
    assert [cmp.abstract(d, "cmp3") for d in deltas] == ["LT", "LT", "EQ", "GT", "GT"]
    assert [cmp.abstract(d, "cmp5") for d in deltas] == ["LT_FAR", "LT_1", "EQ", "GT_1", "GT_FAR"]
    assert cmp.value({}, "cmp5") is NA
    assert cmp.holds("EQ", "cmp3") is True
    assert cmp.holds("LT_1", "cmp5") is False
    assert cmp.far("LT_FAR", "cmp5") is True
    assert cmp.far("LT", "cmp3") is None


def target(*, feasible=lambda a, g: True):
    found, x, flag = (
        attribute("found", Boolean()),
        attribute("x", Integer()),
        attribute("flag", Boolean()),
    )
    a = comparison("a", x, 0, op=">=", available_when=found)
    b = factor("b", flag, available_when=found)
    definition = coverage_spec(
        "test",
        focus="scoring",
        record="one vector",
        attributes=(found, x, flag),
        aspects=(aspect("ab", a, b),),
        profiles={"pairs": nwise((a, b), 2)},
        feasible=feasible,
    )
    return bind(definition, observe_attributes=lambda ctx: ctx.pre).for_spec(SimpleNamespace())


def test_na_never_satisfies_and_scores_are_exact():
    t = target()
    records = []
    for found in (True, False):
        obs = t.observation(
            Context(t._bound_spec, {"found": found, "x": 0, "flag": True}, None, None, {})
        )
        records.append(t.record(obs, "cmp3"))
    report = score(t, records, t.profiles["pairs"], "cmp3")
    assert (report.covered, report.total) == (1, 6)
    assert {"a": "GT", "b": False} in report.uncovered


def test_feasibility_prunes_and_flags_unexpected():
    t = target(feasible=lambda a, g: not (a.get("a") == "LT" and a.get("b") is True))
    report = score(t, [{"a": "LT", "b": True}], t.profiles["pairs"], "cmp3")
    assert (report.covered, report.total) == (0, 5)
    assert report.unexpected == [{"a": "LT", "b": True}]


def test_observation_contains_only_declared_inputs_and_factors():
    t = target()
    obs = t.observation(
        Context(t._bound_spec, {"found": True, "x": 0, "flag": True}, None, object(), {})
    )
    assert obs == {"found": True, "x": 0, "flag": True, "a": 0, "b": True}


def test_declared_outcome_values_are_not_overwritten_by_context():
    present = attribute("post_present", Boolean())
    accepted = factor("accepted", present)
    definition = coverage_spec(
        "explicit_outcome",
        focus="outcome",
        record="one vector",
        attributes=(present,),
        aspects=(aspect("outcome", accepted),),
        profiles={"all": nwise((accepted,), 1)},
    )
    t = bind(definition, observe_attributes=lambda ctx: {"post_present": True}).for_spec(object())
    assert t.observation(Context(t._bound_spec, None, None, None, {})) == {
        "post_present": True,
        "accepted": True,
    }
