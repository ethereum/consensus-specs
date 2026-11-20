"""Aggregate withdrawals retain legacy coverage and realize both preset limits."""

import json
from functools import lru_cache
from hashlib import sha256
from itertools import combinations
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.runner.discovery import gather_tests
from tests.generators.compliance_runners.runner.state_transition import (
    run_test,
)
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    profile_records,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    recover_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    load_observations,
    score,
)
from tests.generators.compliance_runners.state_transition.provider import (
    load_provider,
    materialize_handler,
)

from .materializer import MATERIALIZER
from .target import ASPECTS, TARGET

pending_provider = load_provider("builder_pending_withdrawal_processing")
validate_case = load_provider("withdrawal_processing").validate_case


@lru_cache
def target(preset):
    bound = TARGET.for_spec(spec_targets[preset]["gloas"])
    assert bound.backend == "minizinc"
    return bound


@lru_cache
def records(preset, profile):
    return profile_records(target(preset), profile)


def digest(rows):
    return sha256(
        json.dumps(sorted((tuple(sorted(r.items())) for r in rows), key=repr)).encode()
    ).hexdigest()


def projections(rows, strength):
    return {
        tuple(
            (name, r[name]) for name in sorted({f.name for a in selected for f in a.declarations})
        )
        for selected in combinations(ASPECTS, strength)
        for r in rows
    }


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_exhaustive_legacy_fingerprints(preset):
    # Original withdrawal_processing.mzn signatures, with F/T -> booleans.
    selected = records(preset, "max")
    assert len(selected) == 873
    assert digest(selected) == "12bd766e58da65ed0e68bb285b14ae939f07ac7c7eb82d15d9c6a389ebe659f2"
    for parent, count, expected in (
        (True, 864, "1b82b8e6f36401bff93ce8a98d018393cf8cdd59bd5a9cbade0e60a9e66f2a23"),
        (False, 9, "5bb5d45aa81cce22b442c74b72e50a9fa6729b72bca902f05cd8cf902be7c156"),
    ):
        scoped = [r for r in selected if r["state_latest_block_hash_match"] is parent]
        assert len(scoped) == count
        assert digest(scoped) == expected
    assert all(target(preset).feasible(r) for r in selected)


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_every_legacy_profile_obligation_and_python_reference(preset):
    bound = target(preset)
    reference = TARGET.for_spec(spec_targets[preset]["gloas"], backend="python")
    # Compare reference projection/completion over the independently legacy-
    # validated space, without allocating the millions of raw configurations.
    reference._cache[True] = (
        reference.definition.model(reference.bound_constants),
        bound._configurations(filtered=True)[1],
    )
    for name, strength, count, obligation_count, expected in (
        ("smoke", 1, 40, 44, "4561cbe9bdc5cb96390c9935bb6b5a9dca63e53c8a545faaffc3bca1c94b22fd"),
        (
            "exceptional",
            1,
            40,
            44,
            "4561cbe9bdc5cb96390c9935bb6b5a9dca63e53c8a545faaffc3bca1c94b22fd",
        ),
        ("normal", 2, 267, 393, "b0a712a3960a2f1941854f73aa98eee3a370ba79aa3a2b7eb43ed18e7a160b7f"),
        (
            "standard",
            2,
            267,
            393,
            "b0a712a3960a2f1941854f73aa98eee3a370ba79aa3a2b7eb43ed18e7a160b7f",
        ),
    ):
        selected = records(preset, name)
        assert len(selected) == count
        observed = projections(selected, strength)
        assert len(observed) == obligation_count
        assert sha256(json.dumps(sorted(observed, key=repr)).encode()).hexdigest() == expected
    for name, formula in bound.profiles.items():
        assert formula.run() == reference.profiles[name].run()
        assert formula.generation_obligations() == reference.profiles[name].generation_obligations()
        result = score(bound, records(preset, name), formula, name)
        assert result.covered == result.total
        assert not result.unexpected


@lru_cache
def materializer(preset):
    m = MATERIALIZER(spec_targets[preset]["gloas"], preset_name=preset, seed=124)
    m.test_provider = "withdrawal_processing"
    return m


