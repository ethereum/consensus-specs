from eth2spec.test.context import is_post_altair, is_post_bellatrix
from eth2spec.test.helpers.execution_payload import build_empty_execution_payload
from eth2spec.test.helpers.keys import privkeys
from eth2spec.utils import bls
from eth2spec.utils.bls import only_with_bls
from eth2spec.utils.ssz.ssz_impl import hash_tree_root


def get_proposer_index_maybe(spec, state, slot, proposer_index=None):
    if proposer_index is None:
        assert state.slot <= slot
        if slot == state.slot:
            proposer_index = spec.get_beacon_proposer_index(state)
        else:
            if spec.compute_epoch_at_slot(state.slot) + 1 > spec.compute_epoch_at_slot(slot):
                print("warning: block slot far away, and no proposer index manually given."
                      " Signing block is slow due to transition for proposer index calculation.")
            # use stub state to get proposer index of future slot
            stub_state = state.copy()
            if stub_state.slot < slot:
                spec.process_slots(stub_state, slot)
            proposer_index = spec.get_beacon_proposer_index(stub_state)
    return proposer_index


@only_with_bls()
def apply_randao_reveal(spec, state, block, proposer_index=None):
    assert state.slot <= block.slot

    proposer_index = get_proposer_index_maybe(spec, state, block.slot, proposer_index)
    privkey = privkeys[proposer_index]

    domain = spec.get_domain(state, spec.DOMAIN_RANDAO, spec.compute_epoch_at_slot(block.slot))
    signing_root = spec.compute_signing_root(spec.compute_epoch_at_slot(block.slot), domain)
    block.body.randao_reveal = bls.Sign(privkey, signing_root)


# Fully ignore the function if BLS is off, beacon-proposer index calculation is slow.
@only_with_bls()
def apply_sig(spec, state, signed_block, proposer_index=None):
    block = signed_block.message

    proposer_index = get_proposer_index_maybe(spec, state, block.slot, proposer_index)
    privkey = privkeys[proposer_index]
    domain = spec.get_domain(state, spec.DOMAIN_BEACON_PROPOSER, spec.compute_epoch_at_slot(block.slot))
    signing_root = spec.compute_signing_root(block, domain)

    signed_block.signature = bls.Sign(privkey, signing_root)


def sign_block(spec, state, block, proposer_index=None):
    signed_block = spec.SignedBeaconBlock(message=block)
    apply_sig(spec, state, signed_block, proposer_index)
    return signed_block


def transition_unsigned_block(spec, state, block):
    assert state.slot < block.slot  # Preserve assertion from state transition to avoid strange pre-states from testing
    if state.slot < block.slot:
        spec.process_slots(state, block.slot)
    assert state.latest_block_header.slot < block.slot  # There may not already be a block in this slot or past it.
    assert state.slot == block.slot  # The block must be for this slot
    spec.process_block(state, block)
    return block


def apply_empty_block(spec, state, slot=None):
    """
    Transition via an empty block (on current slot, assuming no block has been applied yet).
    """
    block = build_empty_block(spec, state, slot)
    return transition_unsigned_block(spec, state, block)


def build_empty_block(spec, state, slot=None):
    """
    Build empty block for ``slot``, built upon the latest block header seen by ``state``.
    Slot must be greater than or equal to the current slot in ``state``.
    """
    if slot is None:
        slot = state.slot
    if slot < state.slot:
        raise Exception("build_empty_block cannot build blocks for past slots")
    if state.slot < slot:
        # transition forward in copied state to grab relevant data from state
        state = state.copy()
        spec.process_slots(state, slot)

    state, parent_block_root = get_state_and_beacon_parent_root_at_slot(spec, state, slot)
    empty_block = spec.BeaconBlock()
    empty_block.slot = slot
    empty_block.proposer_index = spec.get_beacon_proposer_index(state)
    empty_block.body.eth1_data.deposit_count = state.eth1_deposit_index
    empty_block.parent_root = parent_block_root

    apply_randao_reveal(spec, state, empty_block)

    if is_post_altair(spec):
        empty_block.body.sync_aggregate.sync_committee_signature = spec.G2_POINT_AT_INFINITY

    if is_post_bellatrix(spec):
        empty_block.body.execution_payload = build_empty_execution_payload(spec, state)

    return empty_block


def build_empty_block_for_next_slot(spec, state):
    return build_empty_block(spec, state, state.slot + 1)


def get_state_and_beacon_parent_root_at_slot(spec, state, slot):
    if slot < state.slot:
        raise Exception("Cannot build blocks for past slots")
    if slot > state.slot:
        # transition forward in copied state to grab relevant data from state
        state = state.copy()
        spec.process_slots(state, slot)

    previous_block_header = state.latest_block_header.copy()
    if previous_block_header.state_root == spec.Root():
        previous_block_header.state_root = hash_tree_root(state)
    beacon_parent_root = hash_tree_root(previous_block_header)
    return state, beacon_parent_root
