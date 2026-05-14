from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.deposits import (
    prepare_deposit_request,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    apply_next_slots_with_attestations,
    get_genesis_forkchoice_store_and_block,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_new_validator_deposit_with_multiple_epoch_transitions(spec, state):
    """
    Test deposit processing across epochs.
    """
    # signify the eth1 bridge deprecation
    state.deposit_requests_start_index = state.eth1_deposit_index

    # yield anchor state and block
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    test_steps = []

    # (1) create deposit request for a new validator
    deposit_request = prepare_deposit_request(
        spec, len(state.validators), spec.MIN_ACTIVATION_BALANCE, signed=True
    )
    execution_requests = spec.ExecutionRequests(
        deposits=spec.List[spec.DepositRequest, spec.MAX_DEPOSIT_REQUESTS_PER_PAYLOAD](
            [deposit_request]
        ),
    )

    # Build the deposit block
    deposit_block = build_empty_block_for_next_slot(spec, state)
    deposit_bid = deposit_block.body.signed_execution_payload_bid.message
    deposit_bid.execution_requests_root = spec.hash_tree_root(execution_requests)
    deposit_bid.block_hash = state.latest_block_hash
    signed_deposit_block = state_transition_and_sign_block(spec, state, deposit_block)
    deposit_block_root = signed_deposit_block.message.hash_tree_root()

    yield from tick_and_add_block(spec, store, signed_deposit_block, test_steps)

    # Reveal the execution payload envelope carrying the deposit request
    deposit_envelope = build_signed_execution_payload_envelope(
        spec,
        state,
        deposit_block_root,
        signed_deposit_block,
        execution_requests=execution_requests,
    )
    yield from add_execution_payload(spec, store, deposit_envelope, test_steps, valid=True)

    # Pre-check that the deposit is not yet in state.pending_deposits
    assert state.pending_deposits == []

    # Build the child block that carries parent_execution_requests
    child_block = build_empty_block_for_next_slot(spec, state)
    child_block.body.parent_execution_requests = execution_requests
    signed_child_block = state_transition_and_sign_block(spec, state, child_block)

    yield from tick_and_add_block(spec, store, signed_child_block, test_steps)

    # Build the expected pending deposit
    pending_deposit = spec.PendingDeposit(
        pubkey=deposit_request.pubkey,
        withdrawal_credentials=deposit_request.withdrawal_credentials,
        amount=deposit_request.amount,
        signature=deposit_request.signature,
        slot=child_block.slot,
    )
    assert state.pending_deposits == [pending_deposit]

    # (2) finalize and process pending deposit on one fork
    slots = 4 * spec.SLOTS_PER_EPOCH - state.slot
    post_state, _, latest_block = yield from apply_next_slots_with_attestations(
        spec, state, store, slots, True, True, test_steps
    )

    # check new validator has been created
    assert post_state.pending_deposits == []
    new_validator = post_state.validators[len(post_state.validators) - 1]
    assert new_validator.pubkey == pending_deposit.pubkey
    assert new_validator.withdrawal_credentials == pending_deposit.withdrawal_credentials

    # (3) create a conflicting block that triggers deposit processing on another fork
    prev_epoch_ancestor = store.blocks[latest_block.message.parent_root]
    # important to skip last block of the epoch to make client do the epoch processing
    # otherwise, client can read the post-epoch from cache
    prev_epoch_ancestor = store.blocks[prev_epoch_ancestor.parent_root]
    another_fork_state = store.block_states[prev_epoch_ancestor.hash_tree_root()].copy()

    assert another_fork_state.pending_deposits == [pending_deposit]

    # skip a slot to create and process a fork block
    next_slot(spec, another_fork_state)
    post_state, _, _ = yield from apply_next_slots_with_attestations(
        spec, another_fork_state, store, 1, True, True, test_steps
    )

    # check new validator has been created on another fork
    assert post_state.pending_deposits == []
    new_validator = post_state.validators[len(post_state.validators) - 1]
    assert new_validator.pubkey == pending_deposit.pubkey
    assert new_validator.withdrawal_credentials == pending_deposit.withdrawal_credentials

    yield "steps", test_steps
