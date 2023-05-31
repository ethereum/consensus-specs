from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_slot,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.context import (
    spec_state_test,
    with_eip6988_and_later,
)
from copy import deepcopy


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
