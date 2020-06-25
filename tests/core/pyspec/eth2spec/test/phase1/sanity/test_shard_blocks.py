from eth2spec.test.context import (
    PHASE0,
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_all_phases_except,
)
from eth2spec.test.helpers.shard_block import (
    build_shard_block,
    sign_shard_block,
)
from eth2spec.test.helpers.shard_transitions import is_full_crosslink
from eth2spec.test.helpers.state import transition_to_valid_shard_slot


def run_shard_blocks(spec, shard_state, signed_shard_block,
                     beacon_parent_state,
                     validate=True, valid=True):
    pre_shard_state = shard_state.copy()

    yield 'pre', pre_shard_state
    yield 'signed_shard_block', signed_shard_block
    yield 'validate', validate
    yield 'beacon_parent_state', beacon_parent_state

    if not valid:
        expect_assertion_error(lambda: spec.shard_state_transition(
            shard_state, signed_shard_block, validate=validate, beacon_parent_state=beacon_parent_state)
        )
        yield 'post', None
        return

    spec.shard_state_transition(shard_state, signed_shard_block,
                                validate=validate, beacon_parent_state=beacon_parent_state)
    yield 'post', shard_state

    # Verify `process_shard_block`
    block = signed_shard_block.message

    assert shard_state.slot == block.slot

    shard_block_length = len(block.body)
    assert shard_state.gasprice == spec.compute_updated_gasprice(pre_shard_state.gasprice, shard_block_length)
    if shard_block_length != 0:
        shard_state.latest_block_root == block.hash_tree_root()
    else:
        shard_state.latest_block_root == pre_shard_state.latest_block_root


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_valid_shard_block(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    beacon_state = transition_to_valid_shard_slot(spec, state)
    shard = 0
    shard_state = beacon_state.shard_states[shard]
    signed_shard_block = build_shard_block(spec, beacon_state, shard, slot=beacon_state.slot, signed=True)

    yield from run_shard_blocks(spec, shard_state, signed_shard_block, beacon_state)


#
# verify_shard_block_message
#


@with_all_phases_except([PHASE0])
@spec_state_test
def test_invalid_shard_parent_root(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    beacon_state = transition_to_valid_shard_slot(spec, state)
    shard = 0
    shard_state = beacon_state.shard_states[shard]
    signed_shard_block = build_shard_block(spec, beacon_state, shard, slot=beacon_state.slot, signed=True)
    signed_shard_block.message.shard_parent_root = b'\x12' * 32
    sign_shard_block(spec, beacon_state, shard, signed_shard_block)

    yield from run_shard_blocks(spec, shard_state, signed_shard_block, beacon_state, valid=False)


@with_all_phases_except([PHASE0])
@spec_state_test
def test_invalid_beacon_parent_root(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    beacon_state = transition_to_valid_shard_slot(spec, state)
    shard = 0
    shard_state = beacon_state.shard_states[shard]
    signed_shard_block = build_shard_block(spec, beacon_state, shard, slot=beacon_state.slot, signed=True)
    signed_shard_block.message.beacon_parent_root = b'\x12' * 32
    sign_shard_block(spec, beacon_state, shard, signed_shard_block)

    yield from run_shard_blocks(spec, shard_state, signed_shard_block, beacon_state, valid=False)


@with_all_phases_except([PHASE0])
@spec_state_test
def test_invalid_slot(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    beacon_state = transition_to_valid_shard_slot(spec, state)
    shard = 0
    shard_state = beacon_state.shard_states[shard]
    signed_shard_block = build_shard_block(spec, beacon_state, shard, slot=beacon_state.slot, signed=True)
    signed_shard_block.message.slot = beacon_state.slot + 1
    proposer_index = spec.get_shard_proposer_index(beacon_state, signed_shard_block.message.slot, shard)
    sign_shard_block(spec, beacon_state, shard, signed_shard_block, proposer_index=proposer_index)

    yield from run_shard_blocks(spec, shard_state, signed_shard_block, beacon_state, valid=False)


@with_all_phases_except([PHASE0])
@spec_state_test
def test_invalid_proposer_index(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    beacon_state = transition_to_valid_shard_slot(spec, state)
    shard = 0
    shard_state = beacon_state.shard_states[shard]
    signed_shard_block = build_shard_block(spec, beacon_state, shard, slot=beacon_state.slot, signed=True)
    active_validator_indices = spec.get_active_validator_indices(beacon_state, spec.get_current_epoch(beacon_state))
    proposer_index = (
        (spec.get_shard_proposer_index(beacon_state, signed_shard_block.message.slot, shard) + 1)
        % len(active_validator_indices)
    )
    signed_shard_block.message.proposer_index = proposer_index
    sign_shard_block(spec, beacon_state, shard, signed_shard_block, proposer_index=proposer_index)

    yield from run_shard_blocks(spec, shard_state, signed_shard_block, beacon_state, valid=False)


#
# verify_shard_block_signature
#


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_invalid_signature(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    beacon_state = transition_to_valid_shard_slot(spec, state)
    shard = 0
    shard_state = beacon_state.shard_states[shard]
    signed_shard_block = build_shard_block(spec, beacon_state, shard, slot=beacon_state.slot, signed=False)

    yield from run_shard_blocks(spec, shard_state, signed_shard_block, beacon_state, valid=False)
