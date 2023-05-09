from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.context import (
    spec_state_test,
    with_eip7002_and_later,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
)


@with_eip7002_and_later
@spec_state_test
def test_basic_exit(spec, state):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = spec.get_current_epoch(state)
    validator_index = spec.get_active_validator_indices(state, current_epoch)[0]
    address = b'\x22' * 20
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, address=address)
    execution_layer_exit = spec.ExecutionLayerExit(
        source_address=address,
        validator_index=validator_index,
    )

    yield 'pre', state

    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.exits = [execution_layer_exit]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH
