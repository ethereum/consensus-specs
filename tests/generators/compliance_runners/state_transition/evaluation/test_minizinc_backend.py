"""Compare the default MiniZinc backend with the explicit Python reference."""

from importlib import import_module
from math import prod

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets

from .coverage_dsl import score, TARGETS
from .declarations import (
    all_of,
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    choose,
    cmp5,
    constant,
    coverage_spec,
    coverage_value,
    dimension,
    each,
    exhaustive,
    Finite,
    fix,
    Integer,
    maximum,
    nwise,
    present,
    union,
)


@pytest.fixture(scope="module")
def minizinc_available():
    minizinc = pytest.importorskip("minizinc")
    if minizinc.default_driver is None:
        pytest.skip("MiniZinc executable unavailable")
    try:
        minizinc.Solver.lookup("gecode")
    except LookupError:
        pytest.skip("Gecode unavailable")
    return minizinc


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
@pytest.mark.parametrize("name", tuple(TARGETS))
def test_existing_target_backend_agreement(minizinc_available, preset, name):
    template = import_module(TARGETS[name]).TARGET
    spec = spec_targets[preset]["gloas"]
    python = template.for_spec(spec, backend="python")
    raw_product = prod(
        len(f.values) for f in python.definition.model(python.bound_constants).factors
    )
    if raw_product > 10_000_000:
        pytest.skip(
            "large native Cartesian space; legacy-space and profile parity tested in provider"
        )
    solver = template.for_spec(spec, backend="minizinc")
    # Includes native constraints, fault scopes, and legacy callback tables.
    for filtered in (False, True):
        assert solver._configurations(filtered)[1] == python._configurations(filtered)[1]
    raw_size = len(python._configurations(filtered=False)[1])
    for profile_name, expected in python.profiles.items():
        actual = solver.profiles[profile_name]
        # Unfiltered large spaces are deliberately expensive reference models.
        filtered_modes = (False, True) if raw_size <= 4096 else (True,)
        for filtered in filtered_modes:
            assert actual.run(filtered=filtered) == expected.run(filtered=filtered)
        assert actual.generation_obligations() == expected.generation_obligations()
        records = [dict(c) for c in actual.generation_obligations()]
        assert actual.covered(records) == expected.covered(records)
        assert actual.covered(records) == actual.run()
        if solver.definition.assertions is not None:
            assert all(
                solver.definition.assertions.agrees(r, solver.bound_constants) for r in records
            )
        # Scoring checks only observed raw projections. Full report parity is
        # checked on smaller spaces, including every
        # operator and scope. Large targets still compare raw configurations,
        # every feasible profile, witnesses, coverage, and observed outcomes.
        if raw_size <= 4096:
            report = score(solver, records, actual)
            assert report.covered == report.total
            assert not report.unexpected
            assert not report.outcome_mismatches


def test_backend_binding_is_explicit():
    template = import_module(TARGETS["eth1_data_reset"]).TARGET
    spec = spec_targets["minimal"]["gloas"]
    python = template.for_spec(spec, backend="python")
    solver = template.for_spec(spec, backend="minizinc")
    assert template.backend == "minizinc"
    assert template.for_spec(spec).backend == "minizinc"
    assert python.backend == "python"
    assert solver.backend == "minizinc"
    assert solver.for_spec(spec) is solver
    assert solver.for_spec(spec, backend="minizinc", solver="gecode") is solver
    with pytest.raises(ValueError, match="different backend or solver"):
        solver.for_spec(spec, backend="python")
    with pytest.raises(ValueError, match="unknown backend"):
        template.for_spec(spec, backend="invalid")


