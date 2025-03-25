from eth2spec.test.context import (
    spec_state_test,
    expect_assertion_error,
    always_bls,
    with_all_phases,
)
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.block_header import sign_block_header
from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.proposer_slashings import (
    get_valid_proposer_slashing,
    check_proposer_slashing_effect,
)
from eth2spec.test.helpers.state import next_epoch


def run_proposer_slashing_processing(spec, state, proposer_slashing, valid=True):
    """
    Run ``process_proposer_slashing``, yielding:
      - pre-state ('pre')
      - proposer_slashing ('proposer_slashing')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    pre_state = state.copy()

    yield "pre", state
    yield "proposer_slashing", proposer_slashing

    if not valid:
        expect_assertion_error(
            lambda: spec.process_proposer_slashing(state, proposer_slashing)
        )
        yield "post", None
        return

    spec.process_proposer_slashing(state, proposer_slashing)
    yield "post", state

    slashed_proposer_index = proposer_slashing.signed_header_1.message.proposer_index
    check_proposer_slashing_effect(spec, pre_state, state, slashed_proposer_index)


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=True
    )

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)


@with_all_phases
@spec_state_test
def test_slashed_and_proposer_index_the_same(spec, state):
    # Get proposer for next slot
    block = build_empty_block_for_next_slot(spec, state)
    proposer_index = block.proposer_index

    # Create slashing for same proposer
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slashed_index=proposer_index, signed_1=True, signed_2=True
    )

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)


@with_all_phases
@spec_state_test
def test_block_header_from_future(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slot=state.slot + 5, signed_1=True, signed_2=True
    )

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_1(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=False, signed_2=True
    )
    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_2(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=False
    )
    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_1_and_2(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=False, signed_2=False
    )
    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_1_and_2_swap(spec, state):
    # Get valid signatures for the slashings
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=True
    )

    # But swap them
    signature_1 = proposer_slashing.signed_header_1.signature
    proposer_slashing.signed_header_1.signature = (
        proposer_slashing.signed_header_2.signature
    )
    proposer_slashing.signed_header_2.signature = signature_1
    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
def test_invalid_incorrect_proposer_index(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=True
    )
    # Index just too high (by 1)
    proposer_slashing.signed_header_1.message.proposer_index = len(state.validators)
    proposer_slashing.signed_header_2.message.proposer_index = len(state.validators)

    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
def test_invalid_different_proposer_indices(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=True
    )
    # set different index and sign
    header_1 = proposer_slashing.signed_header_1.message
    header_2 = proposer_slashing.signed_header_2.message
    active_indices = spec.get_active_validator_indices(
        state, spec.get_current_epoch(state)
    )
    active_indices = [i for i in active_indices if i != header_1.proposer_index]

    header_2.proposer_index = active_indices[0]
    proposer_slashing.signed_header_2 = sign_block_header(
        spec, state, header_2, privkeys[header_2.proposer_index]
    )

    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
def test_invalid_slots_of_different_epochs(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=False
    )

    # set slots to be in different epochs
    header_2 = proposer_slashing.signed_header_2.message
    proposer_index = header_2.proposer_index
    header_2.slot += spec.SLOTS_PER_EPOCH
    proposer_slashing.signed_header_2 = sign_block_header(
        spec, state, header_2, privkeys[proposer_index]
    )

    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
def test_invalid_headers_are_same_sigs_are_same(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=False
    )

    # set headers to be the same
    proposer_slashing.signed_header_2 = proposer_slashing.signed_header_1.copy()

    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
def test_invalid_headers_are_same_sigs_are_different(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=False
    )

    # set headers to be the same
    proposer_slashing.signed_header_2 = proposer_slashing.signed_header_1.copy()
    # but signatures to be different
    proposer_slashing.signed_header_2.signature = (
        proposer_slashing.signed_header_2.signature[:-1] + b"\x00"
    )

    assert (
        proposer_slashing.signed_header_1.signature
        != proposer_slashing.signed_header_2.signature
    )

    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
def test_invalid_proposer_is_not_activated(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=True
    )

    # set proposer to be not active yet
    proposer_index = proposer_slashing.signed_header_1.message.proposer_index
    state.validators[proposer_index].activation_epoch = (
        spec.get_current_epoch(state) + 1
    )

    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
def test_invalid_proposer_is_slashed(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=True
    )

    # set proposer to slashed
    proposer_index = proposer_slashing.signed_header_1.message.proposer_index
    state.validators[proposer_index].slashed = True

    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )


@with_all_phases
@spec_state_test
def test_invalid_proposer_is_withdrawn(spec, state):
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, signed_1=True, signed_2=True
    )

    # move 1 epoch into future, to allow for past withdrawable epoch
    next_epoch(spec, state)
    # set proposer withdrawable_epoch in past
    current_epoch = spec.get_current_epoch(state)
    proposer_index = proposer_slashing.signed_header_1.message.proposer_index
    state.validators[proposer_index].withdrawable_epoch = current_epoch - 1

    yield from run_proposer_slashing_processing(
        spec, state, proposer_slashing, valid=False
    )
