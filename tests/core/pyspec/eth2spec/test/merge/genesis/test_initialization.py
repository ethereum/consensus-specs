from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_presets,
    with_merge_and_later,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.deposits import (
    prepare_full_genesis_deposits,
)


def eth1_init_data(eth1_block_hash, eth1_timestamp):
    yield 'eth1', {
        'eth1_block_hash': '0x' + eth1_block_hash.hex(),
        'eth1_timestamp': int(eth1_timestamp),
    }


@with_merge_and_later
@spec_test
@single_phase
@with_presets([MINIMAL], reason="too slow")
def test_initialize_pre_transition_no_param(spec):
    deposit_count = spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, deposit_root, _ = prepare_full_genesis_deposits(
        spec,
        spec.MAX_EFFECTIVE_BALANCE,
        deposit_count,
        signed=True,
    )

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.config.MIN_GENESIS_TIME

    yield from eth1_init_data(eth1_block_hash, eth1_timestamp)
    yield 'deposits', deposits

    # initialize beacon_state *without* an execution_payload_header
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    assert not spec.is_merge_comp(state)

    # yield state
    yield 'state', state


@with_merge_and_later
@spec_test
@single_phase
@with_presets([MINIMAL], reason="too slow")
def test_initialize_pre_transition_empty_payload(spec):
    deposit_count = spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, deposit_root, _ = prepare_full_genesis_deposits(
        spec,
        spec.MAX_EFFECTIVE_BALANCE,
        deposit_count,
        signed=True,
    )

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.config.MIN_GENESIS_TIME

    yield from eth1_init_data(eth1_block_hash, eth1_timestamp)
    yield 'deposits', deposits

    # initialize beacon_state *without* an execution_payload_header
    state = spec.initialize_beacon_state_from_eth1(
        eth1_block_hash,
        eth1_timestamp,
        deposits,
        spec.ExecutionPayloadHeader()
    )

    assert not spec.is_merge_complete(state)

    yield 'execution_payload_header', spec.ExecutionPayloadHeader()

    # yield state
    yield 'state', state


@with_merge_and_later
@spec_test
@single_phase
@with_presets([MINIMAL], reason="too slow")
def test_initialize_post_transition(spec):
    deposit_count = spec.config.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT
    deposits, deposit_root, _ = prepare_full_genesis_deposits(
        spec,
        spec.MAX_EFFECTIVE_BALANCE,
        deposit_count,
        signed=True,
    )

    eth1_block_hash = b'\x12' * 32
    eth1_timestamp = spec.config.MIN_GENESIS_TIME

    yield from eth1_init_data(eth1_block_hash, eth1_timestamp)
    yield 'deposits', deposits

    # initialize beacon_state *with* an execution_payload_header
    genesis_execution_payload_header = spec.ExecutionPayloadHeader(
        parent_hash=b'\x30' * 32,
        coinbase=b'\x42' * 20,
        state_root=b'\x20' * 32,
        receipt_root=b'\x20' * 32,
        logs_bloom=b'\x35' * spec.BYTES_PER_LOGS_BLOOM,
        random=b'\x55' * 32,
        block_number=0,
        gas_limit=30000000,
        base_fee_per_gas=b'\x10' * 32,
        block_hash=b'\x99' * 32,
        transactions_root=spec.Root(b'\x56' * 32),

    )
    state = spec.initialize_beacon_state_from_eth1(
        eth1_block_hash,
        eth1_timestamp,
        deposits,
        genesis_execution_payload_header,
    )

    yield 'execution_payload_header', genesis_execution_payload_header

    assert spec.is_merge_complete(state)

    # yield state
    yield 'state', state