def test_native_constraints_and_formulas_do_not_use_python_evaluation(
    minizinc_available, monkeypatch
):
    flag = attribute("flag", Boolean())
    value = attribute("value", Integer())
    limit = constant("limit", Integer())
    parent = assertion("parent", flag)
    child = assertion("child", cmp5(value, 0, op=">="), when=parent)
    outcome = dimension("accepted", flag)
    assertions = assertion_set(parent, child, observed=outcome, complete=True)
    template = bind(
        coverage_spec(
            "native",
            focus="native translation",
            record="one vector",
            aspects=(aspect("a", parent, child, outcome),),
            constraints=(
                (~parent | child),
                coverage_value(child) != "GT_1",
                choose(parent, maximum(limit, 0) >= 0, no=True),
                parent | ~present(child),
            ),
            assertions=assertions,
            profiles={
                "all": exhaustive((parent, child, outcome)),
                "normal": assertions.normal(each((parent, child))),
                "exceptional": assertions.exceptional(each((parent, child)), faults=1),
                "product": each((parent,)) * each((child,)),
                "union": each((parent,)) | fix(child="EQ"),
                "conflict": fix(parent=False) * fix(child="EQ"),
                "empty": fix(),
            },
        ),
        observe_attributes=lambda ctx: {},
        constants={"limit": lambda spec: 2**64 - 1},
    )
    spec = object()
    python = template.for_spec(spec, backend="python")
    expected_configs = python._configurations(filtered=True)[1]
    expected = {name: formula.run() for name, formula in python.profiles.items()}
    solver = template.for_spec(spec, backend="minizinc")

    # Fail if the optional backend reverts to Python feasibility, projection,
    # formula expansion, or fault-scope filtering.
    def forbidden(*args, **kwargs):
        pytest.fail("Python evaluation used by native MiniZinc compilation")

    monkeypatch.setattr(solver, "feasible", forbidden)
    monkeypatch.setattr(type(solver.profiles["all"]), "_run", forbidden)
    monkeypatch.setattr(type(solver.definition.model()), "project", forbidden)
    monkeypatch.setattr(
        "tests.generators.compliance_runners.state_transition.evaluation.declarations._within_faults",
        forbidden,
    )
    assert solver._configurations(filtered=True)[1] == expected_configs
    for name, formula in solver.profiles.items():
        if name != "conflict":
            assert formula.run() == expected[name]
    assert expected_configs == {
        frozenset({("parent", False), ("accepted", False)}),
        frozenset({("parent", True), ("child", "EQ"), ("accepted", True)}),
        frozenset({("parent", True), ("child", "GT_FAR"), ("accepted", True)}),
    }
    # This intentionally incompatible product has an empty obligation domain.
    # Assert that specific diagnostic rather than ignoring solver warnings.
    with pytest.warns(
        minizinc_available.error.MiniZincWarning,
        match="model inconsistency detected: domain is empty",
    ):
        assert solver.profiles["conflict"].run() == expected["conflict"] == set()


def test_known_false_is_not_hidden_by_inactive_reference(minizinc_available):
    flag = attribute("flag", Boolean())
    parent = dimension("parent", flag)
    child = dimension("child", flag, when=parent)
    template = bind(
        coverage_spec(
            "three_valued",
            focus="inactive conjunction",
            record="one vector",
            aspects=(aspect("a", parent, child),),
            constraints=(all_of(child, parent),),
            profiles={"all": exhaustive((parent, child))},
        ),
        observe_attributes=lambda ctx: {},
    )
    target = template.for_spec(object(), backend="minizinc")
    assert target.profiles["all"].run() == {frozenset({("parent", True), ("child", True)})}


def test_product_uses_independent_leaf_witnesses(minizinc_available):
    flag = attribute("flag", Boolean())
    gate = dimension("gate", flag)
    a = dimension("a", flag)
    b = dimension("b", flag, when=gate)
    template = bind(
        coverage_spec(
            "product",
            focus="short branch merged into longer branch",
            record="one vector",
            aspects=(aspect("a", gate, a, b),),
            profiles={"product": nwise((a, b), 2) * fix(gate=True)},
        ),
        observe_attributes=lambda ctx: {},
    )
    spec = object()
    expected = template.for_spec(spec, backend="python").profiles["product"].run()
    actual = template.for_spec(spec, backend="minizinc").profiles["product"].run()
    assert actual == expected
    # The singleton 'a' leaf came from gate=False, but its merge has a valid
    # gate=True completion. Requiring one shared leaf witness loses this case.
    assert frozenset({("a", True), ("gate", True)}) in actual


@pytest.mark.parametrize("divisor", [-2, 2])
def test_numeric_and_categorical_constraint_expressions(minizinc_available, divisor):
    flag = attribute("flag", Boolean())
    number = attribute("number", Integer(-3, 3))
    label = attribute("label", Finite(("ON", "OFF")))
    parent = dimension("parent", flag)
    numeric = dimension("numeric", number, when=parent)
    category = dimension("category", label)
    template = bind(
        coverage_spec(
            "arithmetic",
            focus="constraint arithmetic",
            record="one vector",
            aspects=(aspect("a", parent, numeric, category),),
            constraints=(
                numeric % divisor == (1 if divisor > 0 else -1),
                numeric + 3 >= 0,
                ~(numeric < -2),
                maximum(numeric - 1, -2) < 3,
                choose(parent, numeric, 0) <= numeric,
                choose(parent, "ON", "OFF") == category,
            ),
            profiles={"all": exhaustive((parent, numeric, category))},
        ),
        observe_attributes=lambda ctx: {},
    )
    spec = object()
    actual = template.for_spec(spec, backend="minizinc")
    assert (
        actual.profiles["all"].run()
        == template.for_spec(spec, backend="python").profiles["all"].run()
    )
    assert actual._configurations(filtered=True)[1] == {
        frozenset({("parent", False), ("category", "OFF")}),
        *(frozenset({("parent", True), ("numeric", n), ("category", "ON")}) for n in (-1, 1, 3)),
    }


