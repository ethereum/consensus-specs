from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.context import (
    with_presets,
    spec_state_test,
    with_electra_until_eip7732,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash_for_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_slot,
)
from eth2spec.test.helpers.deposits import (
    prepare_deposit_request,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    tick_and_add_block,
    apply_next_slots_with_attestations,
)
from eth2spec.test.helpers.constants import (
    MINIMAL,
)


# TODO(jtraglia): In eip7732, how do we set execution requests in the payload envelope?
@with_electra_until_eip7732
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_new_validator_deposit_with_multiple_epoch_transitions(spec, state):
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
    deposit_block = build_empty_block_for_next_slot(spec, state)
    deposit_block.body.execution_requests.deposits = [deposit_request]
    deposit_block.body.execution_payload.block_hash = compute_el_block_hash_for_block(
        spec, deposit_block
    )
    signed_deposit_block = state_transition_and_sign_block(spec, state, deposit_block)

    pending_deposit = spec.PendingDeposit(
        pubkey=deposit_request.pubkey,
        withdrawal_credentials=deposit_request.withdrawal_credentials,
        amount=deposit_request.amount,
        signature=deposit_request.signature,
        slot=deposit_block.slot,
    )

    assert state.pending_deposits == [pending_deposit]

    yield from tick_and_add_block(spec, store, signed_deposit_block, test_steps)

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
