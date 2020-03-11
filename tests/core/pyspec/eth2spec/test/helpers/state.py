from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.block import sign_block, build_empty_block_for_next_slot, transition_unsigned_block


def get_balance(state, index):
    return state.balances[index]


def next_slot(spec, state):
    """
    Transition to the next slot.
    """
    spec.process_slots(state, state.slot + 1)


def transition_to(spec, state, slot):
    """
    Transition to ``slot``.
    """
    assert state.slot <= slot
    for _ in range(slot - state.slot):
        next_slot(spec, state)
    assert state.slot == slot


def next_epoch(spec, state):
    """
    Transition to the start slot of the next epoch
    """
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    spec.process_slots(state, slot)


def get_state_root(spec, state, slot) -> bytes:
    """
    Return the state root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + spec.SLOTS_PER_HISTORICAL_ROOT
    return state.state_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT]


def state_transition_and_sign_block(spec, state, block, expect_fail=False):
    """
    State transition via the provided ``block``
    then package the block with the correct state root and signature.
    """
    if expect_fail:
        expect_assertion_error(lambda: transition_unsigned_block(spec, state, block))
    else:
        transition_unsigned_block(spec, state, block)
    block.state_root = state.hash_tree_root()
    return sign_block(spec, state, block)


def next_epoch_with_attestations(spec,
                                 state,
                                 fill_cur_epoch,
                                 fill_prev_epoch):
    assert state.slot % spec.SLOTS_PER_EPOCH == 0

    post_state = state.copy()
    signed_blocks = []
    for _ in range(spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, post_state)
        if fill_cur_epoch and post_state.slot >= spec.MIN_ATTESTATION_INCLUSION_DELAY:
            slot_to_attest = post_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
            committees_per_slot = spec.get_committee_count_at_slot(state, slot_to_attest)
            if slot_to_attest >= spec.compute_start_slot_at_epoch(spec.get_current_epoch(post_state)):
                for index in range(committees_per_slot):
                    cur_attestation = get_valid_attestation(spec, post_state, slot_to_attest, index=index, signed=True)
                    block.body.attestations.append(cur_attestation)

        if fill_prev_epoch:
            slot_to_attest = post_state.slot - spec.SLOTS_PER_EPOCH + 1
            committees_per_slot = spec.get_committee_count_at_slot(state, slot_to_attest)
            for index in range(committees_per_slot):
                prev_attestation = get_valid_attestation(spec, post_state, slot_to_attest, index=index, signed=True)
                block.body.attestations.append(prev_attestation)

        signed_block = state_transition_and_sign_block(spec, post_state, block)
        signed_blocks.append(signed_block)

    return state, signed_blocks, post_state