def test_exported_scoped_models_are_independently_executable(minizinc_available):
    from .minizinc_backend import _solve, Projection  # noqa: PLC0415 - optional backend

    target = import_module(TARGETS["block_header"]).TARGET.for_spec(
        spec_targets["minimal"]["gloas"], backend="minizinc"
    )
    formula = target.profiles["max"]
    sources = formula.to_minizinc()
    assert len(sources) == 2
    backend = target._solver_backend()
    decoded = set()
    for source in sources:
        configurations = {backend.decode(s) for s in _solve(source["feasibility"], target.solver)}
        projection = Projection(backend.model, configurations)
        decoded.update(
            projection.decode(s.obligation) for s in _solve(source["coverage"], target.solver)
        )
        assert "Formula fault scope" in source["feasibility"]
        assert "Legacy Python witness callbacks" in source["feasibility"]
    assert decoded == formula.run()


def test_unknown_faults_and_missing_outcomes_preserve_scope_semantics(minizinc_available):
    flag = attribute("flag", Boolean())
    gate = dimension("gate", flag)
    parent = dimension("parent", flag, when=gate)
    check = assertion("check", flag, when=parent)
    outcome = dimension("accepted", flag, when=parent)
    assertions = assertion_set(check, observed=outcome, complete=True)
    factors = (gate, parent, check, outcome)
    template = bind(
        coverage_spec(
            "unknown_faults",
            focus="nested inactive assertions and outcomes",
            record="one vector",
            aspects=(aspect("a", *factors),),
            assertions=assertions,
            profiles={
                "normal": assertions.normal(each(factors)),
                "lower_only": assertions.faults(each(factors)),
                "exceptional": assertions.exceptional(each(factors), faults=1),
            },
        ),
        observe_attributes=lambda ctx: {},
    )
    spec = object()
    python = template.for_spec(spec, backend="python")
    solver = template.for_spec(spec, backend="minizinc")
    assert solver._configurations(filtered=True)[1] == python._configurations(filtered=True)[1]
    for name, formula in solver.profiles.items():
        assert formula.run() == python.profiles[name].run()
    unknown = frozenset({("gate", False)})
    backend = solver._solver_backend()
    assert unknown in backend.configurations(scopes=((assertions, 0, None),))
    assert unknown not in backend.configurations(scopes=((assertions, 0, 0),))
    # A known inactive check has no fault, even with an inactive observed outcome.
    assert frozenset({("gate", True), ("parent", False)}) in backend.configurations(
        scopes=((assertions, 0, 0),)
    )


@pytest.mark.parametrize("empty", [False, True])
def test_large_projection_encoding_uses_solved_rows(minizinc_available, monkeypatch, empty):
    # Twenty-one Booleans exceed the mixed-radix Gecode ID range, while the
    # declared constraints leave only two feasible rows (or none).
    flags = tuple(dimension(f"flag_{i}", attribute(f"input_{i}", Boolean())) for i in range(20))
    flags += (dimension("flag_20", attribute("input_20", Boolean()), when=flags[0]),)
    constraints = tuple(flag == flags[0] for flag in flags[1:])
    if empty:
        constraints += (flags[0] & ~flags[0],)
    target = bind(
        coverage_spec(
            "large_projection",
            focus="sparse solved rows with a large raw encoding",
            record="one vector",
            aspects=(aspect("flags", *flags),),
            constraints=constraints,
            profiles={
                "all": exhaustive(flags),
                "conditional": exhaustive((flags[-1],)),
                "pairs": nwise(flags[:3], 2),
                "product": nwise(flags[:3], 2) * fix(flag_0=True),
                "union": union(fix(flag_0=False), fix(flag_1=True)),
                "conflict": fix(flag_0=False) * fix(flag_0=True),
            },
        ),
        observe_attributes=lambda ctx: {},
    ).for_spec(object(), backend="minizinc")
    expected = (
        set()
        if empty
        else {
            frozenset((f.name, value) for f in (flags if value else flags[:-1]))
            for value in (False, True)
        }
    )
    assert target._solver_backend().configurations() == expected
    # Projection must use the supplied solved rows, never enumerate the raw
    # native Cartesian space or an unfiltered MiniZinc space.
    monkeypatch.setattr(target, "_configurations", lambda *a, **kw: pytest.fail("raw enumeration"))
    for name, formula in target.profiles.items():
        if name == "all":
            obligations = expected
        elif name == "conditional":
            obligations = set() if empty else {frozenset((("flag_0", True), ("flag_20", True)))}
        elif name == "pairs":
            obligations = (
                set()
                if empty
                else {
                    frozenset(((flags[i].name, v), (flags[j].name, v)))
                    for i, j in ((0, 1), (0, 2), (1, 2))
                    for v in (False, True)
                }
            )
        elif name == "product":
            obligations = (
                set()
                if empty
                else {
                    frozenset((flags[i].name, True) for i in indices)
                    for indices in ((0, 1), (0, 2), (0, 1, 2))
                }
            )
        elif name == "union":
            obligations = (
                set()
                if empty
                else {
                    frozenset((("flag_0", False),)),
                    frozenset((("flag_1", True),)),
                }
            )
        else:
            obligations = set()
        assert formula.run() == obligations
        assert all(row in expected for row in formula.generation_obligations())
