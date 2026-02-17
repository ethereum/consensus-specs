from curdleproofs import WhiskTracker

from eth_consensus_specs.test.context import spec_state_test, with_eip7441_and_later
from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.eip7441 import compute_whisk_tracker_and_commitment
from eth_consensus_specs.test.helpers.keys import whisk_ks_initial
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

known_whisk_trackers = {}


def assign_proposer_at_slot(state, slot: int):
    state


def initialize_whisk_full(spec, state):
    # TODO: De-duplicate code from whisk/fork.md
    for index in range(len(state.validators)):
        whisk_k_commitment, whisk_tracker = spec.get_initial_commitments(whisk_ks_initial(index))
        state.whisk_k_commitments[index] = whisk_k_commitment
        state.whisk_trackers[index] = whisk_tracker

    # Do a candidate selection followed by a proposer selection so that we have proposers for the upcoming day
    # Use an old epoch when selecting candidates so that we don't get the same seed as in the next candidate selection
    spec.select_whisk_candidate_trackers(state, spec.Epoch(0))
    spec.select_whisk_proposer_trackers(state, spec.Epoch(0))


# Fill candidate trackers with the same tracker so shuffling does not break
def fill_candidate_trackers(spec, state, tracker: WhiskTracker):
    for i in range(spec.CANDIDATE_TRACKERS_COUNT):
        state.whisk_candidate_trackers[i] = tracker


@with_eip7441_and_later
@spec_state_test
def test_eip7441__process_block_single_initial(spec, state):
    assert state.slot == 0
    proposer_slot_1 = 0
    tracker_slot_1, k_commitment = compute_whisk_tracker_and_commitment(
        whisk_ks_initial(proposer_slot_1), 1
    )
    state.whisk_k_commitments[proposer_slot_1] = k_commitment
    state.whisk_proposer_trackers[1] = tracker_slot_1
    fill_candidate_trackers(spec, state, tracker_slot_1)

    # Produce and process a whisk block
    yield "pre", state

    block = build_empty_block(spec, state, 1, proposer_slot_1)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state
