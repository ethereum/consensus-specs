from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_all_phases,
)
from eth_consensus_specs.test.helpers.block_header import sign_block_header
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.proposer_slashings import get_valid_proposer_slashing
from eth_consensus_specs.test.helpers.state import next_epoch, next_slots
from tests.infra.helpers.proposer_slashings import (
    assert_process_proposer_slashing,
    prepare_process_proposer_slashing,
    run_proposer_slashing_processing,
)


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)
    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_headers_differ_only_state_root(spec, state):
    """
    Verify slashing succeeds when headers differ only by state_root.

    Input State Configured:
        - Two headers with identical slot, proposer_index, parent_root, body_root
        - Only state_root differs between headers

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        state_root_2=b"\x99" * 32,  # Only state_root differs
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_headers_differ_only_body_root(spec, state):
    """
    Verify slashing succeeds when headers differ only by body_root.

    Input State Configured:
        - Two headers with identical slot, proposer_index, parent_root, state_root
        - Only body_root differs between headers

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        body_root_2=b"\x99" * 32,  # Only body_root differs
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_headers_differ_multiple_roots(spec, state):
    """
    Verify slashing succeeds when headers differ by multiple root fields.

    Input State Configured:
        - Two headers with identical slot and proposer_index
        - parent_root, state_root, and body_root all differ between headers

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        parent_root_2=b"\x99" * 32,
        state_root_2=b"\xaa" * 32,
        body_root_2=b"\xbb" * 32,
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_slashed_and_proposer_index_the_same(spec, state):
    proposer_index = spec.get_beacon_proposer_index(state)

    # Create slashing for same proposer
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slashed_index=proposer_index, signed_1=True, signed_2=True
    )
    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_self_slashing_future_slot(spec, state):
    """
    Verify self-slashing succeeds when headers reference a future slot.

    Input State Configured:
        - Block proposer determined for current slot
        - Proposer slashing created targeting the same proposer
        - Headers reference a future slot (state.slot + 5)

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    proposer_index = spec.get_beacon_proposer_index(state)

    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        proposer_index=proposer_index,
        slot_offset=5,
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_block_header_from_past(spec, state):
    """
    Verify slashing succeeds when headers reference a past slot.

    Input State Configured:
        - Proposer slashing created with headers at initial state.slot
        - State advanced by one epoch (headers now reference past slot)

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs_after=1,  # Advance state after creating slashing
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_block_header_from_future(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slot=state.slot + 5, signed_1=True, signed_2=True
    )
    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_1(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=False, signed_2=True)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_2(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=False)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_1_and_2(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=False, signed_2=False)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_1_and_2_swap(spec, state):
    # Get valid signatures for the slashings
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    # But swap them
    signature_1 = proposer_slashing.signed_header_1.signature
    proposer_slashing.signed_header_1.signature = proposer_slashing.signed_header_2.signature
    proposer_slashing.signed_header_2.signature = signature_1

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_invalid_incorrect_proposer_index(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)
    # Index just too high (by 1)
    proposer_slashing.signed_header_1.message.proposer_index = len(state.validators)
    proposer_slashing.signed_header_2.message.proposer_index = len(state.validators)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_invalid_different_proposer_indices(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)
    # set different index and sign
    header_1 = proposer_slashing.signed_header_1.message
    header_2 = proposer_slashing.signed_header_2.message
    active_indices = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    active_indices = [i for i in active_indices if i != header_1.proposer_index]

    header_2.proposer_index = active_indices[0]
    proposer_slashing.signed_header_2 = sign_block_header(
        spec, state, header_2, privkeys[header_2.proposer_index]
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_proposer_index_zero(spec, state):
    """
    Verify slashing succeeds for validator at index 0.

    Input State Configured:
        - Proposer slashing targeting validator at index 0

    Output State Verified:
        - Slashing succeeds
        - Validator at index 0 marked as slashed
    """
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slashed_index=0, signed_1=True, signed_2=True
    )
    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_proposer_index_last(spec, state):
    """
    Verify slashing succeeds for validator at the last index.

    Input State Configured:
        - Proposer slashing targeting last validator in the registry

    Output State Verified:
        - Slashing succeeds
        - Last validator marked as slashed
    """
    # prepare_process_proposer_slashing defaults to last active validator
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_invalid_slots_of_different_epochs(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=False)

    # set slots to be in different epochs
    header_2 = proposer_slashing.signed_header_2.message
    proposer_index = header_2.proposer_index
    header_2.slot += spec.SLOTS_PER_EPOCH
    proposer_slashing.signed_header_2 = sign_block_header(
        spec, state, header_2, privkeys[proposer_index]
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_invalid_slots_same_epoch_different_slot(spec, state):
    """
    Verify slashing fails when headers have different slots within the same epoch.

    Input State Configured:
        - Proposer slashing with header_1 at state.slot
        - header_2 at state.slot + 1 (different slot, same epoch)

    Output State Verified:
        - AssertionError raised (slots must match exactly)
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        slot_2=state.slot + 1,  # Different slot for header_2
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        state_unchanged=True,  # Slashing was rejected, state should not change
    )


