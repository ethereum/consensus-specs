from eth2spec.test.context import (
    spec_state_test,
    with_eip7441_and_later,
    expect_assertion_error,
)
from eth2spec.test.helpers.eip7441 import (
    compute_whisk_k_commitment,
    compute_whisk_tracker,
    set_opening_proof,
)


def empty_block(spec):
    return spec.BeaconBlock()


def run_process_whisk_opening_proof(spec, state, block, valid=True):
    yield "pre", state
    yield "block", block

    if not valid:
        expect_assertion_error(lambda: spec.process_whisk_opening_proof(state, block))
        yield "post", None
        return

    spec.process_whisk_opening_proof(state, block)

    yield "post", state


PROPOSER_INDEX = 0
K_OK = 2
K_WRONG = 3
R_OK = 2
R_WRONG = 3


@with_eip7441_and_later
@spec_state_test
def test_valid_proof(spec, state):
    block = empty_block(spec)
    set_opening_proof(spec, state, block, PROPOSER_INDEX, K_OK, R_OK)
    run_process_whisk_opening_proof(spec, state, block)


@with_eip7441_and_later
@spec_state_test
def test_wrong_commitment(spec, state):
    block = empty_block(spec)
    set_opening_proof(spec, state, block, PROPOSER_INDEX, K_OK, R_OK)
    state.whisk_k_commitments[PROPOSER_INDEX] = compute_whisk_k_commitment(K_WRONG)
    run_process_whisk_opening_proof(spec, state, block, valid=False)


@with_eip7441_and_later
@spec_state_test
def test_wrong_tracker_r(spec, state):
    block = empty_block(spec)
    set_opening_proof(spec, state, block, PROPOSER_INDEX, K_OK, R_OK)
    wrong_tracker = compute_whisk_tracker(K_OK, R_WRONG)
    state.whisk_proposer_trackers[state.slot % spec.PROPOSER_TRACKERS_COUNT] = (
        wrong_tracker
    )
    run_process_whisk_opening_proof(spec, state, block, valid=False)


@with_eip7441_and_later
@spec_state_test
def test_wrong_proof(spec, state):
    block = empty_block(spec)
    set_opening_proof(spec, state, block, PROPOSER_INDEX, K_OK, R_OK)
    block.body.whisk_opening_proof = spec.WhiskTrackerProof()
    run_process_whisk_opening_proof(spec, state, block, valid=False)
