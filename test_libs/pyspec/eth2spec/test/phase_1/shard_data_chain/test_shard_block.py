from eth2spec.test.helpers.phase1.shard_block import (
    build_empty_shard_block,
)
from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
    always_bls,
)


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_process_empty_shard_block(spec, beacon_state):
    beacon_state.slot = spec.Slot(spec.SHARD_GENESIS_EPOCH * spec.SLOTS_PER_EPOCH)
    shard_state = spec.get_genesis_shard_state(spec.Shard(0))
    shard_state.slot = spec.ShardSlot(spec.SHARD_GENESIS_EPOCH * spec.SHARD_SLOTS_PER_EPOCH)

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
    yield 'block', block

    spec.shard_state_transition(beacon_state, shard_state, block)

    yield 'post', shard_state


@with_all_phases_except(['phase0'])
@spec_state_test
@always_bls
def test_process_full_attestation_shard_block(spec, beacon_state):
    beacon_state.slot = spec.Slot(spec.SHARD_GENESIS_EPOCH * spec.SLOTS_PER_EPOCH)
    shard_state = spec.get_genesis_shard_state(spec.Shard(0))
    shard_state.slot = spec.SHARD_GENESIS_EPOCH * spec.SHARD_SLOTS_PER_EPOCH

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
    yield 'block', block

    spec.shard_state_transition(beacon_state, shard_state, block)

    yield 'post', shard_state