@with_all_phases
@spec_state_test
def test_invalid_headers_are_same_sigs_are_same(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=False)

    # set headers to be the same
    proposer_slashing.signed_header_2 = proposer_slashing.signed_header_1.copy()

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_invalid_headers_are_same_sigs_are_different(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=False)

    # set headers to be the same
    proposer_slashing.signed_header_2 = proposer_slashing.signed_header_1.copy()
    # but signatures to be different
    proposer_slashing.signed_header_2.signature = (
        proposer_slashing.signed_header_2.signature[:-1] + b"\x00"
    )

    assert (
        proposer_slashing.signed_header_1.signature != proposer_slashing.signed_header_2.signature
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_invalid_proposer_is_not_activated(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    # set proposer to be not active yet
    proposer_index = proposer_slashing.signed_header_1.message.proposer_index
    state.validators[proposer_index].activation_epoch = spec.get_current_epoch(state) + 1

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_proposer_activated_current_epoch(spec, state):
    """
    Verify slashing succeeds for validator activated in the current epoch.

    Input State Configured:
        - Validator's activation_epoch set to current_epoch (just became active)

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        proposer_activation_epoch_offset=0,  # Activated at current epoch
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_invalid_proposer_is_slashed(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    # set proposer to slashed
    proposer_index = proposer_slashing.signed_header_1.message.proposer_index
    state.validators[proposer_index].slashed = True

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_proposer_withdrawable_next_epoch(spec, state):
    """
    Verify slashing succeeds for validator withdrawable in the next epoch.

    Input State Configured:
        - Validator's withdrawable_epoch set to current_epoch + 1 (still slashable)

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        proposer_withdrawable_epoch_offset=1,  # Withdrawable next epoch
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_invalid_proposer_withdrawable_current_epoch(spec, state):
    """
    Verify slashing fails when validator is withdrawable at current epoch.

    Input State Configured:
        - Validator's withdrawable_epoch set to current_epoch (minimum invalid)

    Output State Verified:
        - AssertionError raised (validator not slashable when withdrawable)
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        proposer_withdrawable_epoch_offset=0,  # Withdrawable at current epoch
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        state_unchanged=True,  # Slashing was rejected, state should not change
    )


@with_all_phases
@spec_state_test
def test_invalid_proposer_is_withdrawn(spec, state):
    proposer_slashing = get_valid_proposer_slashing(spec, state, signed_1=True, signed_2=True)

    # move 1 epoch into future, to allow for past withdrawable epoch
    next_epoch(spec, state)
    # set proposer withdrawable_epoch in past
    current_epoch = spec.get_current_epoch(state)
    proposer_index = proposer_slashing.signed_header_1.message.proposer_index
    state.validators[proposer_index].withdrawable_epoch = current_epoch - 1

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing, valid=False)

    assert_process_proposer_slashing(spec, state, pre_state, state_unchanged=True)


@with_all_phases
@spec_state_test
def test_header_slot_at_epoch_start(spec, state):
    """
    Verify slashing succeeds with headers at the first slot of an epoch.

    Input State Configured:
        - State advanced to first slot of next epoch
        - Headers reference the epoch start slot

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=1,  # Advance to first slot of next epoch
        slot_offset=0,  # Headers at epoch start
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    assert state.slot % spec.SLOTS_PER_EPOCH == 0

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_all_phases
@spec_state_test
def test_header_slot_at_epoch_end(spec, state):
    """
    Verify slashing succeeds with headers at the last slot of an epoch.

    Input State Configured:
        - State advanced to last slot of current epoch
        - Headers reference the epoch end slot

    Output State Verified:
        - Slashing succeeds
        - Validator marked as slashed
    """
    # Advance to last slot of epoch before calling helper
    slots_to_end = spec.SLOTS_PER_EPOCH - 1 - (state.slot % spec.SLOTS_PER_EPOCH)
    next_slots(spec, state, slots_to_end)

    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        slot_offset=0,  # Headers at current (last) slot
        parent_root_2=b"\x99" * 32,  # Make headers different
    )

    assert state.slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )
