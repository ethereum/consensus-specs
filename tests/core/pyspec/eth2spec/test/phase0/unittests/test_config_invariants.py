from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)
from eth2spec.test.helpers.constants import UINT64_MAX
from eth2spec.test.helpers.forks import (
    is_post_altair,
    is_post_bellatrix,
    is_post_electra,
)


def check_bound(value, lower_bound, upper_bound):
    assert value >= lower_bound
    assert value <= upper_bound


@with_all_phases
@spec_state_test
def test_validators(spec, state):
    check_bound(spec.VALIDATOR_REGISTRY_LIMIT, 1, UINT64_MAX)
    check_bound(spec.MAX_COMMITTEES_PER_SLOT, 1, UINT64_MAX)
    check_bound(spec.TARGET_COMMITTEE_SIZE, 1, UINT64_MAX)

    # Note: can be less if you assume stricters bounds on validator set based on total ETH supply
    maximum_validators_per_committee = (
        spec.VALIDATOR_REGISTRY_LIMIT // spec.SLOTS_PER_EPOCH // spec.MAX_COMMITTEES_PER_SLOT
    )
    check_bound(spec.MAX_VALIDATORS_PER_COMMITTEE, 1, maximum_validators_per_committee)
    check_bound(spec.config.MIN_PER_EPOCH_CHURN_LIMIT, 1, spec.VALIDATOR_REGISTRY_LIMIT)
    check_bound(spec.config.CHURN_LIMIT_QUOTIENT, 1, spec.VALIDATOR_REGISTRY_LIMIT)

    check_bound(
        spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT, spec.TARGET_COMMITTEE_SIZE, UINT64_MAX
    )


@with_all_phases
@spec_state_test
def test_balances(spec, state):
    assert spec.MAX_EFFECTIVE_BALANCE % spec.EFFECTIVE_BALANCE_INCREMENT == 0
    check_bound(spec.MIN_DEPOSIT_AMOUNT, 1, UINT64_MAX)
    check_bound(spec.MAX_EFFECTIVE_BALANCE, spec.MIN_DEPOSIT_AMOUNT, UINT64_MAX)
    check_bound(spec.MAX_EFFECTIVE_BALANCE, spec.EFFECTIVE_BALANCE_INCREMENT, UINT64_MAX)


@with_all_phases
@spec_state_test
def test_hysteresis_quotient(spec, state):
    check_bound(spec.HYSTERESIS_QUOTIENT, 1, UINT64_MAX)
    check_bound(spec.HYSTERESIS_DOWNWARD_MULTIPLIER, 1, spec.HYSTERESIS_QUOTIENT)
    check_bound(spec.HYSTERESIS_UPWARD_MULTIPLIER, spec.HYSTERESIS_QUOTIENT, UINT64_MAX)


@with_all_phases
@spec_state_test
def test_incentives(spec, state):
    # Ensure no ETH is minted in slash_validator
    if is_post_bellatrix(spec):
        assert spec.MIN_SLASHING_PENALTY_QUOTIENT_BELLATRIX <= spec.WHISTLEBLOWER_REWARD_QUOTIENT
    elif is_post_altair(spec):
        assert spec.MIN_SLASHING_PENALTY_QUOTIENT_ALTAIR <= spec.WHISTLEBLOWER_REWARD_QUOTIENT
    elif is_post_electra(spec):
        assert (
            spec.MIN_SLASHING_PENALTY_QUOTIENT_ELECTRA <= spec.WHISTLEBLOWER_REWARD_QUOTIENT_ELECTRA
        )
    else:
        assert spec.MIN_SLASHING_PENALTY_QUOTIENT <= spec.WHISTLEBLOWER_REWARD_QUOTIENT


@with_all_phases
@spec_state_test
def test_time(spec, state):
    assert spec.SLOTS_PER_EPOCH <= spec.SLOTS_PER_HISTORICAL_ROOT
    assert spec.MIN_SEED_LOOKAHEAD < spec.MAX_SEED_LOOKAHEAD
    assert spec.SLOTS_PER_HISTORICAL_ROOT % spec.SLOTS_PER_EPOCH == 0
    check_bound(spec.SLOTS_PER_HISTORICAL_ROOT, spec.SLOTS_PER_EPOCH, UINT64_MAX)
    check_bound(spec.MIN_ATTESTATION_INCLUSION_DELAY, 1, spec.SLOTS_PER_EPOCH)


@with_all_phases
@spec_state_test
def test_networking(spec, state):
    assert spec.config.MIN_EPOCHS_FOR_BLOCK_REQUESTS == (
        spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY + spec.config.CHURN_LIMIT_QUOTIENT // 2
    )
    assert spec.config.ATTESTATION_SUBNET_PREFIX_BITS == (
        spec.ceillog2(spec.config.ATTESTATION_SUBNET_COUNT)
        + spec.config.ATTESTATION_SUBNET_EXTRA_BITS
    )
    assert spec.config.SUBNETS_PER_NODE <= spec.config.ATTESTATION_SUBNET_COUNT
    node_id_length = spec.NodeID(1).type_byte_length()  # in bytes
    assert node_id_length * 8 == spec.NODE_ID_BITS  # in bits


@with_all_phases
@spec_state_test
def test_fork_choice(spec, state):
    assert spec.ATTESTATION_DUE_MS < spec.config.SECONDS_PER_SLOT * 1000
    assert spec.AGGREGATE_DUE_MS < spec.config.SECONDS_PER_SLOT * 1000
    assert spec.config.PROPOSER_SCORE_BOOST <= 100
