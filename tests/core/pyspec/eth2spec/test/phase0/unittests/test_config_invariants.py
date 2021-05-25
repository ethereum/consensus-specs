from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
    is_post_altair,
)
from eth2spec.test.helpers.constants import MAX_UINT_64


def check_bound(value, lower_bound, upper_bound):
    assert value >= lower_bound
    assert value <= upper_bound


@with_all_phases
@spec_state_test
def test_validators(spec, state):
    check_bound(spec.VALIDATOR_REGISTRY_LIMIT, 1, MAX_UINT_64)
    check_bound(spec.MAX_COMMITTEES_PER_SLOT, 1, MAX_UINT_64)
    check_bound(spec.TARGET_COMMITTEE_SIZE, 1, MAX_UINT_64)

    check_bound(spec.MAX_VALIDATORS_PER_COMMITTEE, 1, spec.VALIDATOR_REGISTRY_LIMIT)
    check_bound(spec.config.MIN_PER_EPOCH_CHURN_LIMIT, 1, spec.VALIDATOR_REGISTRY_LIMIT)
    check_bound(spec.config.CHURN_LIMIT_QUOTIENT, 1, spec.VALIDATOR_REGISTRY_LIMIT)

    check_bound(spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT, spec.TARGET_COMMITTEE_SIZE, MAX_UINT_64)


@with_all_phases
@spec_state_test
def test_hysteresis_quotient(spec, state):
    check_bound(spec.HYSTERESIS_QUOTIENT, 1, MAX_UINT_64)
    check_bound(spec.HYSTERESIS_DOWNWARD_MULTIPLIER, 1, spec.HYSTERESIS_QUOTIENT)
    check_bound(spec.HYSTERESIS_UPWARD_MULTIPLIER, spec.HYSTERESIS_QUOTIENT, MAX_UINT_64)


@with_all_phases
@spec_state_test
def test_incentives(spec, state):
    # Ensure no ETH is minted in slash_validator
    if is_post_altair(spec):
        assert spec.MIN_SLASHING_PENALTY_QUOTIENT_ALTAIR <= spec.WHISTLEBLOWER_REWARD_QUOTIENT
    else:
        assert spec.MIN_SLASHING_PENALTY_QUOTIENT <= spec.WHISTLEBLOWER_REWARD_QUOTIENT


@with_all_phases
@spec_state_test
def test_time(spec, state):
    assert spec.SLOTS_PER_EPOCH <= spec.SLOTS_PER_HISTORICAL_ROOT


@with_all_phases
@spec_state_test
def test_networking(spec, state):
    assert spec.RANDOM_SUBNETS_PER_VALIDATOR <= spec.ATTESTATION_SUBNET_COUNT
