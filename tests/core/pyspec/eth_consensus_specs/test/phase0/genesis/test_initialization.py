from eth_consensus_specs.test.context import (
    PHASE0,
    single_phase,
    spec_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.deposits import (
    prepare_full_genesis_deposits,
    prepare_random_genesis_deposits,
)
from eth_consensus_specs.test.helpers.forks import (
    is_post_altair,
    is_post_electra,
)


def get_post_altair_description(spec):
    return f"Although it's not phase 0, we may use {spec.fork} spec to start testnets."


def eth1_init_data(eth1_block_hash, eth1_timestamp):
    yield (
        "eth1",
        {
            "eth1_block_hash": "0x" + eth1_block_hash.hex(),
            "eth1_timestamp": int(eth1_timestamp),
        },
    )


@with_phases([PHASE0])
@spec_test
@single_phase
@with_presets([MINIMAL], reason="too slow")
def test_initialize_beacon_state_from_eth1(spec):
    if is_post_altair(spec):
        yield "description", "meta", get_post_altair_description(spec)

    deposit_count = spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, deposit_root, _ = prepare_full_genesis_deposits(
        spec,
        spec.MAX_EFFECTIVE_BALANCE,
        deposit_count,
        signed=True,
    )

    eth1_block_hash = b"\x12" * 32
    eth1_timestamp = spec.config.MIN_GENESIS_TIME

    yield from eth1_init_data(eth1_block_hash, eth1_timestamp)
    yield "deposits", deposits

    # initialize beacon_state
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    assert state.genesis_time == eth1_timestamp + spec.config.GENESIS_DELAY
    assert len(state.validators) == deposit_count
    assert state.eth1_data.deposit_root == deposit_root
    assert state.eth1_data.deposit_count == deposit_count
    assert state.eth1_data.block_hash == eth1_block_hash
    assert spec.get_total_active_balance(state) == deposit_count * spec.MAX_EFFECTIVE_BALANCE

    # yield state
    yield "state", state


@with_phases([PHASE0])
@spec_test
@single_phase
@with_presets([MINIMAL], reason="too slow")
def test_initialize_beacon_state_some_small_balances(spec):
    if is_post_altair(spec):
        yield "description", "meta", get_post_altair_description(spec)

    if is_post_electra(spec):
        max_effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    else:
        max_effective_balance = spec.MAX_EFFECTIVE_BALANCE

    main_deposit_count = spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    main_deposits, _, deposit_data_list = prepare_full_genesis_deposits(
        spec,
        max_effective_balance,
        deposit_count=main_deposit_count,
        signed=True,
    )
    # For deposits above, and for another deposit_count, add a balance of EFFECTIVE_BALANCE_INCREMENT
    small_deposit_count = main_deposit_count * 2
    small_deposits, deposit_root, _ = prepare_full_genesis_deposits(
        spec,
        spec.MIN_DEPOSIT_AMOUNT,
        deposit_count=small_deposit_count,
        signed=True,
        deposit_data_list=deposit_data_list,
    )
    deposits = main_deposits + small_deposits

    eth1_block_hash = b"\x12" * 32
    eth1_timestamp = spec.config.MIN_GENESIS_TIME

    yield from eth1_init_data(eth1_block_hash, eth1_timestamp)
    yield "deposits", deposits

    # initialize beacon_state
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    assert state.genesis_time == eth1_timestamp + spec.config.GENESIS_DELAY
    assert len(state.validators) == small_deposit_count
    assert state.eth1_data.deposit_root == deposit_root
    assert state.eth1_data.deposit_count == len(deposits)
    assert state.eth1_data.block_hash == eth1_block_hash
    # only main deposits participate to the active balance
    # NOTE: they are pre-ELECTRA deposits with BLS_WITHDRAWAL_PREFIX,
    # so `MAX_EFFECTIVE_BALANCE` is used
    assert spec.get_total_active_balance(state) == main_deposit_count * spec.MAX_EFFECTIVE_BALANCE

    # yield state
    yield "state", state


@with_phases([PHASE0])
@spec_test
@single_phase
@with_presets([MINIMAL], reason="too slow")
def test_initialize_beacon_state_one_topup_activation(spec):
    if is_post_altair(spec):
        yield "description", "meta", get_post_altair_description(spec)

    # Submit all but one deposit as MAX_EFFECTIVE_BALANCE
    main_deposit_count = spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT - 1
    main_deposits, _, deposit_data_list = prepare_full_genesis_deposits(
        spec,
        spec.MAX_EFFECTIVE_BALANCE,
        deposit_count=main_deposit_count,
        signed=True,
    )

    # Submit last pubkey deposit as MAX_EFFECTIVE_BALANCE - MIN_DEPOSIT_AMOUNT
    partial_deposits, _, deposit_data_list = prepare_full_genesis_deposits(
        spec,
        spec.MAX_EFFECTIVE_BALANCE - spec.MIN_DEPOSIT_AMOUNT,
        deposit_count=1,
        min_pubkey_index=main_deposit_count,
        signed=True,
        deposit_data_list=deposit_data_list,
    )

    # Top up thelast pubkey deposit as MIN_DEPOSIT_AMOUNT to complete the deposit
    top_up_deposits, _, _ = prepare_full_genesis_deposits(
        spec,
        spec.MIN_DEPOSIT_AMOUNT,
        deposit_count=1,
        min_pubkey_index=main_deposit_count,
        signed=True,
        deposit_data_list=deposit_data_list,
    )

    deposits = main_deposits + partial_deposits + top_up_deposits

    eth1_block_hash = b"\x13" * 32
    eth1_timestamp = spec.config.MIN_GENESIS_TIME

    yield from eth1_init_data(eth1_block_hash, eth1_timestamp)
    yield "deposits", deposits

    # initialize beacon_state
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)
    assert spec.is_valid_genesis_state(state)

    # yield state
    yield "state", state


