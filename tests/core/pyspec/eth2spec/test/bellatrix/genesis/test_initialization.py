from eth2spec.test.context import (
    BELLATRIX,
    single_phase,
    spec_test,
    with_presets,
    with_phases,
    with_bellatrix_and_later,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.deposits import (
    prepare_full_genesis_deposits,
)
from eth2spec.test.helpers.genesis import (
    get_sample_genesis_execution_payload_header,
)


def eth1_init_data(eth1_block_hash, eth1_timestamp):
    yield 'eth1', {
        'eth1_block_hash': '0x' + eth1_block_hash.hex(),
        'eth1_timestamp': int(eth1_timestamp),
    }


@with_phases([BELLATRIX])
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
    yield 'execution_payload_header', 'meta', False
    state = spec.initialize_beacon_state_from_eth1(eth1_block_hash, eth1_timestamp, deposits)

    assert not spec.is_merge_transition_complete(state)

    yield 'state', state


@with_bellatrix_and_later
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

    # initialize beacon_state *with* an *empty* execution_payload_header
    yield 'execution_payload_header', 'meta', True
    execution_payload_header = spec.ExecutionPayloadHeader()
    state = spec.initialize_beacon_state_from_eth1(
        eth1_block_hash,
        eth1_timestamp,
        deposits,
        execution_payload_header=execution_payload_header,
    )

    assert not spec.is_merge_transition_complete(state)

    yield 'execution_payload_header', execution_payload_header

    yield 'state', state


@with_bellatrix_and_later
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
    yield 'execution_payload_header', 'meta', True
    genesis_execution_payload_header = get_sample_genesis_execution_payload_header(spec)
    state = spec.initialize_beacon_state_from_eth1(
        eth1_block_hash,
        eth1_timestamp,
        deposits,
        execution_payload_header=genesis_execution_payload_header,
    )

    yield 'execution_payload_header', genesis_execution_payload_header

    assert spec.is_merge_transition_complete(state)

    yield 'state', state
