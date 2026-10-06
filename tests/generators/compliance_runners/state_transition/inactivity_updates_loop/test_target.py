"""Constant-dependent pruning must match the selected spec and abstraction."""

from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    NA,
    score,
)

from .target import BODY, TARGET


def spec_with(recovery=16, bias=4):
    return SimpleNamespace(
        MIN_EPOCHS_TO_INACTIVITY_PENALTY=4,
        config=SimpleNamespace(INACTIVITY_SCORE_RECOVERY_RATE=recovery, INACTIVITY_SCORE_BIAS=bias),
    )


@pytest.mark.parametrize("configuration_name", ["minimal", "mainnet"])
def test_zero_score_has_exact_recovery_bucket(configuration_name):
    spec = spec_targets[configuration_name]["gloas"]
    target = TARGET.for_spec(spec)
    zero = BODY["score_gt_zero"].abstract(0)
    expected = BODY["score_vs_recovery_rate"].abstract(
        -int(spec.config.INACTIVITY_SCORE_RECOVERY_RATE)
    )
    for profile in ("arithmetic", "standard"):
        obligations = target.profiles[profile].run()
        for bucket in BODY["score_vs_recovery_rate"].domain():
            assignment = frozenset(
                {
                    "is_participating": True,
                    "score_gt_zero": zero,
                    "score_vs_recovery_rate": bucket,
                }.items()
            )
            assert any(assignment <= o for o in obligations) == (bucket == expected)


@pytest.mark.parametrize("configuration_name", ["minimal", "mainnet"])
def test_leak_free_increases_are_not_required(configuration_name):
    target = TARGET.for_spec(spec_targets[configuration_name]["gloas"])
    for profile in ("effects", "standard"):
        obligations = target.profiles[profile].run()
        for bucket in BODY["leaking"].domain():
            assignment = frozenset({"leaking": bucket, "score_delta": "INCREASED"}.items())
            assert (assignment in obligations) == BODY["leaking"].holds(bucket)


@pytest.mark.parametrize("recovery", [0, 1, 16])
def test_recovery_bucket_uses_bound_constant(recovery):
    target = TARGET.for_spec(spec_with(recovery=recovery))
    obligations = target.profiles["arithmetic"].run()
    expected = BODY["score_vs_recovery_rate"].abstract(-recovery)
    assignment = frozenset(
        {
            "is_participating": True,
            "score_gt_zero": BODY["score_gt_zero"].abstract(0),
            "score_vs_recovery_rate": expected,
        }.items()
    )
    assert any(assignment <= o for o in obligations)
    for value in BODY["score_vs_recovery_rate"].domain():
        assert target.feasible(
            {
                "is_participating": True,
                "score_gt_zero": BODY["score_gt_zero"].abstract(0),
                "score_vs_recovery_rate": value,
            }
        ) == (value == expected)


@pytest.mark.parametrize(("recovery", "allowed"), [(1, True), (4, False), (16, False)])
def test_increase_pruning_depends_on_bias_and_recovery(recovery, allowed):
    target = TARGET.for_spec(spec_with(recovery=recovery, bias=4))
    assignment = frozenset({"leaking": "EQ", "score_delta": "INCREASED"}.items())
    assert (assignment in target.profiles["effects"].run()) is allowed
    assert (
        target.feasible({"score_vs_recovery_rate": "GT_FAR", "score_delta": "INCREASED"}) is allowed
    )


def test_binding_is_isolated_and_unbound_scoring_is_rejected():
    low = TARGET.for_spec(spec_with(recovery=1))
    high = TARGET.for_spec(spec_with(recovery=16))
    assignment = {"leaking": "EQ", "score_delta": "INCREASED"}
    assert low.feasible(assignment)
    assert not high.feasible(assignment)
    assert low.feasible(assignment)
    assert TARGET._bound_spec is None
    with pytest.raises(ValueError, match="for_spec"):
        score(TARGET, [], TARGET.profiles["effects"])
    with pytest.raises(ValueError, match="fresh target"):
        low.for_spec(spec_with())
    with pytest.raises(ValueError, match="observation spec differs"):
        low.observation(Context(spec_with(), None, None, None, {}))


def test_pruned_but_observed_outcome_is_still_reported():
    target = TARGET.for_spec(spec_with())
    record = {factor.name: False for factor in target.factors}
    record.update(
        is_participating=False, leaking="EQ", score_delta="INCREASED", score_gt_zero="GT_1"
    )
    report = score(target, [record], target.profiles["effects"])
    assert {"leaking": "EQ", "score_delta": "INCREASED"} in report.unexpected


@pytest.mark.parametrize(
    ("threshold", "bias", "recovery"), [(0, 1, 0), (1, 4, 1), (4, 4, 4), (4, 4, 16)]
)
def test_arithmetic_witnesses_cover_integer_intervals(threshold, bias, recovery):
    from .cases import arithmetic_witnesses  # noqa: PLC0415

    comparisons = (BODY["score_gt_zero"], BODY["leaking"], BODY["score_vs_recovery_rate"])
    witnesses = arithmetic_witnesses(threshold, bias, recovery, comparisons)
    concrete = set()
    for participating in (False, True):
        for initial in range(recovery + bias + 10):
            for delay in range(threshold + 5):
                intermediate = max(0, initial - 1) if participating else initial + bias
                post = intermediate if delay > threshold else max(0, intermediate - recovery)
                record = {
                    "is_participating": participating,
                    "score_gt_zero": comparisons[0].abstract(initial),
                    "leaking": comparisons[1].abstract(delay - threshold),
                    "score_delta": "DECREASED"
                    if post < initial
                    else "INCREASED"
                    if post > initial
                    else "UNCHANGED",
                }
                if delay <= threshold:
                    record["score_vs_recovery_rate"] = comparisons[2].abstract(
                        intermediate - recovery
                    )
                concrete.add(tuple(sorted(record.items())))
    assert set(witnesses) == concrete


def test_cmp5_saturation_and_leak_boundaries_materialize():
    from random import Random  # noqa: PLC0415

    from .materializer import InactivityUpdatesLoopMaterializer  # noqa: PLC0415

    spec = spec_targets["minimal"]["gloas"]
    target = TARGET.for_spec(spec)
    materializer = InactivityUpdatesLoopMaterializer(spec)
    materializer.rng = Random(0)
    for score_bucket in ("EQ", "GT_1", "GT_FAR"):
        for leak_bucket in ("LT_FAR", "LT_1", "EQ", "GT_1", "GT_FAR"):
            solution = SimpleNamespace(
                is_participating=True,
                score_gt_zero=score_bucket,
                leaking=leak_bucket,
            )
            _, parts = materializer.materialize_solution(solution)
            pre = spec.BeaconState.decode_bytes(parts[0][2])
            post = spec.BeaconState.decode_bytes(parts[1][2])
            observation = target.observation(Context(spec, pre, None, post, {}))
            record = target.record(observation)
            assert record["score_gt_zero"] == score_bucket
            assert record["leaking"] == leak_bucket
            assert (
                record["score_vs_recovery_rate"] is NA
                if leak_bucket.startswith("GT")
                else record["score_vs_recovery_rate"] is not NA
            )
            assert observation["post_score"] <= observation["score"]