@with_phases([PHASE0])
@spec_test
@single_phase
@with_presets([MINIMAL], reason="too slow")
def test_initialize_beacon_state_random_invalid_genesis(spec):
    if is_post_altair(spec):
        yield "description", "meta", get_post_altair_description(spec)

    # Make a bunch of random deposits
    deposits, _, deposit_data_list = prepare_random_genesis_deposits(
        spec,
        deposit_count=20,
        max_pubkey_index=10,
    )
    eth1_block_hash = b"\x14" * 32
    eth1_timestamp = spec.config.MIN_GENESIS_TIME + 1

    yield from eth1_init_data(eth1_block_hash, eth1_timestamp)
    yield "deposits", deposits

    # initialize beacon_state
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)
    assert not spec.is_valid_genesis_state(state)

    yield "state", state


@with_phases([PHASE0])
@spec_test
@single_phase
@with_presets([MINIMAL], reason="too slow")
def test_initialize_beacon_state_random_valid_genesis(spec):
    if is_post_altair(spec):
        yield "description", "meta", get_post_altair_description(spec)

    # Make a bunch of random deposits
    random_deposits, _, deposit_data_list = prepare_random_genesis_deposits(
        spec,
        deposit_count=20,
        min_pubkey_index=spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT - 5,
        max_pubkey_index=spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT + 5,
    )

    # Then make spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT full deposits
    full_deposits, _, _ = prepare_full_genesis_deposits(
        spec,
        spec.MAX_EFFECTIVE_BALANCE,
        deposit_count=spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT,
        signed=True,
        deposit_data_list=deposit_data_list,
    )

    deposits = random_deposits + full_deposits
    eth1_block_hash = b"\x15" * 32
    eth1_timestamp = spec.config.MIN_GENESIS_TIME + 2

    yield from eth1_init_data(eth1_block_hash, eth1_timestamp)
    yield "deposits", deposits

    # initialize beacon_state
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)
    assert spec.is_valid_genesis_state(state)

    yield "state", state
