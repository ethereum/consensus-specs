"""Public state-transition generation profile checks."""

from itertools import combinations, product
from types import SimpleNamespace

import pytest

from . import provider as runner
from .aspect_coverage import (
    build_profile,
    MAX_EXCEPTIONAL_INTERACTION_STRENGTH,
    MAX_EXHAUSTIVE_FAULTS,
)
from .provider import materialize_handler, PROFILES


def test_all_is_not_a_generation_profile(tmp_path):
    assert "all" not in PROFILES
    assert "max" in PROFILES
    with pytest.raises(ValueError, match="unknown profile: all"):
        materialize_handler("blocks", "all", tmp_path)


def test_max_keeps_every_normal_signature_and_covers_exceptional_interactions():
    dimensions = ("a", "b", "c", "rare", "outcome")
    aspects = {name: [name] for name in dimensions}
    normal = [dict(zip(dimensions, (0, 0, 0, "LOW", "ACCEPT"), strict=True), _nfaults=0, _rank=0)]
    exceptional = [
        dict(
            zip(
                dimensions,
                (*values, "HIGH" if sum(values) == 3 else "LOW", "REJECT"),
                strict=True,
            ),
            _nfaults=sum(values),
            _rank=sum(values),
        )
        for values in product((0, 1), repeat=3)
        if any(values)
    ]
    chosen = build_profile(normal + exceptional, "max", aspects, aspects, {"outcome": ["outcome"]})
    assert [r for r in chosen if r["_nfaults"] == 0] == normal
    selected_exceptional = [r for r in chosen if r["_nfaults"] > 0]
    mandatory = [r for r in exceptional if r["_nfaults"] <= MAX_EXHAUSTIVE_FAULTS]
    assert selected_exceptional[: len(mandatory)] == mandatory
    for names in combinations(
        dimensions, min(MAX_EXCEPTIONAL_INTERACTION_STRENGTH, len(dimensions))
    ):
        assert {tuple(r[name] for name in names) for r in selected_exceptional} == {
            tuple(r[name] for name in names) for r in exceptional
        }

    # With a fault threshold of at least two and at most pairwise interactions,
    # mandatory cases already cover interactions that do not involve "rare".
    ordinary_aspects = {name: [name] for name in ("a", "b", "c", "outcome")}
    ordinary = build_profile(
        normal + exceptional,
        "max",
        ordinary_aspects,
        ordinary_aspects,
        {"outcome": ["outcome"]},
    )
    if MAX_EXHAUSTIVE_FAULTS >= 2 and MAX_EXCEPTIONAL_INTERACTION_STRENGTH <= 2:
        assert [r for r in ordinary if r["_nfaults"] > 0] == mandatory


@pytest.mark.parametrize("spec_bound", [False, True])
def test_materialization_runner_consumes_case_lists(spec_bound, monkeypatch, tmp_path):
    selected_spec = object()
    cases = [{"value": 1}, {"value": 2}]

    def build(name, *, spec):
        assert name == "smoke"
        assert spec is selected_spec
        return cases

    class Materializer:
        runner_name = "epoch_processing"
        handler_name = "example"
        fork_name = "gloas"

        def __init__(self, spec, **kwargs):
            assert spec is selected_spec
            assert kwargs == {"preset_name": "minimal", "seed": 124}

        def materialize_reps(self, directory, representatives, **kwargs):
            assert directory == tmp_path
            assert [vars(r) for r in representatives] == cases
            assert kwargs == {"case_offset": 7, "clean": False}
            return len(representatives)

    module = SimpleNamespace(
        build_profile=build if spec_bound else lambda name: build(name, spec=selected_spec),
        MATERIALIZER=Materializer,
        validate_case=object(),
    )
    monkeypatch.setattr(runner, "import_module", lambda *args: module)
    provider = runner.Provider("example", "example", "epoch_processing", "example")
    assert runner._materialize_provider(
        provider,
        "smoke",
        tmp_path,
        7,
        clean=False,
        spec=selected_spec,
        preset_name="minimal",
        seed=124,
    ) == (module.validate_case, 2, "gloas")
