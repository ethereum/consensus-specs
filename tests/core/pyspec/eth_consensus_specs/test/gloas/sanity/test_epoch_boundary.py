from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import build_empty_block
from eth_consensus_specs.test.helpers.consolidations import (
    prepare_switch_to_compounding_request,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.deposits import (
    prepare_deposit_request,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth_consensus_specs.test.helpers.withdrawals import (
    prepare_withdrawal_request,
    set_eth1_withdrawal_credential_with_balance,
)
from tests.infra.helpers.withdrawals import set_parent_block_full


def _get_last_slot_of_current_epoch(spec, state):
    epoch = spec.get_current_epoch(state)
    return (epoch + 1) * spec.SLOTS_PER_EPOCH - 1


def _setup_switch_to_compounding_validator(spec, state, validator_index):
    """
    Set up a validator with ETH1 withdrawal credentials and balance above
    MIN_ACTIVATION_BALANCE, ready for a switch-to-compounding request.

    Returns the consolidation request.
    """
    address = b"\xaa" * 20
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        address=address,
    )
    # Give the validator a balance above MIN_ACTIVATION_BALANCE so that
    # after switching to compounding, effective balance can increase.
    balance = spec.MIN_ACTIVATION_BALANCE + 3 * spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[validator_index] = balance

    consolidation_request = prepare_switch_to_compounding_request(
        spec,
        state,
        validator_index,
        address=address,
    )
    return consolidation_request


def _build_multi_request_execution_requests(
    spec,
    state,
    consolidation_validator_index,
    deposit_validator_index,
    deposit_amount,
):
    """
    Build an ExecutionRequests with a switch-to-compounding consolidation
    and a top-up deposit.
    """
    consolidation_request = _setup_switch_to_compounding_validator(
        spec, state, consolidation_validator_index
    )

    deposit_validator = state.validators[deposit_validator_index]
    deposit_request = prepare_deposit_request(
        spec,
        validator_index=deposit_validator_index,
        amount=deposit_amount,
        pubkey=deposit_validator.pubkey,
        withdrawal_credentials=deposit_validator.withdrawal_credentials,
        signed=True,
    )

    return spec.ExecutionRequests(
        consolidations=[consolidation_request],
        deposits=[deposit_request],
    )


def _build_all_requests_execution_requests(
    spec,
    state,
    consolidation_validator_index,
    exit_validator_indices,
    deposit_validator_index,
    deposit_amount,
):
    """
    Build an ExecutionRequests with all three request types. Multiple
    full-exit withdrawal requests are included so the request-processing
    loop and the exit-churn progression are both exercised within a single
    payload.
    """
    consolidation_request = _setup_switch_to_compounding_validator(
        spec, state, consolidation_validator_index
    )

    # prepare_withdrawal_request wires 0x01 credentials if the validator
    # doesn't already have execution ones. Each exit gets its own source
    # address so the requests are distinct.
    withdrawal_requests = [
        prepare_withdrawal_request(
            spec,
            state,
            exit_index,
            address=bytes([0xBB + i]) * 20,
            amount=spec.FULL_EXIT_REQUEST_AMOUNT,
        )
        for i, exit_index in enumerate(exit_validator_indices)
    ]

    deposit_validator = state.validators[deposit_validator_index]
    deposit_request = prepare_deposit_request(
        spec,
        validator_index=deposit_validator_index,
        amount=deposit_amount,
        pubkey=deposit_validator.pubkey,
        withdrawal_credentials=deposit_validator.withdrawal_credentials,
        signed=True,
    )

    return spec.ExecutionRequests(
        deposits=[deposit_request],
        withdrawals=withdrawal_requests,
        consolidations=[consolidation_request],
    )


def _assert_registry_integrity(spec, state, pre_state):
    """
    Basic registry invariants that must hold across the scenario: the
    registry does not shrink, pubkeys and activation epochs of existing
    validators are immutable, and every effective_balance respects its
    current credential cap and the EFFECTIVE_BALANCE_INCREMENT quantization.
    """
    assert len(state.validators) == len(state.balances)
    assert len(state.validators) >= len(pre_state.validators)
    for idx in range(len(pre_state.validators)):
        pre_v = pre_state.validators[idx]
        post_v = state.validators[idx]
        assert post_v.pubkey == pre_v.pubkey
        assert post_v.activation_epoch == pre_v.activation_epoch
        assert post_v.effective_balance <= spec.get_max_effective_balance(post_v)
        assert post_v.effective_balance % spec.EFFECTIVE_BALANCE_INCREMENT == 0


def _build_block_with_execution_requests(spec, state, slot, execution_requests):
    """
    Build a self-build block at ``slot`` whose bid commits to
    ``execution_requests`` via its execution_requests_root.
    """
    block = build_empty_block(spec, state, slot=slot)

    bid = block.body.signed_execution_payload_bid.message
    bid.execution_requests_root = spec.hash_tree_root(execution_requests)

    # Self-build uses G2_POINT_AT_INFINITY as the bid signature.
    if bid.builder_index == spec.BUILDER_INDEX_SELF_BUILD:
        block.body.signed_execution_payload_bid = spec.SignedExecutionPayloadBid(
            message=bid,
            signature=spec.G2_POINT_AT_INFINITY,
        )

    return block


def _build_child_block_with_parent_requests(spec, state, slot, parent_execution_requests):
    """
    Build a block at ``slot`` that carries ``parent_execution_requests``
    for a parent payload that was delivered.
    """
    block = build_empty_block(spec, state, slot=slot)
    block.body.parent_execution_requests = parent_execution_requests
    return block


def _run_epoch_boundary_full_parent(spec, state, gap_epochs):
    """
    Block at last slot of the current epoch commits a multi-request payload
    (consolidation + deposit). The payload is delivered. After ``gap_epochs``
    of missed slots, a child block processes the parent's execution requests.
    """
    set_parent_block_full(spec, state)

    # Snapshot pre-state for integrity checks
    pre_state = state.copy()

    consolidation_validator_index = 0
    deposit_validator_index = 2
    deposit_amount = 5 * spec.EFFECTIVE_BALANCE_INCREMENT

    execution_requests = _build_multi_request_execution_requests(
        spec,
        state,
        consolidation_validator_index,
        deposit_validator_index,
        deposit_amount,
    )

    pre_pending_deposits = len(state.pending_deposits)
    pre_withdrawal_index = state.next_withdrawal_index
    deposit_target_pubkey = state.validators[deposit_validator_index].pubkey
    consolidation_pubkey = state.validators[consolidation_validator_index].pubkey

    assert spec.has_eth1_withdrawal_credential(state.validators[consolidation_validator_index])
    assert state.validators[consolidation_validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

    # Block 1: last slot of the current epoch, bid commits to the requests.
    last_slot = _get_last_slot_of_current_epoch(spec, state)
    block_1 = _build_block_with_execution_requests(
        spec,
        state,
        last_slot,
        execution_requests,
    )
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    # Parent payload is delivered for Block 2.
    set_parent_block_full(spec, state)

    # Requests are processed by the child block, not by block_1.
    assert spec.has_eth1_withdrawal_credential(state.validators[consolidation_validator_index])
    assert len(state.pending_deposits) == pre_pending_deposits

    # Block 2: skip ``gap_epochs`` — including slot 0 of the epoch right after
    # block_1 — then process the parent's execution requests.
    block_1_epoch = spec.compute_epoch_at_slot(block_1.slot)
    block_2_slot = (block_1_epoch + gap_epochs) * spec.SLOTS_PER_EPOCH + 1
    block_2 = _build_child_block_with_parent_requests(
        spec,
        state,
        block_2_slot,
        execution_requests,
    )
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # Switch-to-compounding applied in block_2. The credential flipped but no
    # exit was initiated (switch-to-compounding is not an exit).
    assert spec.has_compounding_withdrawal_credential(
        state.validators[consolidation_validator_index]
    )
    assert state.validators[consolidation_validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    assert state.balances[consolidation_validator_index] <= spec.MIN_ACTIVATION_BALANCE

    # Deposit request appended to pending_deposits by block_2's block-level
    # processing. The consolidation's excess was already drained by block_1's
    # partial-withdrawal sweep (0x01 creds + max effective balance + excess
    # balance makes validator partially withdrawable), so
    # queue_excess_active_balance is a no-op when the switch runs in block_2.
    pending_pubkeys = [pd.pubkey for pd in state.pending_deposits]
    assert deposit_target_pubkey in pending_pubkeys
    assert consolidation_pubkey not in pending_pubkeys
    assert len(state.pending_deposits) >= pre_pending_deposits + 1

    # Block_1's withdrawal sweep advanced the global withdrawal index by at
    # least one (the consolidation validator's partial withdrawal).
    assert state.next_withdrawal_index >= pre_withdrawal_index + 1

    assert state.slot == block_2_slot

    _assert_registry_integrity(spec, state, pre_state)


def _run_epoch_boundary_empty_parent(spec, state, gap_epochs):
    """
    Block at last slot of the current epoch commits a multi-request payload
    in its bid, but the payload is not delivered. After ``gap_epochs`` of
    missed slots, a child block is built with empty parent_execution_requests.
    None of the committed requests take effect.
    """
    set_parent_block_full(spec, state)

    # Snapshot pre-state for integrity checks
    pre_state = state.copy()

    consolidation_validator_index = 0
    deposit_validator_index = 2
    deposit_amount = 5 * spec.EFFECTIVE_BALANCE_INCREMENT

    execution_requests = _build_multi_request_execution_requests(
        spec,
        state,
        consolidation_validator_index,
        deposit_validator_index,
        deposit_amount,
    )

    pre_pending_deposits = len(state.pending_deposits)
    pre_partial_withdrawals = len(state.pending_partial_withdrawals)
    consolidation_pubkey = state.validators[consolidation_validator_index].pubkey
    deposit_target_pubkey = state.validators[deposit_validator_index].pubkey
    pre_consolidation_exit_epoch = state.validators[consolidation_validator_index].exit_epoch
    pre_deposit_target_exit_epoch = state.validators[deposit_validator_index].exit_epoch

    assert spec.has_eth1_withdrawal_credential(state.validators[consolidation_validator_index])
    assert pre_consolidation_exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

    # Block 1: last slot of the current epoch, bid commits to the requests.
    last_slot = _get_last_slot_of_current_epoch(spec, state)
    block_1 = _build_block_with_execution_requests(
        spec,
        state,
        last_slot,
        execution_requests,
    )
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    # Payload is NOT delivered: parent stays empty.
    assert spec.has_eth1_withdrawal_credential(state.validators[consolidation_validator_index])

    # Block 2: after the gap, with empty parent_execution_requests (parent
    # payload is empty).
    block_1_epoch = spec.compute_epoch_at_slot(block_1.slot)
    block_2_slot = (block_1_epoch + gap_epochs) * spec.SLOTS_PER_EPOCH + 1
    block_2 = build_empty_block(spec, state, slot=block_2_slot)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # None of the committed requests were applied: the parent payload never
    # arrived, so process_parent_execution_requests is skipped.
    assert spec.has_eth1_withdrawal_credential(state.validators[consolidation_validator_index])
    assert (
        state.validators[consolidation_validator_index].exit_epoch == pre_consolidation_exit_epoch
    )
    assert state.validators[deposit_validator_index].exit_epoch == pre_deposit_target_exit_epoch

    pending_pubkeys = [pd.pubkey for pd in state.pending_deposits]
    assert consolidation_pubkey not in pending_pubkeys
    assert deposit_target_pubkey not in pending_pubkeys
    # Queues can only shrink (drained by epoch processing in the gap),
    # never grow from the dropped requests.
    assert len(state.pending_deposits) <= pre_pending_deposits
    assert len(state.pending_partial_withdrawals) <= pre_partial_withdrawals

    assert state.slot == block_2_slot

    _assert_registry_integrity(spec, state, pre_state)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="long gap requires many empty slots")
def test_epoch_boundary_full_parent_gap_1_epoch(spec, state):
    """
    Last-payload requests (consolidation + deposit), parent delivered, then
    1 epoch of missed slots. Next block processes the parent's requests.
    """
    yield from _run_epoch_boundary_full_parent(spec, state, gap_epochs=1)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="long gap requires many empty slots")
def test_epoch_boundary_full_parent_gap_2_epochs(spec, state):
    """
    Last-payload requests (consolidation + deposit), parent delivered, then
    2 epochs of missed slots. Next block processes the parent's requests.
    """
    yield from _run_epoch_boundary_full_parent(spec, state, gap_epochs=2)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="long gap requires many empty slots")
