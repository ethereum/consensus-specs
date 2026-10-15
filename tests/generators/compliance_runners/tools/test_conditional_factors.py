from itertools import product

import pytest

from .conditional_factors import Factor, Model


def obligation(**values):
    return frozenset(values.items())


@pytest.fixture(params=["python", "minizinc"])
def backend(request):
    if request.param == "minizinc":
        minizinc = pytest.importorskip("minizinc")
        if minizinc.default_driver is None:
            pytest.skip("MiniZinc executable unavailable")
        try:
            minizinc.Solver.lookup("gecode")
        except LookupError:
            pytest.skip("Gecode unavailable")
    return request.param


def example():
    return Model([Factor("A", (False, True)), Factor("B", (False, True), (("A", True),))])


def test_selected_factor_and_prerequisite(backend):
    model = example()
    assert model.nwise(["B"], 1, backend=backend) == {
        obligation(A=True, B=False),
        obligation(A=True, B=True),
    }
    assert model.nwise(["A"], 1, backend=backend) == {obligation(A=False), obligation(A=True)}


def test_exhaustive_preserves_inactive_branch(backend):
    expected = {obligation(A=False), obligation(A=True, B=False), obligation(A=True, B=True)}
    assert example().exhaustive(["A", "B"], backend=backend) == expected


def test_nested_dependencies_and_unrelated_witnesses(backend):
    model = Model(
        [
            Factor("C", ("x", "y"), (("B", True),)),
            Factor("B", (False, True), (("A", True),)),
            Factor("A", (False, True)),
            Factor("unrelated", (1, 2, 3)),
        ]
    )
    assert model.nwise(["C"], 1, backend=backend) == {
        obligation(A=True, B=True, C="x"),
        obligation(A=True, B=True, C="y"),
    }


def test_exclusive_branches(backend):
    model = Model(
        [
            Factor("A", (False, True)),
            Factor("B", (0, 1), (("A", True),)),
            Factor("C", (2, 3), (("A", False),)),
        ]
    )
    assert model.exhaustive(["B", "C"], backend=backend) == {
        obligation(A=True, B=0),
        obligation(A=True, B=1),
        obligation(A=False, C=2),
        obligation(A=False, C=3),
    }


def test_global_conflicts_prune_projected_obligations(backend):
    model = Model(
        [
            Factor("A", (False, True)),
            Factor("B", (0, 1)),
        ],
        forbidden=[obligation(A=True, B=0), obligation(A=True, B=1)],
    )
    assert model.nwise(["A"], 1, backend=backend) == {obligation(A=False)}


def test_unsatisfiable_and_inactive_conflicts(backend):
    assert (
        Model([Factor("A", (False, True))], [frozenset()]).configurations(backend=backend) == set()
    )
    model = Model(example().factors, [obligation(B=False), obligation(B=True)])
    assert model.exhaustive(["A", "B"], backend=backend) == {obligation(A=False)}


def test_unconditional_pairwise(backend):
    model = Model([Factor(name, (False, True)) for name in "ABC"])
    result = model.nwise("ABC", 2, backend=backend)
    assert len(result) == 12
    assert all(len(o) == 2 for o in result)


def test_backend_agreement_for_all_selections(backend):
    model = Model(
        [
            Factor("A", (False, True)),
            Factor("B", ("one", "many"), (("A", True),)),
            Factor("C", (0, 1), (("A", True), ("B", "many"))),
        ],
        [obligation(C=1)],
    )
    assert model.configurations(backend=backend) == model.configurations()
    for selected in [("A",), ("B",), ("C",), ("A", "C"), ("A", "B", "C")]:
        for strength in range(1, len(selected) + 1):
            assert model.nwise(selected, strength, backend=backend) == model.nwise(
                selected, strength
            )


@pytest.mark.parametrize(
    "factors",
    [
        [],
        [Factor("A", ())],
        [Factor("A", (True, 1))],
        [Factor("A", (True,)), Factor("A", (False,))],
        [Factor("A", (True,), (("unknown", True),))],
        [Factor("A", (True,), (("A", True),))],
        [Factor("A", (True,), (("B", True),)), Factor("B", (True,), (("A", True),))],
    ],
)
def test_invalid_model(factors):
    with pytest.raises(ValueError, match=r"expected|nonempty|duplicate|unknown|cyclic"):
        Model(factors)


@pytest.mark.parametrize(
    ("selected", "strength"), [([], 1), (["missing"], 1), (["A", "A"], 1), (["A"], 0), (["A"], 2)]
)
def test_invalid_request(selected, strength):
    with pytest.raises(ValueError, match=r"select|strength"):
        example().nwise(selected, strength)


def test_export_is_readable_and_uses_safe_identifiers():
    text = Model([Factor("unsafe\nname", ("x", "y"))]).to_minizinc()
    assert '"factor": "unsafe\\nname"' in text
    assert "var 0..2: v_0;" in text
    assert "solve satisfy;" in text


