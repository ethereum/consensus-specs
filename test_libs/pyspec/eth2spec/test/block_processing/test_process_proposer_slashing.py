import eth2spec.phase0.spec as spec
from eth2spec.phase0.spec import (
    get_current_epoch,
    process_proposer_slashing,
)
from eth2spec.test.context import spec_state_test, expect_assertion_error, always_bls
from eth2spec.test.helpers.block_header import sign_block_header
from eth2spec.test.helpers.keys import privkeys
from eth2spec.test.helpers.proposer_slashings import get_valid_proposer_slashing
from eth2spec.test.helpers.state import get_balance


def run_proposer_slashing_processing(state, proposer_slashing, valid=True):
    """
    Run ``process_proposer_slashing``, yielding:
      - pre-state ('pre')
      - proposer_slashing ('proposer_slashing')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    yield 'pre', state
    yield 'proposer_slashing', proposer_slashing

    if not valid:
        expect_assertion_error(lambda: process_proposer_slashing(state, proposer_slashing))
        yield 'post', None
        return

    pre_proposer_balance = get_balance(state, proposer_slashing.proposer_index)

    process_proposer_slashing(state, proposer_slashing)
    yield 'post', state

    # check if slashed
    slashed_validator = state.validator_registry[proposer_slashing.proposer_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    # lost whistleblower reward
    assert (
        get_balance(state, proposer_slashing.proposer_index) <
        pre_proposer_balance
    )


@spec_state_test
def test_success(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=True, signed_2=True)

    yield from run_proposer_slashing_processing(state, proposer_slashing)


@always_bls
@spec_state_test
def test_invalid_sig_1(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=False, signed_2=True)
    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@always_bls
@spec_state_test
def test_invalid_sig_2(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=True, signed_2=False)
    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@always_bls
@spec_state_test
def test_invalid_sig_1_and_2(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=False, signed_2=False)
    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_invalid_proposer_index(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=True, signed_2=True)
    # Index just too high (by 1)
    proposer_slashing.proposer_index = len(state.validator_registry)

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_epochs_are_different(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=True, signed_2=False)

    # set slots to be in different epochs
    proposer_slashing.header_2.slot += spec.SLOTS_PER_EPOCH
    sign_block_header(state, proposer_slashing.header_2, privkeys[proposer_slashing.proposer_index])

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_headers_are_same(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=True, signed_2=False)

    # set headers to be the same
    proposer_slashing.header_2 = proposer_slashing.header_1

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_proposer_is_not_activated(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=True, signed_2=True)

    # set proposer to be not active yet
    state.validator_registry[proposer_slashing.proposer_index].activation_epoch = get_current_epoch(state) + 1

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_proposer_is_slashed(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=True, signed_2=True)

    # set proposer to slashed
    state.validator_registry[proposer_slashing.proposer_index].slashed = True

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_proposer_is_withdrawn(state):
    proposer_slashing = get_valid_proposer_slashing(state, signed_1=True, signed_2=True)

    # move 1 epoch into future, to allow for past withdrawable epoch
    state.slot += spec.SLOTS_PER_EPOCH
    # set proposer withdrawable_epoch in past
    current_epoch = get_current_epoch(state)
    proposer_index = proposer_slashing.proposer_index
    state.validator_registry[proposer_index].withdrawable_epoch = current_epoch - 1

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)
