from curdleproofs import GenerateWhiskShuffleProof

from eth2spec.test.context import expect_assertion_error, spec_state_test, with_eip7441_and_later
from eth2spec.test.helpers.eip7441 import compute_whisk_tracker
from eth2spec.test.helpers.keys import whisk_ks_initial


def set_correct_shuffle_proofs(spec, state, body):
    pre_shuffle_trackers = get_and_populate_pre_shuffle_trackers(spec, state, body)

    post_trackers, shuffle_proof = GenerateWhiskShuffleProof(
        spec.CURDLEPROOFS_CRS, pre_shuffle_trackers
    )
    body.whisk_post_shuffle_trackers = post_trackers
    body.whisk_shuffle_proof = shuffle_proof


def get_and_populate_pre_shuffle_trackers(spec, state, body):
    shuffle_indices = spec.get_shuffle_indices(body.randao_reveal)
    pre_shuffle_trackers = []
    for i in shuffle_indices:
        # Set r to some value > 1 ( = 2+i)
        tracker = compute_whisk_tracker(whisk_ks_initial(i), 2 + i)
        state.whisk_candidate_trackers[i] = tracker
        pre_shuffle_trackers.append(tracker)
    return pre_shuffle_trackers


def get_pre_shuffle_trackers(spec, state, body):
    return [state.whisk_candidate_trackers[i] for i in spec.get_shuffle_indices(body.randao_reveal)]


def set_state_epoch(spec, state, epoch):
    state.slot = epoch * spec.SLOTS_PER_EPOCH


def set_state_epoch_selection_gap(spec, state):
    set_state_epoch(spec, state, spec.config.EPOCHS_PER_SHUFFLING_PHASE - 1)


def empty_block_body(spec):
    return spec.BeaconBlockBody()


def run_process_shuffled_trackers(spec, state, body, valid=True):
    yield "pre", state
    yield "body", body

    if not valid:
        expect_assertion_error(lambda: spec.process_shuffled_trackers(state, body))
        yield "post", None
        return

    spec.process_shuffled_trackers(state, body)

    yield "post", state


@with_eip7441_and_later
@spec_state_test
def test_shuffle_trackers(spec, state):
    body = empty_block_body(spec)
    set_correct_shuffle_proofs(spec, state, body)
    yield from run_process_shuffled_trackers(spec, state, body)


@with_eip7441_and_later
@spec_state_test
def test_no_shuffle_minus_selection_gap(spec, state):
    body = empty_block_body(spec)
    set_state_epoch_selection_gap(spec, state)
    yield from run_process_shuffled_trackers(spec, state, body)


@with_eip7441_and_later
@spec_state_test
def test_no_shuffle_minus_one_and_selection_gap(spec, state):
    body = empty_block_body(spec)
    set_state_epoch(
        spec, state, spec.config.EPOCHS_PER_SHUFFLING_PHASE - spec.config.PROPOSER_SELECTION_GAP - 1
    )
    yield from run_process_shuffled_trackers(spec, state, body)


@with_eip7441_and_later
@spec_state_test
def test_shuffle_during_selection_gap(spec, state):
    body = empty_block_body(spec)
    set_correct_shuffle_proofs(spec, state, body)
    set_state_epoch_selection_gap(spec, state)
    yield from run_process_shuffled_trackers(spec, state, body, valid=False)


# Invalid cases on shuffle
# - wrong proof
# - wrong post shuffle


@with_eip7441_and_later
@spec_state_test
def test_invalid_shuffle_bad_proof(spec, state):
    body = empty_block_body(spec)
    set_correct_shuffle_proofs(spec, state, body)
    body.whisk_shuffle_proof = spec.WhiskShuffleProof()
    yield from run_process_shuffled_trackers(spec, state, body, valid=False)


@with_eip7441_and_later
@spec_state_test
def test_invalid_shuffle_bad_trackers_zero(spec, state):
    body = empty_block_body(spec)
    set_correct_shuffle_proofs(spec, state, body)
    body.whisk_post_shuffle_trackers[0] = spec.WhiskTracker()
    yield from run_process_shuffled_trackers(spec, state, body, valid=False)


# Invalid cases on gap
# - not empty shuffle trackers
# - not empty proof


@with_eip7441_and_later
@spec_state_test
def test_invalid_gap_non_zero_proof(spec, state):
    body = empty_block_body(spec)
    body.whisk_shuffle_proof = spec.WhiskShuffleProof("0xff")
    set_state_epoch_selection_gap(spec, state)
    yield from run_process_shuffled_trackers(spec, state, body, valid=False)


@with_eip7441_and_later
@spec_state_test
def test_invalid_gap_non_zero_trackers(spec, state):
    body = empty_block_body(spec)
    body.whisk_post_shuffle_trackers = get_and_populate_pre_shuffle_trackers(spec, state, body)
    set_state_epoch_selection_gap(spec, state)
    yield from run_process_shuffled_trackers(spec, state, body, valid=False)