def vector(preset, record):
    m = materializer(preset)
    solution = SimpleNamespace(**record)
    m.rng = m._rng_for_solution(solution)
    metadata, parts = m.materialize_solution(solution)
    encoded = {name: data for name, _, data in parts}
    return metadata, Context(
        m.spec,
        m.spec.BeaconState.decode_bytes(encoded["pre"]),
        None,
        m.spec.BeaconState.decode_bytes(encoded["post"]),
        {},
    )


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_vectors_independently_recover_and_replay(preset):
    # Minimal covers the complete space. Mainnet covers all standard pairs;
    # these use real 16,384-position sweep boundaries, not minimal constants.
    selected = records(preset, "max" if preset == "minimal" else "standard")
    for record in selected:
        metadata, ctx = vector(preset, record)
        assert recover_record(TARGET, ctx)[2] == metadata["claimed"] == record
        expected = ctx.pre.copy()
        ctx.spec.process_withdrawals(expected)
        assert expected == ctx.post
        if not record["state_latest_block_hash_match"]:
            assert ctx.pre == ctx.post


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_partial_source_reserves_its_capacity_before_builder_sweep(preset):
    record = next(
        r
        for r in records(preset, "max")
        if r["builder_pending_withdrawals_exist"]
        and not r["builder_pending_withdrawals_hit_limit"]
        and r["validator_pending_withdrawals_hit_limit"]
        and r["cmp_eligible_builder_count_zero"] == "GT"
        and r["cmp_builder_count_max_per_sweep"] == "GT"
    )
    _, ctx = vector(preset, record)
    expected = ctx.spec.get_expected_withdrawals(ctx.pre)
    limit = int(ctx.spec.MAX_WITHDRAWALS_PER_PAYLOAD) - 1
    partials = int(ctx.spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP)
    assert expected.processed_builder_withdrawals_count == limit - partials
    assert expected.processed_partial_withdrawals_count == partials
    assert (
        sum(not ctx.spec.is_builder_index(w.validator_index) for w in expected.withdrawals[:limit])
        == partials
    )
    assert record["cmp_swept_count_zero"] == "EQ"
    assert recover_record(TARGET, ctx)[2] == record


@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_shared_smoke_pipeline_separates_providers_and_requires_post(preset, tmp_path):
    pending = pending_provider.build_profile("smoke", spec=spec_targets[preset]["gloas"])
    aggregate = records(preset, "smoke")
    assert materialize_handler("withdrawals", "smoke", tmp_path, preset_name=preset, seed=7) == len(
        pending
    ) + len(aggregate)
    for template, count in ((TARGET, len(aggregate)), (pending_provider.TARGET, len(pending))):
        bound = template.for_spec(spec_targets[preset]["gloas"])
        observations = load_observations([tmp_path], bound, preset)
        assert len(observations) == count
        result = score(
            bound, [bound.record(o) for o in observations], bound.profiles["smoke"], "smoke"
        )
        assert result.covered == result.total
        assert not result.unexpected
    yaml = YAML()
    aggregate_case = None
    for case in gather_tests(tmp_path):
        run_test(case)
        metadata = yaml.load((case.test_dir / "dimensions.yaml").read_text())
        if metadata["test_provider"] == "withdrawal_processing":
            aggregate_case = case.test_dir
    spec = spec_targets[preset]["gloas"]
    assert all(c.status == "ok" for c in validate_case.for_spec(spec, aggregate_case))
    metadata_path = aggregate_case / "dimensions.yaml"
    metadata = yaml.load(metadata_path.read_text())
    metadata["claimed"]["state_latest_block_hash_match"] = not metadata["claimed"][
        "state_latest_block_hash_match"
    ]
    with metadata_path.open("w") as stream:
        yaml.dump(metadata, stream)
    assert any(
        c.status == "mismatch" and c.dimension == "state_latest_block_hash_match"
        for c in validate_case.for_spec(spec, aggregate_case)
    )
    (aggregate_case / "post.ssz_snappy").unlink()
    assert any(
        c.status == "mismatch" and c.dimension == "post_state_present"
        for c in validate_case.for_spec(spec, aggregate_case)
    )