def test_epoch_boundary_full_parent_gap_5_epochs(spec, state):
    """
    Last-payload requests (consolidation + deposit), parent delivered, then
    5 epochs of missed slots. Next block processes the parent's requests.
    """
    yield from _run_epoch_boundary_full_parent(spec, state, gap_epochs=5)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="long gap requires many empty slots")
def test_epoch_boundary_empty_parent_gap_1_epoch(spec, state):
    """
    Last-payload requests (consolidation + deposit) committed in bid, parent
    NOT delivered, then 1 epoch of missed slots. Requests are never applied.
    """
    yield from _run_epoch_boundary_empty_parent(spec, state, gap_epochs=1)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="long gap requires many empty slots")
def test_epoch_boundary_empty_parent_gap_2_epochs(spec, state):
    """
    Last-payload requests (consolidation + deposit) committed in bid, parent
    NOT delivered, then 2 epochs of missed slots. Requests are never applied.
    """
    yield from _run_epoch_boundary_empty_parent(spec, state, gap_epochs=2)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="long gap requires many empty slots")
def test_epoch_boundary_empty_parent_gap_5_epochs(spec, state):
    """
    Last-payload requests (consolidation + deposit) committed in bid, parent
    NOT delivered, then 5 epochs of missed slots. Requests are never applied.
    """
    yield from _run_epoch_boundary_empty_parent(spec, state, gap_epochs=5)


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="epoch boundary timing requires controlled slots")
def test_switch_to_compounding_across_epoch_boundary(spec, state):
    """
    A validator with balance above MIN_ACTIVATION_BALANCE and 0x01
    credentials submits a switch-to-compounding request in the last payload
    of an epoch. The request is deferred to the next block, so the epoch
    transition runs without the credential flip. Balance-dependent
    assignments (proposer lookahead, sync committees, PTC window) are
    computed against the pre-switch effective balance, not the
    post-compounding cap.
    """
    set_parent_block_full(spec, state)

    pre_state = state.copy()

    validator_index = 0
    consolidation_request = _setup_switch_to_compounding_validator(
        spec,
        state,
        validator_index,
    )

    execution_requests = spec.ExecutionRequests(
        consolidations=[consolidation_request],
    )

    # 0x01 credentials cap effective balance at MIN_ACTIVATION_BALANCE.
    assert spec.has_eth1_withdrawal_credential(state.validators[validator_index])
    assert state.validators[validator_index].effective_balance == spec.MIN_ACTIVATION_BALANCE
    assert state.balances[validator_index] > spec.MIN_ACTIVATION_BALANCE

    # Snapshot balance-dependent assignments before the request is in flight.
    pre_current_sync_root = spec.hash_tree_root(state.current_sync_committee)
    pre_next_sync_root = spec.hash_tree_root(state.next_sync_committee)

    yield "pre", state

    # Block 1: last slot of the current epoch, bid commits to the switch.
    last_slot = _get_last_slot_of_current_epoch(spec, state)
    block_1 = _build_block_with_execution_requests(
        spec,
        state,
        last_slot,
        execution_requests,
    )
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    set_parent_block_full(spec, state)

    # The switch is committed but not yet processed.
    assert spec.has_eth1_withdrawal_credential(state.validators[validator_index])
    assert state.validators[validator_index].effective_balance == spec.MIN_ACTIVATION_BALANCE

    # Block 2: first slot of the next epoch, processes the parent's request.
    block_2 = _build_child_block_with_parent_requests(
        spec,
        state,
        last_slot + 1,
        execution_requests,
    )
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # The switch has now been applied.
    assert spec.has_compounding_withdrawal_credential(state.validators[validator_index])
    # Switch-to-compounding is not an exit.
    assert state.validators[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    assert state.balances[validator_index] <= spec.MIN_ACTIVATION_BALANCE

    # Critical property: effective_balance does not jump to the compounding
    # cap. process_effective_balance_updates ran against 0x01 credentials
    # before block_2 applied the switch, so it stays at MIN_ACTIVATION_BALANCE.
    assert state.validators[validator_index].effective_balance == spec.MIN_ACTIVATION_BALANCE

    # Note: block_1 already swept the 0x01 excess via process_withdrawals
    # (0x01 max_effective_balance == MIN_ACTIVATION_BALANCE + excess balance
    # makes the validator partially withdrawable), so block_2's
    # queue_excess_active_balance is a no-op. The deferral property still
    # holds: the credential flip and any dependent state change only happen
    # in block_2.

    # proposer_lookahead has fixed shape (MIN_SEED_LOOKAHEAD + 1) *
    # SLOTS_PER_EPOCH and each entry must reference a real validator.
    expected_lookahead_len = (spec.MIN_SEED_LOOKAHEAD + 1) * spec.SLOTS_PER_EPOCH
    assert len(state.proposer_lookahead) == expected_lookahead_len
    for proposer_index in state.proposer_lookahead:
        assert proposer_index < len(state.validators)

    # ptc_window has fixed shape (2 + MIN_SEED_LOOKAHEAD) * SLOTS_PER_EPOCH
    # of PTC-sized committees referencing real validators.
    expected_ptc_window_len = (2 + spec.MIN_SEED_LOOKAHEAD) * spec.SLOTS_PER_EPOCH
    assert len(state.ptc_window) == expected_ptc_window_len
    for ptc_slice in state.ptc_window:
        assert len(ptc_slice) == spec.PTC_SIZE
        for member_index in ptc_slice:
            assert member_index < len(state.validators)

    # With EPOCHS_PER_SYNC_COMMITTEE_PERIOD = 8 in minimal, the 0 -> 1 epoch
    # transition must not rotate the committees, and they must not have been
    # recomputed using a post-switch effective balance.
    assert spec.hash_tree_root(state.current_sync_committee) == pre_current_sync_root
    assert spec.hash_tree_root(state.next_sync_committee) == pre_next_sync_root
    assert len(state.current_sync_committee.pubkeys) == spec.SYNC_COMMITTEE_SIZE
    assert len(state.next_sync_committee.pubkeys) == spec.SYNC_COMMITTEE_SIZE

    _assert_registry_integrity(spec, state, pre_state)

    assert state.slot == last_slot + 1


@with_gloas_and_later
@spec_state_test
@with_presets([MINIMAL], reason="long gap and SHARD_COMMITTEE_PERIOD advance")
def test_epoch_boundary_full_parent_all_requests_gap_5_epochs(spec, state):
    """
    Block at last slot of an epoch commits a payload with all three
    execution request types: three full-exit withdrawals on distinct
    validators, a top-up deposit, and a switch-to-compounding consolidation.
    Payload is delivered. The next block lands after 5 epochs of missed
    slots — including slot 0 of the epoch immediately following block_1 —
    and processes the parent's execution requests. Each request type must
    be honored; the three exits must make progress through the exit-churn
    state within a single request-processing loop.
    """
    # Advance past SHARD_COMMITTEE_PERIOD so process_withdrawal_request
    # accepts the full-exit requests (each requires
    # current_epoch >= activation_epoch + SHARD_COMMITTEE_PERIOD).
    target_slot = spec.Slot(spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH)
    spec.process_slots(state, target_slot)

    set_parent_block_full(spec, state)

    pre_state = state.copy()

    consolidation_validator_index = 0
    exit_validator_indices = [4, 5, 6]
    deposit_validator_index = 2
    deposit_amount = 5 * spec.EFFECTIVE_BALANCE_INCREMENT

    execution_requests = _build_all_requests_execution_requests(
        spec,
        state,
        consolidation_validator_index,
        exit_validator_indices,
        deposit_validator_index,
        deposit_amount,
    )

    pre_pending_deposits = len(state.pending_deposits)
    pre_withdrawal_index = state.next_withdrawal_index
    pre_exit_balance_to_consume = state.exit_balance_to_consume
    pre_earliest_exit_epoch = state.earliest_exit_epoch
    deposit_target_pubkey = state.validators[deposit_validator_index].pubkey
    consolidation_pubkey = state.validators[consolidation_validator_index].pubkey

    assert spec.has_eth1_withdrawal_credential(state.validators[consolidation_validator_index])
    assert state.validators[consolidation_validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    for exit_index in exit_validator_indices:
        assert spec.has_eth1_withdrawal_credential(state.validators[exit_index])
        assert state.validators[exit_index].exit_epoch == spec.FAR_FUTURE_EPOCH

    yield "pre", state

    # Block 1: last slot of the current epoch, bid commits to all requests.
    last_slot = _get_last_slot_of_current_epoch(spec, state)
    block_1 = _build_block_with_execution_requests(
        spec,
        state,
        last_slot,
        execution_requests,
    )
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    set_parent_block_full(spec, state)

    # None of the requests have been applied yet.
    assert spec.has_eth1_withdrawal_credential(state.validators[consolidation_validator_index])
    for exit_index in exit_validator_indices:
        assert state.validators[exit_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    assert len(state.pending_deposits) == pre_pending_deposits

    # Block 2: skip 5 full epochs — including slot 0 of the epoch right after
    # block_1 — then process the parent's execution requests.
    block_1_epoch = spec.compute_epoch_at_slot(block_1.slot)
    gap_epochs = 5
    block_2_slot = (block_1_epoch + gap_epochs) * spec.SLOTS_PER_EPOCH + 1
    block_2 = _build_child_block_with_parent_requests(
        spec,
        state,
        block_2_slot,
        execution_requests,
    )
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)

    yield "blocks", [signed_block_1, signed_block_2]
    yield "post", state

    # 1) Consolidation (switch-to-compounding) applied in block_2. The
    # switch is not an exit.
    assert spec.has_compounding_withdrawal_credential(
        state.validators[consolidation_validator_index]
    )
    assert state.validators[consolidation_validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    assert state.balances[consolidation_validator_index] <= spec.MIN_ACTIVATION_BALANCE

    # 2) Each full-exit withdrawal request applied in block_2: exit is
    # scheduled, withdrawable_epoch = exit_epoch + MIN_VALIDATOR_WITHDRAWABILITY_DELAY,
    # and balance is not zeroed.
    current_epoch = spec.get_current_epoch(state)
    exit_epochs = []
    for exit_index in exit_validator_indices:
        post_exit_epoch = state.validators[exit_index].exit_epoch
        post_withdrawable_epoch = state.validators[exit_index].withdrawable_epoch
        assert post_exit_epoch < spec.FAR_FUTURE_EPOCH
        assert post_exit_epoch >= current_epoch
        assert (
            post_withdrawable_epoch
            == post_exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        )
        assert state.balances[exit_index] > 0
        exit_epochs.append(post_exit_epoch)

    # Exit-churn progression: the request-processing loop called
    # initiate_validator_exit three times in order, each consuming
    # exit-balance churn from the same state, so exit epochs must be
    # monotonically non-decreasing.
    assert exit_epochs == sorted(exit_epochs)
    # The churn state advanced — either earliest_exit_epoch moved forward
    # or exit_balance_to_consume was drawn down.
    assert (
        state.earliest_exit_epoch > pre_earliest_exit_epoch
        or state.exit_balance_to_consume < pre_exit_balance_to_consume
    )

    # 3) Deposit request appended to state.pending_deposits by block_2's
    # block-level processing. The consolidation's excess was already drained
    # by block_1's partial-withdrawal sweep, so queue_excess_active_balance
    # is a no-op and no consolidation pending-deposit entry appears.
    pending_pubkeys = [pd.pubkey for pd in state.pending_deposits]
    assert deposit_target_pubkey in pending_pubkeys
    assert consolidation_pubkey not in pending_pubkeys
    assert len(state.pending_deposits) >= pre_pending_deposits + 1

    # Block_1's withdrawal sweep advanced the global withdrawal index by at
    # least one (the consolidation validator's partial withdrawal). No
    # blocks run in the 5-epoch gap, so no additional sweeps contribute
    # there; block_2 may add more depending on state — we assert the lower
    # bound.
    assert state.next_withdrawal_index >= pre_withdrawal_index + 1

    assert state.slot == block_2_slot

    _assert_registry_integrity(spec, state, pre_state)
