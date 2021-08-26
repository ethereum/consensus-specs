from eth2spec.test.helpers.constants import (
    ALTAIR, MERGE,
    FORKS_BEFORE_ALTAIR, FORKS_BEFORE_MERGE,
)
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


def create_genesis_state(spec, validator_balances, activation_threshold):
    deposit_root = b'\x42' * 32

    eth1_block_hash = b'\xda' * 32
    previous_version = spec.config.GENESIS_FORK_VERSION
    current_version = spec.config.GENESIS_FORK_VERSION

    if spec.fork == ALTAIR:
        current_version = spec.config.ALTAIR_FORK_VERSION
    elif spec.fork == MERGE:
        previous_version = spec.config.ALTAIR_FORK_VERSION
        current_version = spec.config.MERGE_FORK_VERSION

    state = spec.BeaconState(
        genesis_time=0,
        eth1_deposit_index=len(validator_balances),
        eth1_data=spec.Eth1Data(
            deposit_root=deposit_root,
            deposit_count=len(validator_balances),
            block_hash=eth1_block_hash,
        ),
        fork=spec.Fork(
            previous_version=previous_version,
            current_version=current_version,
            epoch=spec.GENESIS_EPOCH,
        ),
        latest_block_header=spec.BeaconBlockHeader(body_root=spec.hash_tree_root(spec.BeaconBlockBody())),
        randao_mixes=[eth1_block_hash] * spec.EPOCHS_PER_HISTORICAL_VECTOR,
    )

    # We "hack" in the initial validators,
    #  as it is much faster than creating and processing genesis deposits for every single test case.
    state.balances = validator_balances
    state.validators = [build_mock_validator(spec, i, state.balances[i]) for i in range(len(validator_balances))]

    # Process genesis activations
    for validator in state.validators:
        if validator.effective_balance >= activation_threshold:
            validator.activation_eligibility_epoch = spec.GENESIS_EPOCH
            validator.activation_epoch = spec.GENESIS_EPOCH
        if spec.fork not in FORKS_BEFORE_ALTAIR:
            state.previous_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
            state.current_epoch_participation.append(spec.ParticipationFlags(0b0000_0000))
            state.inactivity_scores.append(spec.uint64(0))

    # Set genesis validators root for domain separation and chain versioning
    state.genesis_validators_root = spec.hash_tree_root(state.validators)

    if spec.fork not in FORKS_BEFORE_ALTAIR:
        # Fill in sync committees
        # Note: A duplicate committee is assigned for the current and next committee at genesis
        state.current_sync_committee = spec.get_next_sync_committee(state)
        state.next_sync_committee = spec.get_next_sync_committee(state)

    if spec.fork not in FORKS_BEFORE_MERGE:
        # Initialize the execution payload header (with block number and genesis time set to 0)
        state.latest_execution_payload_header.block_hash = eth1_block_hash
        state.latest_execution_payload_header.random = eth1_block_hash
        state.latest_execution_payload_header.gas_limit = spec.GENESIS_GAS_LIMIT
        state.latest_execution_payload_header.base_fee_per_gas = spec.GENESIS_BASE_FEE_PER_GAS

    return state
