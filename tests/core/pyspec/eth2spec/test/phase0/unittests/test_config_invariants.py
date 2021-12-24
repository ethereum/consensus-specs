from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
    is_post_altair, is_post_bellatrix,
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

    # Note: can be less if you assume stricters bounds on validator set based on total ETH supply
    maximum_validators_per_committee = (
        spec.VALIDATOR_REGISTRY_LIMIT
        // spec.SLOTS_PER_EPOCH
        // spec.MAX_COMMITTEES_PER_SLOT
    )
    check_bound(spec.MAX_VALIDATORS_PER_COMMITTEE, 1, maximum_validators_per_committee)
    check_bound(spec.config.MIN_PER_EPOCH_CHURN_LIMIT, 1, spec.VALIDATOR_REGISTRY_LIMIT)
    check_bound(spec.config.CHURN_LIMIT_QUOTIENT, 1, spec.VALIDATOR_REGISTRY_LIMIT)

    check_bound(spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT, spec.TARGET_COMMITTEE_SIZE, MAX_UINT_64)


@with_all_phases
@spec_state_test
def test_balances(spec, state):
    assert spec.MAX_EFFECTIVE_BALANCE % spec.EFFECTIVE_BALANCE_INCREMENT == 0
    check_bound(spec.MIN_DEPOSIT_AMOUNT, 1, MAX_UINT_64)
    check_bound(spec.MAX_EFFECTIVE_BALANCE, spec.MIN_DEPOSIT_AMOUNT, MAX_UINT_64)
    check_bound(spec.MAX_EFFECTIVE_BALANCE, spec.EFFECTIVE_BALANCE_INCREMENT, MAX_UINT_64)


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
    if is_post_bellatrix(spec):
        assert spec.MIN_SLASHING_PENALTY_QUOTIENT_BELLATRIX <= spec.WHISTLEBLOWER_REWARD_QUOTIENT
    elif is_post_altair(spec):
        assert spec.MIN_SLASHING_PENALTY_QUOTIENT_ALTAIR <= spec.WHISTLEBLOWER_REWARD_QUOTIENT
    else:
        assert spec.MIN_SLASHING_PENALTY_QUOTIENT <= spec.WHISTLEBLOWER_REWARD_QUOTIENT


@with_all_phases
@spec_state_test
def test_time(spec, state):
    assert spec.SLOTS_PER_EPOCH <= spec.SLOTS_PER_HISTORICAL_ROOT
    assert spec.MIN_SEED_LOOKAHEAD < spec.MAX_SEED_LOOKAHEAD
    assert spec.SLOTS_PER_HISTORICAL_ROOT % spec.SLOTS_PER_EPOCH == 0
    check_bound(spec.SLOTS_PER_HISTORICAL_ROOT, spec.SLOTS_PER_EPOCH, MAX_UINT_64)
    check_bound(spec.MIN_ATTESTATION_INCLUSION_DELAY, 1, spec.SLOTS_PER_EPOCH)


@with_all_phases
@spec_state_test
def test_networking(spec, state):
    assert spec.RANDOM_SUBNETS_PER_VALIDATOR <= spec.ATTESTATION_SUBNET_COUNT


@with_all_phases
@spec_state_test
def test_fork_choice(spec, state):
    assert spec.INTERVALS_PER_SLOT < spec.config.SECONDS_PER_SLOT
    assert spec.config.PROPOSER_SCORE_BOOST <= 100
