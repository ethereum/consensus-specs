import random
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_epoch,
    next_epoch_via_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    build_empty_block,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
)
from eth2spec.test.context import (
    with_altair_and_later,
    spec_state_test,
)


def run_sync_committee_sanity_test(spec, state, fraction_full=1.0):
    all_pubkeys = [v.pubkey for v in state.validators]
    committee = [all_pubkeys.index(pubkey) for pubkey in state.current_sync_committee.pubkeys]
    participants = random.sample(committee, int(len(committee) * fraction_full))

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=[index in participants for index in committee],
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            participants,
        )
    )
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state


@with_altair_and_later
@spec_state_test
def test_full_sync_committee_committee(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=1.0)


@with_altair_and_later
@spec_state_test
def test_half_sync_committee_committee(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.5)


@with_altair_and_later
@spec_state_test
def test_empty_sync_committee_committee(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.0)


@with_altair_and_later
@spec_state_test
def test_full_sync_committee_committee_genesis(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=1.0)


@with_altair_and_later
@spec_state_test
def test_half_sync_committee_committee_genesis(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.5)


@with_altair_and_later
@spec_state_test
def test_empty_sync_committee_committee_genesis(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.0)


@with_altair_and_later
@spec_state_test
def test_inactivity_scores(spec, state):
    for _ in range(spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY + 2):
        next_epoch_via_block(spec, state)

    assert spec.is_in_inactivity_leak(state)
    previous_inactivity_scores = state.inactivity_scores.copy()

    yield 'pre', state

    # Block transition to next epoch
    block = build_empty_block(spec, state, slot=state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    for pre, post in zip(previous_inactivity_scores, state.inactivity_scores):
        assert post == pre + spec.config.INACTIVITY_SCORE_BIAS
