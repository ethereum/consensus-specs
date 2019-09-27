from eth2spec.test.helpers.keys import pubkeys


def build_mock_validator(spec, i: int, balance: int):
    pubkey = pubkeys[i]
    # insecurely use pubkey as withdrawal key as well
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkey)[1:]
    return spec.Validator(
        pubkey=pubkeys[i],
        withdrawal_credentials=withdrawal_credentials,
        activation_eligibility_epoch=spec.FAR_FUTURE_EPOCH,
        activation_epoch=spec.FAR_FUTURE_EPOCH,
        exit_epoch=spec.FAR_FUTURE_EPOCH,
        withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        effective_balance=min(balance - balance % spec.EFFECTIVE_BALANCE_INCREMENT, spec.MAX_EFFECTIVE_BALANCE)
    )


def create_genesis_state(spec, num_validators, validator_balance):
    deposit_root = b'\x42' * 32

    state = spec.BeaconState(
        genesis_time=0,
        eth1_deposit_index=num_validators,
        eth1_data=spec.Eth1Data(
            deposit_root=deposit_root,
            deposit_count=num_validators,
            block_hash=spec.Hash(),
        ),
        latest_block_header=spec.BeaconBlockHeader(body_root=spec.hash_tree_root(spec.BeaconBlockBody())),
    )

    # We "hack" in the initial validators,
    #  as it is much faster than creating and processing genesis deposits for every single test case.
    state.balances = [validator_balance] * num_validators
    state.validators = [build_mock_validator(spec, i, state.balances[i]) for i in range(num_validators)]

    # Process genesis activations
    for validator in state.validators:
        if validator.effective_balance >= validator_balance:
            validator.activation_eligibility_epoch = spec.GENESIS_EPOCH
            validator.activation_epoch = spec.GENESIS_EPOCH

    return state
