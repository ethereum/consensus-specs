from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.context import (
    spec_state_test,
    with_eip7002_and_later,
)
from eth2spec.test.helpers.bls_to_execution_changes import (
    get_signed_address_change,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.voluntary_exits import (
    prepare_signed_exits,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
)


@with_eip7002_and_later
@spec_state_test
def test_basic_el_exit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield 'pre', state

    validator_index = 0
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    validator_pubkey = state.validators[validator_index].pubkey
    execution_layer_exit = spec.ExecutionLayerExit(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.exits = [execution_layer_exit]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_eip7002_and_later
@spec_state_test
def test_basic_btec_and_el_exit_in_same_block(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield 'pre', state
    validator_index = 0
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    block = build_empty_block_for_next_slot(spec, state)

    address = b'\x22' * 20
    signed_address_change = get_signed_address_change(
        spec,
        state,
        validator_index=validator_index,
        to_execution_address=address,
    )
    block.body.bls_to_execution_changes = [signed_address_change]

    validator_pubkey = state.validators[validator_index].pubkey
    execution_layer_exit = spec.ExecutionLayerExit(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block.body.execution_payload.exits = [execution_layer_exit]

    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    # BTEC is executed after EL-Exit, so it doesn't take effect. `initiate_validator_exit` is not called.
    validator = state.validators[validator_index]
    assert validator.exit_epoch == spec.FAR_FUTURE_EPOCH
    # Check if BTEC is effect
    is_execution_address = validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    is_correct_source_address = validator.withdrawal_credentials[12:] == address
    assert is_execution_address and is_correct_source_address


@with_eip7002_and_later
@spec_state_test
def test_basic_btec_before_el_exit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield 'pre', state

    validator_index = 0
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # block_1 contains a BTEC operation of the given validator
    address = b'\x22' * 20
    signed_address_change = get_signed_address_change(
        spec,
        state,
        validator_index=validator_index,
        to_execution_address=address,
    )
    block_1 = build_empty_block_for_next_slot(spec, state)
    block_1.body.bls_to_execution_changes = [signed_address_change]
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    validator = state.validators[validator_index]
    assert validator.exit_epoch == spec.FAR_FUTURE_EPOCH
    # Check if BTEC is effect
    is_execution_address = validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    is_correct_source_address = validator.withdrawal_credentials[12:] == address
    assert is_execution_address and is_correct_source_address

    # block_2 contains an EL-Exit operation of the given validator
    validator_pubkey = state.validators[validator_index].pubkey
    execution_layer_exit = spec.ExecutionLayerExit(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block_2 = build_empty_block_for_next_slot(spec, state)
    block_2.body.execution_payload.exits = [execution_layer_exit]
    block_2.body.execution_payload.block_hash = compute_el_block_hash(spec, block_2.body.execution_payload)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield 'blocks', [signed_block_1, signed_block_2]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@with_eip7002_and_later
@spec_state_test
def test_cl_exit_and_el_exit_in_same_block(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield 'pre', state

    validator_index = 0
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # CL-Exit
    signed_voluntary_exits = prepare_signed_exits(spec, state, indices=[validator_index])
    # EL-Exit
    validator_pubkey = state.validators[validator_index].pubkey
    execution_layer_exit = spec.ExecutionLayerExit(
        source_address=address,
        validator_pubkey=validator_pubkey,
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.voluntary_exits = signed_voluntary_exits
    block.body.execution_payload.exits = [execution_layer_exit]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH
