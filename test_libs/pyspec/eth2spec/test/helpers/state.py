from copy import deepcopy
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.block import sign_block, build_empty_block_for_next_slot


def get_balance(state, index):
    return state.balances[index]


def next_slot(spec, state):
    """
    Transition to the next slot.
    """
    spec.process_slots(state, state.slot + 1)


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


def state_transition_and_sign_block(spec, state, block):
    """
    State transition via the provided ``block``
    then package the block with the state root and signature.
    """
    spec.state_transition(state, block)
    block.state_root = state.hash_tree_root()
    sign_block(spec, state, block)


def next_epoch_with_attestations(spec,
                                 state,
                                 fill_cur_epoch,
                                 fill_prev_epoch):
    assert state.slot % spec.SLOTS_PER_EPOCH == 0

    post_state = deepcopy(state)
    blocks = []
    for _ in range(spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, post_state)
        if fill_cur_epoch and post_state.slot >= spec.MIN_ATTESTATION_INCLUSION_DELAY:
            slot_to_attest = post_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
            committees_per_slot = spec.get_committees_per_slot(state, slot_to_attest)
            if slot_to_attest >= spec.compute_start_slot_of_epoch(spec.get_current_epoch(post_state)):
                for index in range(committees_per_slot):
                    cur_attestation = get_valid_attestation(spec, post_state, slot_to_attest, index=index)
                    block.body.attestations.append(cur_attestation)

        if fill_prev_epoch:
            slot_to_attest = post_state.slot - spec.SLOTS_PER_EPOCH + 1
            committees_per_slot = spec.get_committees_per_slot(state, slot_to_attest)
            for index in range(committees_per_slot):
                prev_attestation = get_valid_attestation(spec, post_state, slot_to_attest, index=index)
                block.body.attestations.append(prev_attestation)

        state_transition_and_sign_block(spec, post_state, block)
        blocks.append(block)

    return state, blocks, post_state
