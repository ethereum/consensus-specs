from eth2spec.test.context import spec_state_test, with_eip7441_and_later, expect_assertion_error
from eth2spec.test.helpers.eip7441 import (
    set_as_first_proposal,
    compute_whisk_k_commitment,
    set_registration,
    register_tracker
)


def empty_block_body(spec):
    return spec.BeaconBlockBody()


def set_as_first_proposal_and_proposer(spec, state, proposer_index):
    state.latest_block_header.proposer_index = proposer_index
    set_as_first_proposal(spec, state, proposer_index)


def run_process_whisk_registration(spec, state, body, valid=True):
    yield 'pre', state
    yield 'body', body

    if not valid:
        expect_assertion_error(lambda: spec.process_whisk_registration(state, body))
        yield 'post', None
        return

    spec.process_whisk_registration(state, body)

    yield 'post', state


IDENTITY_R = 1
OTHER_R = 100_000_2  # Large enough values to not collide with initial k values
OTHER_K = 100_000_2
PROPOSER_INDEX = 0
OTHER_INDEX = 1

# First proposal


@with_eip7441_and_later
@spec_state_test
def test_first_proposal_ok(spec, state):
    body = empty_block_body(spec)
    set_as_first_proposal_and_proposer(spec, state, PROPOSER_INDEX)
    set_registration(body, OTHER_K, OTHER_R)
    yield from run_process_whisk_registration(spec, state, body)


@with_eip7441_and_later
@spec_state_test
def test_first_proposal_identity_tracker(spec, state):
    body = empty_block_body(spec)
    set_as_first_proposal_and_proposer(spec, state, PROPOSER_INDEX)
    set_registration(body, OTHER_K, IDENTITY_R)
    yield from run_process_whisk_registration(spec, state, body, valid=False)


@with_eip7441_and_later
@spec_state_test
def test_first_proposal_non_unique_k_other(spec, state):
    body = empty_block_body(spec)
    set_as_first_proposal_and_proposer(spec, state, PROPOSER_INDEX)
    state.whisk_k_commitments[OTHER_INDEX] = compute_whisk_k_commitment(OTHER_K)
    set_registration(body, OTHER_K, OTHER_R)
    yield from run_process_whisk_registration(spec, state, body, valid=False)


@with_eip7441_and_later
@spec_state_test
def test_first_proposal_non_unique_k_self(spec, state):
    body = empty_block_body(spec)
    set_as_first_proposal_and_proposer(spec, state, PROPOSER_INDEX)
    state.whisk_k_commitments[PROPOSER_INDEX] = compute_whisk_k_commitment(OTHER_K)
    set_registration(body, OTHER_K, OTHER_R)
    yield from run_process_whisk_registration(spec, state, body, valid=False)


@with_eip7441_and_later
@spec_state_test
def test_first_proposal_invalid_proof(spec, state):
    body = empty_block_body(spec)
    set_as_first_proposal_and_proposer(spec, state, PROPOSER_INDEX)
    set_registration(body, OTHER_K, OTHER_R)
    body.whisk_tracker.k_r_G = spec.BLSG1Point()
    yield from run_process_whisk_registration(spec, state, body, valid=False)

# Second proposal


@with_eip7441_and_later
@spec_state_test
def test_second_proposal_ok(spec, state):
    body = empty_block_body(spec)
    # An empty body has the correct values for a second proposal
    # Set tracker to != G1 generator for second proposal condition
    register_tracker(state, PROPOSER_INDEX, OTHER_K, OTHER_R)
    yield from run_process_whisk_registration(spec, state, body)


@with_eip7441_and_later
@spec_state_test
def test_second_proposal_not_zero(spec, state):
    body = empty_block_body(spec)
    set_registration(body, OTHER_K, OTHER_R)
    register_tracker(state, PROPOSER_INDEX, OTHER_K, OTHER_R)
    yield from run_process_whisk_registration(spec, state, body, valid=False)
