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
from eth2spec.test.helpers.state import transition_to, transition_to_valid_shard_slot


def run_basic_crosslink_tests(spec, state, target_len_offset_slot, valid=True):
    state = transition_to_valid_shard_slot(spec, state)
    # At the beginning, let `x = state.slot`, `state.shard_states[shard].slot == x - 1`
    slot_x = state.slot
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    assert state.shard_states[shard].slot == slot_x - 1

    # Create SignedShardBlock
    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    shard_block = build_shard_block(spec, state, shard, body=body, signed=True)
    shard_blocks = [shard_block]
    # Create a shard_transitions that would be included at beacon block `state.slot + target_len_offset_slot`
    shard_transitions = build_shard_transitions_till_slot(
        spec,
        state,
        shard_blocks={shard: shard_blocks},
        on_time_slot=state.slot + target_len_offset_slot,
    )
    shard_transition = shard_transitions[shard]
    # Create an attestation that would be included at beacon block `state.slot + target_len_offset_slot`
    attestation = build_attestation_with_shard_transition(
        spec,
        state,
        index=committee_index,
        on_time_slot=state.slot + target_len_offset_slot,
        shard_transition=shard_transition,
    )
    pre_gasprice = state.shard_states[shard].gasprice

    transition_to(spec, state, state.slot + target_len_offset_slot)
    pre_shard_state = state.shard_states[shard]

    yield from run_crosslinks_processing(spec, state, shard_transitions, [attestation], valid=valid)

    if valid:
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
    yield from run_basic_crosslink_tests(spec, state, target_len_offset_slot=1, valid=True)


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_multiple_offset_slots(spec, state):
    yield from run_basic_crosslink_tests(spec, state, target_len_offset_slot=3, valid=True)
