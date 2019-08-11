from eth2spec.test.helpers.phase1.shard_block import (
    build_empty_shard_block,
)
from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
    always_bls,
)


@with_all_phases_except(['phase0'])
@always_bls
@spec_state_test
def test_process_empty_shard_block(spec, state):
    beacon_state = state

    shard_slot = spec.PHASE_1_FORK_SLOT
    beacon_state.slot = spec.Slot(spec.PHASE_1_FORK_EPOCH * spec.SLOTS_PER_EPOCH)
    shard_state = spec.get_default_shard_state(beacon_state, shard=spec.Shard(0))
    shard_state.slot = shard_slot

    block = build_empty_shard_block(
        spec,
        shard_state,
        beacon_state,
        slot=shard_slot + 1,
        parent_root=spec.Hash(),
        signed=True,
        full_attestation=False,
    )

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state
    yield 'block', block

    spec.shard_state_transition(shard_state, beacon_state, block)

    yield 'post', shard_state


@with_all_phases_except(['phase0'])
@always_bls
@spec_state_test
def test_process_full_attestation_shard_block(spec, state):
    beacon_state = state

    shard_slot = spec.PHASE_1_FORK_SLOT
    beacon_state.slot = spec.Slot(spec.PHASE_1_FORK_EPOCH * spec.SLOTS_PER_EPOCH)
    shard_state = spec.get_default_shard_state(beacon_state, shard=spec.Shard(0))
    shard_state.slot = shard_slot

    block = build_empty_shard_block(
        spec,
        shard_state,
        beacon_state,
        slot=shard_slot + 1,
        parent_root=spec.Hash(),
        signed=True,
        full_attestation=True,
    )

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state
    yield 'block', block

    spec.shard_state_transition(shard_state, beacon_state, block)

    yield 'post', shard_state
