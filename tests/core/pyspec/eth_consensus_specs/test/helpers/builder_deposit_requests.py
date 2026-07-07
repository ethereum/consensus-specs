from eth_consensus_specs.test.helpers.deposits import sign_builder_deposit_request
from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey, builder_pubkeys
from eth_consensus_specs.test.helpers.state import next_epoch


def run_builder_deposit_request_processing(spec, state, builder_deposit_request):
    """
    Run process_builder_deposit_request, yielding pre/post states for test vectors.

    The function never raises. Requests that fail a precondition are consumed
    without changing the state.
    """
    yield "pre", state
    yield "builder_deposit_request", builder_deposit_request

    spec.process_builder_deposit_request(state, builder_deposit_request)
    yield "post", state


def prepare_process_builder_deposit_request(
    spec,
    state,
    advance_epochs=None,
    builder_index=None,
    pubkey=None,
    withdrawal_credentials=None,
    amount=None,
    signed=False,
    builders=None,
    builder_modifications=None,
):
    """
    Prepare a builder deposit request operation with configurable parameters.

    This helper creates a BuilderDepositRequest object and optionally modifies
    state fields related to builder deposit request processing.

    Args:
        spec: The spec object.
        state: The beacon state to modify.
        advance_epochs: Number of epochs to advance before setup.
        builder_index: Index for builder pubkey lookup. Default: len(state.builders)
            (a new builder).
        pubkey: Explicit BLSPubkey. Default: derived from builder_index.
        withdrawal_credentials: Explicit Bytes32 credentials. Default:
            PAYLOAD_BUILDER_VERSION followed by an eth1 address derived from the pubkey.
        amount: Deposit amount in Gwei. Default: MIN_ACTIVATION_BALANCE.
        signed: If True, sign with a valid builder deposit signature.
        builders: Override state.builders list entirely. Use [] for empty registry.
        builder_modifications: Dict mapping builder index to dict of field modifications.
            Supported fields: "withdrawable_epoch", "balance".
            Example: {0: {"withdrawable_epoch": 5, "balance": 0}} sets builder[0]
            to withdrawable at epoch 5 with zero balance.
            Use "current_epoch" as a special value to set to current epoch.
            Use "current_epoch-1" or "current_epoch+1" for relative epochs.

    Returns:
        BuilderDepositRequest: The builder deposit request.
    """
    # Phase 1: Advance epochs if requested (before setup)
    if advance_epochs is not None:
        for _ in range(advance_epochs):
            next_epoch(spec, state)

    # Phase 2: Derive effective values
    index = builder_index if builder_index is not None else len(state.builders)
    effective_pubkey = pubkey if pubkey is not None else builder_pubkeys[index]
    effective_privkey = builder_pubkey_to_privkey[effective_pubkey]
    effective_amount = amount if amount is not None else spec.MIN_ACTIVATION_BALANCE
    if withdrawal_credentials is not None:
        effective_withdrawal_credentials = withdrawal_credentials
    else:
        # Payload builder version followed by an eth1 address derived from the pubkey
        effective_withdrawal_credentials = (
            bytes([spec.PAYLOAD_BUILDER_VERSION])
            + b"\x00" * 11
            + spec.hash(effective_pubkey)[12:]
        )

    # Phase 3: Apply state overrides (before creating request)
    if builders is not None:
        state.builders = builders

    if builder_modifications is not None:
        current_epoch = spec.get_current_epoch(state)
        for idx, mods in builder_modifications.items():
            if "withdrawable_epoch" in mods:
                epoch_value = mods["withdrawable_epoch"]
                # Support special string values for relative epochs
                if epoch_value == "current_epoch":
                    epoch_value = current_epoch
                elif epoch_value == "current_epoch-1":
                    epoch_value = current_epoch - 1
                elif epoch_value == "current_epoch+1":
                    epoch_value = current_epoch + 1
                state.builders[idx].withdrawable_epoch = epoch_value
            if "balance" in mods:
                state.builders[idx].balance = spec.Gwei(mods["balance"])

    # Phase 4: Build the request and optionally sign
    request = spec.BuilderDepositRequest(
        pubkey=effective_pubkey,
        withdrawal_credentials=effective_withdrawal_credentials,
        amount=effective_amount,
    )
    if signed:
        request.signature = sign_builder_deposit_request(spec, request, effective_privkey)

    return request