def test_activation_accepts_multiple_parent_values(backend):
    model = Model(
        [
            Factor("A", ("LT", "EQ", "GT")),
            Factor("B", (False, True), allowed=(("A", ("LT", "EQ")),)),
        ]
    )
    assert model.nwise(["B"], 1, backend=backend) == {
        obligation(A=a, B=b) for a in ("LT", "EQ") for b in (False, True)
    }
    assert model.exhaustive(["A", "B"], backend=backend) == {
        obligation(A="GT"),
        *(obligation(A=a, B=b) for a in ("LT", "EQ") for b in (False, True)),
    }


def test_contradictory_activation_preserves_parent_branches(backend):
    model = Model(
        [
            Factor("A", (False, True)),
            Factor("B", (False, True), allowed=(("A", ()),)),
        ]
    )
    assert model.nwise(["B"], 1, backend=backend) == set()
    assert model.exhaustive(["A", "B"], backend=backend) == {
        obligation(A=False),
        obligation(A=True),
    }


def test_complete_projections_cover_obligations_and_omit_inactive_factors(backend):
    model = Model([*example().factors, Factor("C", (0, 1))])
    configurations = model.configurations(backend=backend)
    projected = model.nwise(["A", "B"], 1, backend=backend)
    completed = model.nwise(["A", "B"], 1, backend=backend, complete=True)
    assert completed <= configurations
    assert all(any(o <= c for c in completed) for o in projected)
    assert all("C" in dict(c) and ("B" in dict(c)) == dict(c)["A"] for c in completed)
    assert model.exhaustive(["A"], backend=backend, complete=True) == model.complete(
        model.exhaustive(["A"], backend=backend), configurations
    )


def test_completion_respects_scoped_configurations_and_preference(backend, monkeypatch):
    model = Model([*example().factors, Factor("C", (0, 1))])
    scoped = {c for c in model.configurations(backend=backend) if dict(c)["A"]}

    def forbidden(*args, **kwargs):
        pytest.fail("completion re-enumerated instead of using the supplied scope")

    monkeypatch.setattr(model, "configurations", forbidden)
    obligations = [obligation(A=True), obligation(B=True)]

    def preferred(c):
        return -dict(c)["C"]

    completed = model.complete(obligations, scoped, preference=preferred)
    assert completed == {obligation(A=True, B=False, C=1), obligation(A=True, B=True, C=1)}
    assert (
        model.complete(obligations, sorted(scoped, key=repr, reverse=True), preference=preferred)
        == completed
    )
    with pytest.raises(ValueError, match="no feasible completion"):
        model.complete([obligation(A=False)], scoped)


def test_complete_can_enumerate_its_own_witnesses(backend):
    assert example().complete([obligation(B=True)], backend=backend) == {obligation(A=True, B=True)}


@pytest.mark.parametrize(
    "partial",
    [obligation(A=False, B=True), obligation(A=1), obligation(B=0), obligation(unknown=True)],
)
def test_completion_rejects_infeasible_and_invalid_values(partial):
    with pytest.raises(ValueError, match=r"no feasible completion|unknown factor/value"):
        example().complete([partial])


def test_completion_handles_empty_obligations_and_missing_extensions():
    model = example()
    assert model.complete([]) == set()
    assert model.complete([frozenset()]) == {obligation(A=False)}
    with pytest.raises(ValueError, match="no feasible completion"):
        model.complete([frozenset()], set())


@pytest.mark.parametrize("forbidden", [(), (obligation(A=True, other=False),), (frozenset(),)])
def test_partial_completion_matches_exhaustive_rows(forbidden):
    model = Model(
        [
            Factor("A", (False, True)),
            Factor("B", ("x", "y"), (("A", True),)),
            Factor("other", (False, True)),
        ],
        forbidden=forbidden,
    )
    rows = model.configurations()
    names = tuple(f.name for f in model.factors)
    for values in product((None, False, True), (None, "x", "y"), (None, False, True)):
        fixed = {
            name: value for name, value in zip(names, values, strict=True) if value is not None
        }
        for mask in product((False, True), repeat=len(names)):
            inactive = {name for name, omit in zip(names, mask, strict=True) if omit}
            for with_predicate in (False, True):
                expected = any(
                    fixed.items() <= row
                    and not (inactive & dict(row).keys())
                    and (not with_predicate or dict(row)["other"])
                    for row in rows
                )
                assert (
                    model.has_completion(
                        fixed,
                        inactive=inactive,
                        required=("other",) if with_predicate else (),
                        predicate=(lambda row: row["other"]) if with_predicate else None,
                    )
                    == expected
                )
    assert model._closure(name for name in ("B",)) == {"A", "B"}


def test_completion_ignores_unrelated_cartesian_dimensions(monkeypatch):
    model = Model(
        [
            Factor("A", (False, True)),
            Factor("B", (False, True), (("A", True),)),
            *(Factor(f"unused_{i}", (False, True)) for i in range(40)),
        ]
    )
    monkeypatch.setattr(model, "configurations", lambda **kw: pytest.fail("raw enumeration"))
    assert model.has_completion({"B": True})
    assert not model.has_completion({"B": True}, inactive=("A",))
