from eth_consensus_specs.test.context import spec_state_test, with_phases, with_presets
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    run_attestation_processing,
    sign_attestation,
)
from eth_consensus_specs.test.helpers.block import apply_empty_block
from eth_consensus_specs.test.helpers.constants import MINIMAL, PQ
from eth_consensus_specs.test.helpers.state import next_slot, next_slots


def run_grandparent_attestation(spec, state, block_available, other_available):
    """
    Process an attestation with ``index = 1`` for skipped slot 2, whose block at
    slot 1 is the grandparent of the block at slot 3, setting the availability
    bit at slot 1 to ``block_available`` and the bits at slots 2 and 3 to
    ``other_available``. Return whether the attester received the timely head
    flag.
    """
    apply_empty_block(spec, state, 1)
    apply_empty_block(spec, state, 3)
    next_slot(spec, state)
    assert state.slot == 2 + spec.MIN_ATTESTATION_INCLUSION_DELAY_PQ
    state.execution_payload_availability[1] = block_available
    state.execution_payload_availability[2] = other_available
    state.execution_payload_availability[3] = other_available

    attestation = get_valid_attestation(
        spec, state, slot=2, beacon_block_root=spec.get_block_root_at_slot(state, 1)
    )
    attestation.data.index = 1
    sign_attestation(spec, state, attestation)
    assert not spec.is_attestation_same_slot(state, attestation.data)
    validator_index = next(iter(spec.get_attesting_indices(state, attestation)))

    yield from run_attestation_processing(spec, state, attestation)

    participation = state.current_epoch_participation[validator_index]
    return spec.has_flag(participation, spec.TIMELY_HEAD_FLAG_INDEX)


@with_phases([PQ])
@spec_state_test
def test_grandparent_matching_payload_gets_head_flag(spec, state):
    """
    Test that an attestation for the grandparent gets the head flag when
    ``data.index`` matches the availability bit at the grandparent's slot.
    """
    has_head_flag = yield from run_grandparent_attestation(spec, state, 1, 0)
    assert has_head_flag


@with_phases([PQ])
@spec_state_test
def test_grandparent_mismatched_payload_no_head_flag(spec, state):
    """
    Test that an attestation for the grandparent does not get the head flag when
    ``data.index`` does not match the availability bit at the grandparent's
    slot, even if the bits at ``data.slot`` and the parent's slot match.
    """
    has_head_flag = yield from run_grandparent_attestation(spec, state, 0, 1)
    assert not has_head_flag


@with_phases([PQ])
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_attested_block_older_than_block_roots(spec, state):
    """
    Test that an attestation is valid when the block it votes for is older than
    the block roots kept in the state and is not the parent block.
    """
    attestation_slot = spec.Slot(spec.SLOTS_PER_HISTORICAL_ROOT)
    apply_empty_block(spec, state, attestation_slot + 1)
    next_slots(spec, state, 1)
    assert state.slot == attestation_slot + spec.MIN_ATTESTATION_INCLUSION_DELAY_PQ

    # The parent block comes after the attestation slot, so the attestation
    # votes for the genesis block, whose slot is outside the block roots kept
    assert state.latest_block_header.slot == attestation_slot + 1
    attestation = get_valid_attestation(spec, state, slot=attestation_slot, signed=True)
    assert attestation.data.beacon_block_root == state.latest_block_header.parent_root

    yield from run_attestation_processing(spec, state, attestation)
