from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
    always_bls,
)
from eth2spec.test.helpers.phase1.shard_block import (
    build_empty_shard_block,
)
from eth2spec.test.helpers.attestations import get_valid_attestation


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
        full_attestation=True,
    )

    yield 'pre', shard_state
    yield 'beacon_state', beacon_state
    yield 'block', block

    beacon_attestation = get_valid_attestation(spec, beacon_state, signed=True)
    yield 'beacon_attestation', beacon_attestation

    is_valid_beacon_attestation = spec.is_valid_beacon_attestation(
        pre_state=shard_state,
        shard_blocks_or_state_roots=(block,),
        beacon_state=beacon_state,
        valid_attestations=set([beacon_attestation]),
        candidate=beacon_attestation,
    )
    assert is_valid_beacon_attestation
    yield 'is_valid_beacon_attestation', is_valid_beacon_attestation
