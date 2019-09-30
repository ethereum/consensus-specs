from copy import deepcopy

from eth2spec.test.helpers.phase1.shard_block import (
    build_empty_shard_block,
    sign_shard_block,
)
from eth2spec.test.helpers.phase1.shard_state import (
    configure_shard_state,
    shard_state_transition_and_sign_block,
)
from eth2spec.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_all_phases_except,
)


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_process_empty_shard_block(spec, state):
    beacon_state, shard_state = configure_shard_state(spec, state)

    block = build_empty_shard_block(
        spec,
        beacon_state,
        shard_state,
        slot=shard_state.slot + 1,
        signed=True,
        full_attestation=False,
    )

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state

    shard_state_transition_and_sign_block(spec, beacon_state, shard_state, block)

    yield 'blocks', [block]
    yield 'post', shard_state


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_process_full_attestation_shard_block(spec, state):
    beacon_state, shard_state = configure_shard_state(spec, state)

    block = build_empty_shard_block(
        spec,
        beacon_state,
        shard_state,
        slot=shard_state.slot + 1,
        signed=True,
        full_attestation=True,
    )

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state

    shard_state_transition_and_sign_block(spec, beacon_state, shard_state, block)

    yield 'blocks', [block]
    yield 'post', shard_state


@with_all_phases_except(['phase0'])
@spec_state_test
def test_prev_slot_block_transition(spec, state):
    beacon_state, shard_state = configure_shard_state(spec, state)

    # Go to clean slot
    spec.process_shard_slots(shard_state, shard_state.slot + 1)
    # Make a block for it
    block = build_empty_shard_block(spec, beacon_state, shard_state, slot=shard_state.slot, signed=True)
    # Transition to next slot, above block will not be invalid on top of new state.
    spec.process_shard_slots(shard_state, shard_state.slot + 1)

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state
    expect_assertion_error(
        lambda: spec.shard_state_transition(beacon_state, shard_state, block)
    )
    yield 'blocks', [block]
    yield 'post', None


@with_all_phases_except(['phase0'])
@spec_state_test
def test_same_slot_block_transition(spec, state):
    beacon_state, shard_state = configure_shard_state(spec, state)

    # Same slot on top of pre-state, but move out of slot 0 first.
    spec.process_shard_slots(shard_state, shard_state.slot + 1)
    block = build_empty_shard_block(spec, beacon_state, shard_state, slot=shard_state.slot, signed=True)

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state

    shard_state_transition_and_sign_block(spec, beacon_state, shard_state, block)

    yield 'blocks', [block]
    yield 'post', shard_state


@with_all_phases_except(['phase0'])
@spec_state_test
def test_invalid_state_root(spec, state):
    beacon_state, shard_state = configure_shard_state(spec, state)

    spec.process_shard_slots(shard_state, shard_state.slot + 1)
    block = build_empty_shard_block(spec, beacon_state, shard_state, slot=shard_state.slot)
    block.state_root = b'\x36' * 32
    sign_shard_block(spec, beacon_state, shard_state, block)

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state
    expect_assertion_error(
        lambda: spec.shard_state_transition(beacon_state, shard_state, block, validate_state_root=True)
    )
    yield 'blocks', [block]
    yield 'post', None


@with_all_phases_except(['phase0'])
@spec_state_test
def test_skipped_slots(spec, state):
    beacon_state, shard_state = configure_shard_state(spec, state)

    block = build_empty_shard_block(spec, beacon_state, shard_state, slot=shard_state.slot + 3, signed=True)

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state

    shard_state_transition_and_sign_block(spec, beacon_state, shard_state, block)

    yield 'blocks', [block]
    yield 'post', shard_state

    assert shard_state.slot == block.slot
    latest_block_header = deepcopy(shard_state.latest_block_header)
    latest_block_header.state_root = shard_state.hash_tree_root()
    assert latest_block_header.signing_root() == block.signing_root()


@with_all_phases_except(['phase0'])
@spec_state_test
def test_empty_shard_period_transition(spec, state):
    beacon_state, shard_state = configure_shard_state(spec, state)

    # modify some of the deltas to ensure the period transition works properly
    stub_delta = 10
    shard_state.newer_committee_positive_deltas[0] = stub_delta
    shard_state.newer_committee_negative_deltas[0] = stub_delta

    slot = shard_state.slot + spec.SHARD_SLOTS_PER_EPOCH * spec.EPOCHS_PER_SHARD_PERIOD
    block = build_empty_shard_block(spec, beacon_state, shard_state, slot=slot, signed=True)

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state

    shard_state_transition_and_sign_block(spec, beacon_state, shard_state, block)

    yield 'blocks', [block]
    yield 'post', shard_state

    shard_state.older_committee_positive_deltas[0] == stub_delta
    shard_state.older_committee_negative_deltas[0] == stub_delta
    shard_state.newer_committee_positive_deltas[0] == 0
    shard_state.newer_committee_negative_deltas[0] == 0
