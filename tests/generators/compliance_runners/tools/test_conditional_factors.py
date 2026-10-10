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
