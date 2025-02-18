from eth2spec.test.helpers.execution_payload import build_empty_execution_payload
from eth2spec.test.helpers.execution_payload import build_empty_signed_execution_payload_header
from eth2spec.test.helpers.forks import is_post_eip7441, is_post_altair, is_post_bellatrix, is_post_eip7732, \
    is_post_electra
from eth2spec.test.helpers.keys import privkeys, whisk_ks_initial, whisk_ks_final
from eth2spec.utils import bls
from eth2spec.utils.bls import only_with_bls
from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from curdleproofs import (
    GenerateWhiskTrackerProof,
    WhiskTracker,
    GenerateWhiskShuffleProof,
)
from py_ecc.optimized_bls12_381.optimized_curve import G1, multiply
from py_ecc.typing import Optimized_Field, Optimized_Point3D
from py_ecc.bls.g2_primitives import (
    G1_to_pubkey as py_ecc_G1_to_bytes48,
    pubkey_to_G1 as py_ecc_bytes48_to_G1,
)
from eth2spec.test.helpers.eip7441 import (
    compute_whisk_tracker_and_commitment,
    is_first_proposal,
    resolve_known_tracker
)
from py_arkworks_bls12381 import Scalar

PointProjective = Optimized_Point3D[Optimized_Field]


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
def apply_randao_reveal(spec, state, block, proposer_index):
    assert state.slot <= block.slot

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


def build_empty_block(spec, state, slot=None, proposer_index=None):
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
    proposer_index = get_beacon_proposer_to_build(spec, state, proposer_index)
    empty_block = spec.BeaconBlock()
    empty_block.slot = slot
    empty_block.proposer_index = proposer_index
    empty_block.body.eth1_data.deposit_count = state.eth1_deposit_index
    empty_block.parent_root = parent_block_root

    apply_randao_reveal(spec, state, empty_block, proposer_index)

    if is_post_altair(spec):
        empty_block.body.sync_aggregate.sync_committee_signature = spec.G2_POINT_AT_INFINITY

    if is_post_eip7732(spec):
        signed_header = build_empty_signed_execution_payload_header(spec, state)
        empty_block.body.signed_execution_payload_header = signed_header
        return empty_block

    if is_post_bellatrix(spec):
        empty_block.body.execution_payload = build_empty_execution_payload(spec, state)

    if is_post_electra(spec):
        empty_block.body.execution_requests.deposits = []
        empty_block.body.execution_requests.withdrawals = []
        empty_block.body.execution_requests.consolidations = []

    if is_post_eip7441(spec):
        # Whisk opening proof
        #######

        # Create valid whisk opening proof
        # TODO: Use k_initial or k_final to handle first and subsequent proposals
        k_initial = whisk_ks_initial(proposer_index)

        # Sanity check proposer is correct
        proposer_k_commitment = state.whisk_k_commitments[proposer_index]
        k_commitment = py_ecc_G1_to_bytes48(multiply(G1, int(k_initial)))
        if proposer_k_commitment != k_commitment:
            raise Exception("k proposer_index not eq proposer_k_commitment", proposer_k_commitment, k_commitment)

        proposer_tracker = state.whisk_proposer_trackers[state.slot % spec.PROPOSER_TRACKERS_COUNT]
        if not is_whisk_proposer(proposer_tracker, k_initial):
            raise Exception("k proposer_index does not match proposer_tracker")

        empty_block.body.whisk_opening_proof = GenerateWhiskTrackerProof(proposer_tracker, Scalar(k_initial))

        # Whisk shuffle proof
        #######

        shuffle_indices = spec.get_shuffle_indices(empty_block.body.randao_reveal)
        pre_shuffle_trackers = [state.whisk_candidate_trackers[i] for i in shuffle_indices]

        post_trackers, shuffle_proof = GenerateWhiskShuffleProof(spec.CURDLEPROOFS_CRS, pre_shuffle_trackers)
        empty_block.body.whisk_post_shuffle_trackers = post_trackers
        empty_block.body.whisk_shuffle_proof = shuffle_proof

        # Whisk registration proof
        #######

        # Branching logic depending if first proposal or not
        if is_first_proposal(spec, state, proposer_index):
            # Register new tracker
            k_final = whisk_ks_final(proposer_index)
            # TODO: Actual logic should pick a random r, but may need to do something fancy to locate trackers quickly
            r = 2
            tracker, k_commitment = compute_whisk_tracker_and_commitment(k_final, r)
            empty_block.body.whisk_registration_proof = GenerateWhiskTrackerProof(tracker, Scalar(k_final))
            empty_block.body.whisk_tracker = tracker
            empty_block.body.whisk_k_commitment = k_commitment

        else:
            # Subsequent proposals, just leave empty
            empty_block.body.whisk_registration_proof = spec.WhiskTrackerProof()
            empty_block.body.whisk_tracker = spec.WhiskTracker()
            empty_block.body.whisk_k_commitment = spec.BLSG1Point()

    return empty_block


def is_whisk_proposer(tracker: WhiskTracker, k: int) -> bool:
    return py_ecc_G1_to_bytes48(multiply(py_ecc_bytes48_to_G1(tracker.r_G), k)) == tracker.k_r_G


def get_beacon_proposer_to_build(spec, state, proposer_index=None):
    if is_post_eip7441(spec):
        if proposer_index is None:
            return find_whisk_proposer(spec, state)
        else:
            return proposer_index
    else:
        return spec.get_beacon_proposer_index(state)


def find_whisk_proposer(spec, state):
    proposer_tracker = state.whisk_proposer_trackers[state.slot % spec.PROPOSER_TRACKERS_COUNT]

    # Check record of known trackers
    # During the first shuffling phase (epoch < EPOCHS_PER_SHUFFLING_PHASE)
    # proposer trackers are those inserted on the genesis state, and have not gone
    # through any shuffling. We cache those initial trackers and use `resolve_known_tracker`
    # to check if the tracker is known, and skip the need to actually find the matching tracker
    proposer_index = resolve_known_tracker(proposer_tracker)
    if proposer_index is not None:
        return proposer_index

    print("proposer_tracker", proposer_tracker)
    # # First attempt direct equality with trackers
    # for i, validator in enumerate(state.validators):
    #     # # This is insanely slow
    #     # if validator.whisk_tracker == proposer_tracker:
    #     if True:
    #         return i
    # # In Whisk where to get proposer from?
    # raise Exception("proposer_tracker not matched")
    raise Exception("proposer not known without heavy math")


def build_empty_block_for_next_slot(spec, state, proposer_index=None):
    return build_empty_block(spec, state, state.slot + 1, proposer_index)


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
