def validate_constants(spec):
    print("validating constants")
    #
    # Non-zero values
    #

    non_zero_vars = [
        spec.SHARD_COUNT,
        spec.TARGET_COMMITTEE_SIZE,
        spec.MAX_INDICES_PER_ATTESTATION,
        spec.MIN_PER_EPOCH_CHURN_LIMIT,
        spec.CHURN_LIMIT_QUOTIENT,
        spec.BASE_REWARDS_PER_EPOCH,
        spec.MIN_DEPOSIT_AMOUNT,
        spec.MAX_EFFECTIVE_BALANCE,
        spec.EFFECTIVE_BALANCE_INCREMENT,
        spec.MIN_ATTESTATION_INCLUSION_DELAY,
        spec.SLOTS_PER_EPOCH,  # This might need to be greater than 1
        spec.MIN_SEED_LOOKAHEAD,
        spec.ACTIVATION_EXIT_DELAY,  # needs to be greater than min seed lookahead
        spec.SLOTS_PER_ETH1_VOTING_PERIOD,  # needs to be multiple of epoch
        spec.SLOTS_PER_HISTORICAL_ROOT,  # multiple of epoch
        spec.MIN_VALIDATOR_WITHDRAWABILITY_DELAY,  # not sure if this needs to be non-zero but will probably relate to custody
        spec.PERSISTENT_COMMITTEE_PERIOD,
        spec.MAX_EPOCHS_PER_CROSSLINK,  # needs to be greater than 1 to ever catch up. might need to be dynamic
        spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY,  # should probably be greater than 1
        spec.LATEST_RANDAO_MIXES_LENGTH,  # must be greater than seed lookahead
        spec.LATEST_ACTIVE_INDEX_ROOTS_LENGTH,  # must be at least ACTIVATION_EXIT_DELAY because use in `generate_seed`
        spec.LATEST_SLASHED_EXIT_LENGTH,  # this looks like it should be at least 2
        spec.BASE_REWARD_QUOTIENT,
        spec.WHISTLEBLOWING_REWARD_QUOTIENT,
        spec.PROPOSER_REWARD_QUOTIENT,
        spec.INACTIVITY_PENALTY_QUOTIENT,
        spec.MIN_SLASHING_PENALTY_QUOTIENT,
        # most operations need to have at least one for security and functionality but not requisite for chain running
        spec.SECONDS_PER_SLOT
    ]
    for var in non_zero_vars:
        assert var > 0


    # there must be a valid range for deposit amounts
    assert spec.MAX_EFFECTIVE_BALANCE >= spec.MIN_DEPOSIT_AMOUNT

    assert spec.ACTIVATION_EXIT_DELAY >= spec.MIN_SEED_LOOKAHEAD

    assert spec.LATEST_RANDAO_MIXES_LENGTH > spec.MIN_SEED_LOOKAHEAD
    # must have at least 2 mixes around for the previous and current epoch
    assert spec.LATEST_RANDAO_MIXES_LENGTH >= 2

    assert spec.LATEST_ACTIVE_INDEX_ROOTS_LENGTH >= spec.ACTIVATION_EXIT_DELAY

    # because slashed balance is calculated halfway between slashed epoch and `LATEST_SLASHED_EXIT_LENGTH` epochs
    assert spec.LATEST_SLASHED_EXIT_LENGTH >= 2
    print("done validating constants")
