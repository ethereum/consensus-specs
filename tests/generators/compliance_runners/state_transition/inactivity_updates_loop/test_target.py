"""Constant-dependent pruning must match the selected spec and abstraction."""

from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
    Context,
    GRANULARITIES,
    score,
)

from .target import BODY, TARGET


def spec_with(recovery=16, bias=4):
    return SimpleNamespace(
        MIN_EPOCHS_TO_INACTIVITY_PENALTY=4,
        config=SimpleNamespace(INACTIVITY_SCORE_RECOVERY_RATE=recovery, INACTIVITY_SCORE_BIAS=bias),
    )


@pytest.mark.parametrize("configuration_name", ["minimal", "mainnet"])
@pytest.mark.parametrize("granularity", GRANULARITIES)
def test_zero_score_has_exact_recovery_bucket(configuration_name, granularity):
    spec = spec_targets[configuration_name]["gloas"]
    target = TARGET.for_spec(spec)
    zero = BODY["score_gt_zero"].abstract(0, granularity)
    expected = BODY["score_vs_recovery_rate"].abstract(
        -int(spec.config.INACTIVITY_SCORE_RECOVERY_RATE), granularity
    )
    for profile in ("arithmetic", "standard"):
        obligations = target.profiles[profile].run(granularity)
        for bucket in BODY["score_vs_recovery_rate"].domain(granularity):
            assignment = frozenset(
                {
                    "is_participating": True,
                    "score_gt_zero": zero,
                    "score_vs_recovery_rate": bucket,
                }.items()
            )
            assert (assignment in obligations) == (bucket == expected)


@pytest.mark.parametrize("configuration_name", ["minimal", "mainnet"])
@pytest.mark.parametrize("granularity", GRANULARITIES)
def test_leak_free_increases_are_not_required(configuration_name, granularity):
    target = TARGET.for_spec(spec_targets[configuration_name]["gloas"])
    for profile in ("effects", "standard"):
        obligations = target.profiles[profile].run(granularity)
        for bucket in BODY["leaking"].domain(granularity):
            assignment = frozenset({"leaking": bucket, "score_delta": "INCREASED"}.items())
            assert (assignment in obligations) == BODY["leaking"].holds(bucket, granularity)


@pytest.mark.parametrize("recovery", [0, 1, 16])
def test_recovery_bucket_uses_bound_constant(recovery):
    target = TARGET.for_spec(spec_with(recovery=recovery))
    obligations = target.profiles["arithmetic"].run("cmp5")
    expected = BODY["score_vs_recovery_rate"].abstract(-recovery, "cmp5")
    assignment = frozenset(
        {
            "is_participating": True,
            "score_gt_zero": "EQ",
            "score_vs_recovery_rate": expected,
        }.items()
    )
    assert assignment in obligations
    for value in BODY["score_vs_recovery_rate"].domain("cmp5"):
        assert target.feasible(
            {
                "is_participating": True,
                "score_gt_zero": "EQ",
                "score_vs_recovery_rate": value,
            },
            "cmp5",
        ) == (value == expected)


@pytest.mark.parametrize(("recovery", "allowed"), [(1, True), (4, False), (16, False)])
def test_increase_pruning_depends_on_bias_and_recovery(recovery, allowed):
    target = TARGET.for_spec(spec_with(recovery=recovery, bias=4))
    assignment = frozenset({"leaking": False, "score_delta": "INCREASED"}.items())
    assert (assignment in target.profiles["effects"].run("predicate")) is allowed
    assert (
        target.feasible({"score_vs_recovery_rate": True, "score_delta": "INCREASED"}, "predicate")
        is allowed
    )


def test_binding_is_isolated_and_unbound_scoring_is_rejected():
    low = TARGET.for_spec(spec_with(recovery=1))
    high = TARGET.for_spec(spec_with(recovery=16))
    assignment = {"leaking": False, "score_delta": "INCREASED"}
    assert low.feasible(assignment, "predicate")
    assert not high.feasible(assignment, "predicate")
    assert low.feasible(assignment, "predicate")
    assert TARGET._bound_spec is None
    with pytest.raises(ValueError, match="for_spec"):
        score(TARGET, [], TARGET.profiles["effects"], "predicate")
    with pytest.raises(ValueError, match="fresh target"):
        low.for_spec(spec_with())
    with pytest.raises(ValueError, match="observation spec differs"):
        low.observation(Context(spec_with(), None, None, None, {}))


def test_pruned_but_observed_outcome_is_still_reported():
    target = TARGET.for_spec(spec_with())
    record = {factor.name: False for factor in target.factors}
    record.update(
        is_participating=False, leaking=False, score_delta="INCREASED", score_gt_zero=True
    )
    report = score(target, [record], target.profiles["effects"], "predicate")
    assert {"leaking": False, "score_delta": "INCREASED"} in report.unexpected
