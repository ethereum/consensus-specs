from eth2spec.test.context import (
    PHASE0,
    with_all_phases_except,
    spec_state_test,
    always_bls,
)
from eth2spec.test.helpers.crosslinks import run_crosslinks_processing
from eth2spec.test.helpers.shard_block import (
    build_attestation_with_shard_transition,
    build_shard_block,
    build_shard_transitions_till_slot,
)
from eth2spec.test.helpers.state import next_epoch, next_slot, transition_to


def run_basic_crosslink_tests(spec, state, target_len_offset_slot):
    next_epoch(spec, state)
    next_epoch(spec, state)
    state = spec.upgrade_to_phase1(state)
    next_slot(spec, state)

    # At the beginning, let `x = state.slot`, `state.shard_states[shard].slot == x - 1`
    slot_x = state.slot
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    assert state.shard_states[shard].slot == slot_x - 1

    # Create SignedShardBlock at slot `shard_state.slot + 1` -> x
    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    shard_block = build_shard_block(spec, state, shard, body=body, signed=True)
    shard_blocks = [shard_block]

    # Attester creates `attestation` at slot x
    # Use temporary next state to get ShardTransition of shard block
    shard_transitions = build_shard_transitions_till_slot(
        spec,
        state,
        shards=[shard, ],
        shard_blocks={shard: shard_blocks},
        target_len_offset_slot=target_len_offset_slot,
    )
    shard_transition = shard_transitions[shard]
    attestation = build_attestation_with_shard_transition(
        spec,
        state,
        slot=slot_x + target_len_offset_slot - 1,
        index=committee_index,
        target_len_offset_slot=target_len_offset_slot,
        shard_transition=shard_transition,
    )
    pre_gasprice = state.shard_states[shard].gasprice

    transition_to(spec, state, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)
    pre_shard_state = state.shard_states[shard]
    yield from run_crosslinks_processing(spec, state, shard_transitions, [attestation])

    # After state transition,
    assert state.slot == slot_x + target_len_offset_slot
    shard_state = state.shard_states[shard]
    assert shard_state != pre_shard_state
    assert shard_state == shard_transition.shard_states[len(shard_transition.shard_states) - 1]

    if target_len_offset_slot == 1:
        assert shard_state.gasprice > pre_gasprice


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_basic_crosslinks(spec, state):
    run_basic_crosslink_tests(spec, state, target_len_offset_slot=1)


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_multiple_offset_slots(spec, state):
    run_basic_crosslink_tests(spec, state, target_len_offset_slot=3)
