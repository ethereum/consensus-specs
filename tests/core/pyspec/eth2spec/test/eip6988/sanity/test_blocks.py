from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_slot,
    next_epoch_via_signed_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.context import (
    spec_state_test,
    with_eip6988_and_later,
)
from copy import deepcopy
from eth2spec.test.helpers.proposer_slashings import get_valid_proposer_slashing


@with_eip6988_and_later
@spec_state_test
def test_slashed_proposer_with_lack_of_effective_balance(spec, state):
    advanced_state = deepcopy(state)
    next_slot(spec, advanced_state)
    proposer_index = spec.get_beacon_proposer_index(advanced_state)

    state.validators[proposer_index].effective_balance = spec.config.EJECTION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[proposer_index] = state.validators[proposer_index].effective_balance
    state.validators[proposer_index].slashed = True

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    assert proposer_index != block.proposer_index

    yield 'blocks', [signed_block]
    yield 'post', state


@with_eip6988_and_later
@spec_state_test
def test_slashed_validator_is_not_proposing_block(spec, state):
    advanced_state = deepcopy(state)
    next_slot(spec, advanced_state)
    proposer_index = spec.get_beacon_proposer_index(advanced_state)

    state.validators[proposer_index].slashed = True

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    assert proposer_index != block.proposer_index

    yield 'blocks', [signed_block]
    yield 'post', state


@with_eip6988_and_later
@spec_state_test
def test_proposer_shuffling_changes_within_epoch(spec, state):
    yield 'pre', state

    blocks = []

    # Transition to next epoch
    signed_block = next_epoch_via_signed_block(spec, state)
    blocks.append(signed_block)

    # Advance a state to get proposer index
    advanced_state = deepcopy(state)
    next_slot(spec, advanced_state)
    next_slot(spec, advanced_state)
    proposer_index = spec.get_beacon_proposer_index(advanced_state)

    # Slash proposer of the next slot
    block = build_empty_block_for_next_slot(spec, state)
    proposer_slashing = get_valid_proposer_slashing(spec, state,
                                                    slashed_index=proposer_index,
                                                    signed_1=True, signed_2=True)
    block.body.proposer_slashings.append(proposer_slashing)
    signed_block = state_transition_and_sign_block(spec, state, block)
    blocks.append(signed_block)

    # Check that proposer of the next slot is changed
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    blocks.append(signed_block)

    assert proposer_index != block.proposer_index

    yield 'blocks', [signed_block]
    yield 'post', state
