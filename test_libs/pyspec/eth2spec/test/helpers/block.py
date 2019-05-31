from copy import deepcopy

from eth2spec.phase0 import spec
from eth2spec.phase0.spec import (
    BeaconBlock,
    get_beacon_proposer_index, slot_to_epoch, get_domain,
    process_slots, state_transition,
)
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils.bls import bls_sign, only_with_bls
from eth2spec.utils.minimal_ssz import signing_root, hash_tree_root


# Fully ignore the function if BLS is off, beacon-proposer index calculation is slow.
@only_with_bls()
def sign_block(state, block, proposer_index=None):
    assert state.slot <= block.slot

    if proposer_index is None:
        if block.slot == state.slot:
            proposer_index = get_beacon_proposer_index(state)
        else:
            if slot_to_epoch(state.slot) + 1 > slot_to_epoch(block.slot):
                print("warning: block slot far away, and no proposer index manually given."
                      " Signing block is slow due to transition for proposer index calculation.")
            # use stub state to get proposer index of future slot
            stub_state = deepcopy(state)
            process_slots(stub_state, block.slot)
            proposer_index = get_beacon_proposer_index(stub_state)

    privkey = privkeys[proposer_index]

    block.body.randao_reveal = bls_sign(
        privkey=privkey,
        message_hash=hash_tree_root(slot_to_epoch(block.slot)),
        domain=get_domain(
            state,
            message_epoch=slot_to_epoch(block.slot),
            domain_type=spec.DOMAIN_RANDAO,
        )
    )
    block.signature = bls_sign(
        message_hash=signing_root(block),
        privkey=privkey,
        domain=get_domain(
            state,
            spec.DOMAIN_BEACON_PROPOSER,
            slot_to_epoch(block.slot)))


def apply_empty_block(state):
    """
    Transition via an empty block (on current slot, assuming no block has been applied yet).
    :return: the empty block that triggered the transition.
    """
    block = build_empty_block(state, signed=True)
    state_transition(state, block)
    return block


def build_empty_block(state, slot=None, signed=False):
    if slot is None:
        slot = state.slot
    empty_block = BeaconBlock()
    empty_block.slot = slot
    empty_block.body.eth1_data.deposit_count = state.deposit_index
    previous_block_header = deepcopy(state.latest_block_header)
    if previous_block_header.state_root == spec.ZERO_HASH:
        previous_block_header.state_root = state.hash_tree_root()
    empty_block.parent_root = signing_root(previous_block_header)

    if signed:
        sign_block(state, empty_block)

    return empty_block


def build_empty_block_for_next_slot(state, signed=False):
    return build_empty_block(state, state.slot + 1, signed=signed)