def assert_process_builder_deposit_request(
    spec,
    state,
    pre_state,
    builder_deposit_request,
    state_unchanged=False,
    expected_builder_balance=None,
    expected_builder_balance_delta=None,
    expected_builder_count=None,
    expected_builder_index=None,
    expected_execution_address=None,
    expected_builder_withdrawable_epoch=None,
    slot_reused=None,
):
    """
    Assert expected outcomes from process_builder_deposit_request.

    TEST-SPECIFIC CHECKS (controlled by parameters):
    - expected_builder_balance: Exact builder balance check
    - expected_builder_balance_delta: Builder balance change check
    - expected_builder_count: Exact builder count check
    - expected_builder_index: Verify builder at specific index
    - expected_execution_address: Verify builder's execution_address
    - expected_builder_withdrawable_epoch: Expected withdrawable_epoch of the builder
    - slot_reused: True = count same (slot reused), False = count +1 (new slot).
      When False, also verifies original builders are unchanged.

    Args:
        spec: The spec module for the fork being tested
        state: State after the builder deposit request was processed
        pre_state: State before the builder deposit request was processed
        builder_deposit_request: The request that was processed
        state_unchanged: If True, asserts state equals pre_state
    """
    if state_unchanged:
        assert state == pre_state, (
            "Expected state to be unchanged after rejected builder deposit request"
        )
        return

    # Find the builder by pubkey
    builder_index = None
    for i, builder in enumerate(state.builders):
        if builder.pubkey == builder_deposit_request.pubkey:
            builder_index = i
            break

    assert builder_index is not None, (
        f"Builder with pubkey {builder_deposit_request.pubkey[:8]}... should exist after deposit"
    )

    # Check if this was a new builder or top-up
    pre_builder_index = None
    for i, builder in enumerate(pre_state.builders):
        if builder.pubkey == builder_deposit_request.pubkey:
            pre_builder_index = i
            break

    if pre_builder_index is None:
        # New builder was created (could be appended or reused slot)
        # The count either increases by 1 (append) or stays the same (slot reuse)
        # If slot_reused is specified, that takes precedence for the check
        if slot_reused is None:
            # Allow either case (append or reuse) if not explicitly specified
            assert len(state.builders) >= len(pre_state.builders), (
                "Builder count should not decrease for new builder deposit"
            )
    else:
        # Top-up of existing builder
        assert len(state.builders) == len(pre_state.builders), (
            "Builder count should not change for top-up deposit"
        )
        # Balance should increase
        pre_balance = pre_state.builders[pre_builder_index].balance
        post_balance = state.builders[builder_index].balance
        assert post_balance == pre_balance + builder_deposit_request.amount, (
            f"Builder balance should increase by deposit amount: "
            f"pre={pre_balance}, post={post_balance}, amount={builder_deposit_request.amount}"
        )
        # All other builders should remain unchanged
        for i in range(len(pre_state.builders)):
            if i != pre_builder_index:
                assert state.builders[i] == pre_state.builders[i], (
                    f"Builder at index {i} should be unchanged during top-up"
                )

    # Test-specific checks
    if expected_builder_balance is not None:
        assert state.builders[builder_index].balance == expected_builder_balance

    if expected_builder_balance_delta is not None:
        if pre_builder_index is not None:
            pre_balance = pre_state.builders[pre_builder_index].balance
        else:
            pre_balance = 0
        assert state.builders[builder_index].balance == pre_balance + expected_builder_balance_delta

    if expected_builder_count is not None:
        assert len(state.builders) == expected_builder_count, (
            f"expected_builder_count: expected={expected_builder_count}, got={len(state.builders)}"
        )

    if expected_builder_index is not None:
        assert builder_index == expected_builder_index, (
            f"expected_builder_index: expected={expected_builder_index}, got={builder_index}"
        )

    if expected_execution_address is not None:
        assert state.builders[builder_index].execution_address == expected_execution_address, (
            f"expected_execution_address: expected={expected_execution_address}, "
            f"got={state.builders[builder_index].execution_address}"
        )

    if expected_builder_withdrawable_epoch is not None:
        assert (
            state.builders[builder_index].withdrawable_epoch == expected_builder_withdrawable_epoch
        ), (
            f"expected_builder_withdrawable_epoch: expected={expected_builder_withdrawable_epoch}, "
            f"got={state.builders[builder_index].withdrawable_epoch}"
        )

    if slot_reused is True:
        assert len(state.builders) == len(pre_state.builders), (
            f"slot_reused=True: builder count should be unchanged: "
            f"pre={len(pre_state.builders)}, post={len(state.builders)}"
        )
        # Verify exactly one original builder was replaced and it met reuse criteria
        changed_indices = [
            i for i in range(len(pre_state.builders)) if state.builders[i] != pre_state.builders[i]
        ]
        assert len(changed_indices) == 1, (
            f"slot_reused=True: exactly one builder should change: "
            f"changed_indices={changed_indices}"
        )
        reused_idx = changed_indices[0]
        pre_builder = pre_state.builders[reused_idx]
        current_epoch = spec.get_current_epoch(pre_state)
        assert pre_builder.withdrawable_epoch <= current_epoch, (
            f"slot_reused=True: reused builder at index {reused_idx} must have "
            f"withdrawable_epoch <= current_epoch: "
            f"withdrawable_epoch={pre_builder.withdrawable_epoch}, current_epoch={current_epoch}"
        )
        assert pre_builder.balance == 0, (
            f"slot_reused=True: reused builder at index {reused_idx} must have "
            f"zero balance: balance={pre_builder.balance}"
        )
    elif slot_reused is False:
        assert len(state.builders) == len(pre_state.builders) + 1, (
            f"slot_reused=False: builder count should increase by 1: "
            f"pre={len(pre_state.builders)}, post={len(state.builders)}"
        )
        # Verify original builders are unchanged when new builder is appended
        for i in range(len(pre_state.builders)):
            assert state.builders[i] == pre_state.builders[i], (
                f"slot_reused=False: original builder at index {i} should be unchanged"
            )
