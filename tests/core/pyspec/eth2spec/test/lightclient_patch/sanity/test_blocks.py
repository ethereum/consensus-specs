import random
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_epoch,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.sync_committee import (
    compute_aggregate_sync_committee_signature,
)
from eth2spec.test.context import (
    PHASE0, PHASE1,
    with_all_phases_except,
    spec_state_test,
)


def run_sync_committee_sanity_test(spec, state, fraction_full=1.0):
    committee = spec.get_sync_committee_indices(state, spec.get_current_epoch(state))
    participants = random.sample(committee, int(len(committee) * fraction_full))

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.sync_committee_bits = [index in participants for index in committee]
    block.body.sync_committee_signature = compute_aggregate_sync_committee_signature(
        spec,
        state,
        block.slot - 1,
        participants,
    )
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
def test_full_sync_committee_committee(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=1.0)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
def test_half_sync_committee_committee(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.5)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
def test_empty_sync_committee_committee(spec, state):
    next_epoch(spec, state)
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.0)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
def test_full_sync_committee_committee_genesis(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=1.0)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
def test_half_sync_committee_committee_genesis(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.5)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
def test_empty_sync_committee_committee_genesis(spec, state):
    yield from run_sync_committee_sanity_test(spec, state, fraction_full=0.0)
