from random import Random

from eth2spec.test.context import (
    spec_state_test,
    with_altair_and_later,
)
from eth2spec.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.inactivity_scores import randomize_inactivity_scores
from eth2spec.test.helpers.rewards import leaking
from eth2spec.test.helpers.state import (
    next_epoch,
    set_full_participation_previous_epoch,
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
)


def run_sync_committee_sanity_test(spec, state, fraction_full=1.0, rng=Random(454545)):
    all_pubkeys = [v.pubkey for v in state.validators]
    committee = [all_pubkeys.index(pubkey) for pubkey in state.current_sync_committee.pubkeys]
    selected_indices = rng.sample(range(len(committee)), int(len(committee) * fraction_full))
    sync_committee_bits = [i in selected_indices for i in range(len(committee))]
    participants = [
        validator_index for i, validator_index in enumerate(committee) if sync_committee_bits[i]
    ]

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_aggregate = spec.SyncAggregate(
        sync_committee_bits=sync_committee_bits,
        sync_committee_signature=compute_aggregate_sync_committee_signature(
            spec,
            state,
            block.slot - 1,
            participants,
        ),
    )
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state


@with_altair_and_later
@spec_state_test
def test_sync_committee_committee__full(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=1.0)


@with_altair_and_later
@spec_state_test
def test_sync_committee_committee__half(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.5, rng=Random(1212))


@with_altair_and_later
@spec_state_test
def test_sync_committee_committee__empty(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.0)


@with_altair_and_later
@spec_state_test
def test_sync_committee_committee_genesis__full(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=1.0)


@with_altair_and_later
@spec_state_test
def test_sync_committee_committee_genesis__half(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.5, rng=Random(2323))


@with_altair_and_later
@spec_state_test
def test_sync_committee_committee_genesis__empty(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.0)


@with_altair_and_later
@spec_state_test
@leaking()
def test_inactivity_scores_leaking(spec, state):
    assert spec.is_in_inactivity_leak(state)

    randomize_inactivity_scores(spec, state, rng=Random(5252))
    assert len(set(state.inactivity_scores)) > 1

    previous_inactivity_scores = state.inactivity_scores.copy()

    yield "pre", state

    # Block transition to next epoch
    block = build_empty_block(spec, state, slot=state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state

    # No participation during a leak so all scores should increase
    for pre, post in zip(previous_inactivity_scores, state.inactivity_scores):
        assert post == pre + spec.config.INACTIVITY_SCORE_BIAS


@with_altair_and_later
@spec_state_test
@leaking()
def test_inactivity_scores_full_participation_leaking(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(5252))
    assert len(set(state.inactivity_scores)) > 1

    # Only set full participation for previous epoch to remain in leak
    set_full_participation_previous_epoch(spec, state)

    previous_inactivity_scores = state.inactivity_scores.copy()

    yield "pre", state

    # Block transition to next epoch
    block = build_empty_block(spec, state, slot=state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    assert spec.is_in_inactivity_leak(state)

    yield "blocks", [signed_block]
    yield "post", state

    # Full participation during a leak so all scores should decrease by 1
    for pre, post in zip(previous_inactivity_scores, state.inactivity_scores):
        assert post == pre - 1
