from copy import deepcopy

from eth2spec.phase0 import spec
from eth2spec.phase0.spec import get_beacon_proposer_index, slot_to_epoch, get_domain, BeaconBlock
from eth2spec.phase0.state_transition import state_transition
from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.state import next_slot
from eth2spec.utils.bls import bls_sign
from eth2spec.utils.minimal_ssz import signing_root, hash_tree_root


def sign_block(state, block):
    assert block.slot == state.slot or block.slot == state.slot + 1
    if block.slot == state.slot:
        proposer_index = get_beacon_proposer_index(state)
    else:
        # use stub state to get proposer index of next slot
        stub_state = deepcopy(state)
        next_slot(stub_state)
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
    return block


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
    empty_block.previous_block_root = signing_root(previous_block_header)

    if signed:
        sign_block(state, empty_block)

    return empty_block


def build_empty_block_for_next_slot(state, signed=False):
    return build_empty_block(state, state.slot + 1, signed=signed)

