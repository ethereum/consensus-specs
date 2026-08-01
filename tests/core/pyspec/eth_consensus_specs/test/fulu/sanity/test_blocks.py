from eth_consensus_specs.test.context import spec_state_test, with_fulu_and_later
from eth_consensus_specs.test.helpers.balances import get_min_activation_balance
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.deposits import prepare_state_and_deposit
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


@with_fulu_and_later
@spec_state_test
def test_invalid_old_style_deposit_rejected(spec, state):
    # The former (Eth1 bridge) deposit mechanism is disabled from Fulu onward.
    # `process_operations` asserts that blocks carry no deposits, so
    # a block with a non-empty `body.deposits` must be rejected.
    validator_index = len(state.validators)
    amount = get_min_activation_balance(spec)
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)
    block.body.deposits.append(deposit)
    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None
