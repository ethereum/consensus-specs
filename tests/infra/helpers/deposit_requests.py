import pytest

from eth_consensus_specs.test.helpers.deposits import build_deposit_data
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.keys import (
    builder_pubkey_to_privkey,
    builder_pubkeys,
    privkeys,
    pubkeys,
)
from eth_consensus_specs.test.helpers.state import next_epoch


def run_deposit_request_processing(spec, state, deposit_request, valid=True):
    """
    Run process_deposit_request, yielding pre/post states for test vectors.

    Args:
        spec: The spec object
        state: The beacon state (modified in place)
        deposit_request: The deposit request operation
        valid: If True, expect success. If False, expect error (AssertionError).
    """
    yield "pre", state
    yield "deposit_request", deposit_request

    if valid:
        spec.process_deposit_request(state, deposit_request)
        yield "post", state
    else:
        with pytest.raises(AssertionError):
            spec.process_deposit_request(state, deposit_request)
        yield "post", None


def prepare_process_deposit_request(
    spec,
    state,
    advance_epochs=None,
    validator_index=None,
    builder_index=None,
    pubkey=None,
    withdrawal_credentials=None,
    amount=None,
    signed=False,
    for_builder=False,
    builders=None,
    builder_modifications=None,
):
    """
    Prepare a deposit request operation with configurable parameters.

    This helper creates a DepositRequest object and optionally modifies
    state fields related to deposit request processing.

    The process_deposit_request function behavior varies by fork:
    - Electra/Fulu: Sets deposit_requests_start_index if UNSET, appends PendingDeposit
    - Gloas+: For builder deposits (0x03 prefix or existing builder pubkey), applies
      deposit immediately via apply_deposit_for_builder. For validator deposits,
      appends PendingDeposit (does NOT set deposit_requests_start_index).

    Args:
        spec: The spec object.
        state: The beacon state to modify.
        advance_epochs: Number of epochs to advance before setup.
        validator_index: Index for pubkey lookup. If None, uses len(state.validators) for new
            validator. Ignored if for_builder=True or builder_index is set.
        builder_index: Index for builder pubkey lookup. If set, implies for_builder=True.
            If None with for_builder=True, uses len(state.builders).
        pubkey: Explicit BLSPubkey. Default: derived from validator_index or builder_index.
        withdrawal_credentials: Explicit Bytes32 credentials. Default: BLS prefix (0x00) for
            validators, Builder prefix (0x03) for builders.
        amount: Deposit amount in Gwei. Default: MIN_ACTIVATION_BALANCE.
        signed: If True, sign with valid BLS signature.
        for_builder: If True, create a builder deposit using builder keys and
            BUILDER_WITHDRAWAL_PREFIX (Gloas+).
        builders: Override state.builders list entirely. Use [] for empty registry.
        builder_modifications: Dict mapping builder index to dict of field modifications.
            Supported fields: "withdrawable_epoch", "balance".
            Example: {0: {"withdrawable_epoch": 5, "balance": 0}} sets builder[0]
            to withdrawable at epoch 5 with zero balance.
            Use "current_epoch" as a special value to set to current epoch.
            Use "current_epoch-1" or "current_epoch+1" for relative epochs.

    Returns:
        DepositRequest: The deposit request.
    """
    # Phase 1: Advance epochs if requested (before setup)
    if advance_epochs is not None:
        for _ in range(advance_epochs):
            next_epoch(spec, state)

    # Phase 2: Determine if this is a builder deposit
    is_builder_deposit = for_builder or builder_index is not None

    # Phase 3: Derive effective values based on deposit type
    if is_builder_deposit:
        # Builder deposit: use builder keys
        index = builder_index if builder_index is not None else len(state.builders)
        effective_pubkey = pubkey if pubkey is not None else builder_pubkeys[index]
        effective_privkey = builder_pubkey_to_privkey[effective_pubkey]
        effective_amount = amount if amount is not None else spec.MIN_ACTIVATION_BALANCE

        # Default withdrawal credentials: Builder prefix (0x03)
        if withdrawal_credentials is not None:
            effective_withdrawal_credentials = withdrawal_credentials
        else:
            effective_withdrawal_credentials = (
                spec.BUILDER_WITHDRAWAL_PREFIX
                + b"\x00" * 11
                + spec.hash(effective_pubkey)[12:]  # 20-byte eth1 address
            )
    else:
        # Validator deposit: use validator keys
        index = validator_index if validator_index is not None else len(state.validators)
        effective_pubkey = pubkey if pubkey is not None else pubkeys[index]
        effective_privkey = privkeys[index]
        effective_amount = amount if amount is not None else spec.MIN_ACTIVATION_BALANCE

        # Default withdrawal credentials: BLS prefix + hash(pubkey)[1:]
        if withdrawal_credentials is not None:
            effective_withdrawal_credentials = withdrawal_credentials
        else:
            effective_withdrawal_credentials = (
                spec.BLS_WITHDRAWAL_PREFIX + spec.hash(effective_pubkey)[1:]
            )

    # Phase 4: Apply state overrides (before creating request)
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

    # Phase 5: Build deposit data and optionally sign
    deposit_data = build_deposit_data(
        spec,
        effective_pubkey,
        effective_privkey,
        effective_amount,
        effective_withdrawal_credentials,
        signed=signed,
    )

    # Phase 6: Build deposit request object
    deposit_request = spec.DepositRequest(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        index=0,
    )

    return deposit_request


def _is_builder_deposit(spec, pre_state, deposit_request):
    """Check if request routes to builder path under Gloas+ deposit routing rules."""
    if not is_post_gloas(spec):
        return False
    builder_pubkeys = {builder.pubkey for builder in pre_state.builders}
    validator_pubkeys = {v.pubkey for v in pre_state.validators}
    is_builder = deposit_request.pubkey in builder_pubkeys
    is_validator = deposit_request.pubkey in validator_pubkeys
    return is_builder or (
        spec.is_builder_withdrawal_credential(deposit_request.withdrawal_credentials)
        and not is_validator
        and not spec.is_pending_validator(pre_state, deposit_request.pubkey)
    )


def assert_process_deposit_request(
    spec,
    state,
    pre_state,
    deposit_request=None,
    state_unchanged=False,
    is_builder_deposit=None,
    expected_deposit_requests_start_index=None,
    expected_pending_deposit_pubkey=None,
    expected_pending_deposit_amount=None,
    expected_pending_deposit_slot=None,
    expected_pending_deposit_credentials=None,
    expected_builder_balance=None,
    expected_builder_balance_delta=None,
    expected_builder_count=None,
    expected_builder_index=None,
    expected_execution_address=None,
    expected_builder_withdrawable_epoch=None,
    slot_reused=None,
):
    """
    Assert expected outcomes from process_deposit_request.

    INVARIANT CHECKS FOR VALIDATOR DEPOSITS (always run):
    - pending_deposits increases by exactly 1
    - New pending deposit has correct pubkey, withdrawal_credentials, amount, signature
    - New pending deposit slot equals state.slot
    - deposit_requests_start_index is set only if previously UNSET (Electra/Fulu only)
    - Validator count unchanged (validators created during epoch processing)
    - Balances unchanged (balance applied during epoch processing)

    INVARIANT CHECKS FOR BUILDER DEPOSITS (Gloas+):
    - pending_deposits unchanged (builder deposits applied immediately)
    - Builder balance increases by deposit amount
    - New builder created if pubkey didn't exist

    TEST-SPECIFIC CHECKS (controlled by parameters):
    - expected_deposit_requests_start_index: Exact value check
    - expected_pending_deposit_*: Check specific fields of the new deposit
    - expected_builder_balance: Exact builder balance check
    - expected_builder_balance_delta: Builder balance change check
    - expected_builder_count: Exact builder count check
    - expected_builder_index: Verify builder at specific index
    - expected_execution_address: Verify builder's execution_address
    - expected_builder_withdrawable_epoch: Expected withdrawable_epoch of new builder
    - slot_reused: True = count same (slot reused), False = count +1 (new slot).
      When False, also verifies original builders are unchanged.

    Args:
        spec: The spec module for the fork being tested
        state: State after deposit request was processed
        pre_state: State before deposit request was processed
        deposit_request: The deposit request that was processed (required for invariant checks)
        state_unchanged: If True, asserts state equals pre_state (for rejected requests)
        is_builder_deposit: If True, use builder deposit assertions. Auto-detected if None.
        expected_deposit_requests_start_index: Expected value of deposit_requests_start_index
        expected_pending_deposit_pubkey: Expected pubkey of new pending deposit
        expected_pending_deposit_amount: Expected amount of new pending deposit
        expected_pending_deposit_slot: Expected slot of new pending deposit
        expected_pending_deposit_credentials: Expected withdrawal_credentials of new pending deposit
        expected_builder_balance: Expected balance of the builder after deposit
        expected_builder_balance_delta: Expected change in builder balance
        expected_builder_count: Expected exact count of builders after deposit
        expected_builder_index: Expected index of the builder (for verifying slot reuse)
        expected_execution_address: Expected execution_address of the new builder
        expected_builder_withdrawable_epoch: Expected withdrawable_epoch of the builder
        slot_reused: If True, assert builder count unchanged; if False, assert +1
            and verify all original builders are unchanged
    """
    if state_unchanged:
        assert state == pre_state, "Expected state to be unchanged after rejected deposit request"
        return

    # Invariant checks require deposit_request
    assert deposit_request is not None, "deposit_request required when state_unchanged=False"

    # Auto-detect builder deposit if not specified
    if is_builder_deposit is None:
        is_builder_deposit = _is_builder_deposit(spec, pre_state, deposit_request)

    if is_builder_deposit and is_post_gloas(spec):
        # BUILDER DEPOSIT ASSERTIONS (Gloas+)
        # Builder deposits are applied immediately, not queued

        # INVARIANT: pending_deposits unchanged for builder deposits
        assert len(state.pending_deposits) == len(pre_state.pending_deposits), (
            f"pending_deposits should not change for builder deposits: "
            f"pre={len(pre_state.pending_deposits)}, post={len(state.pending_deposits)}"
        )

        # Find the builder by pubkey
        builder_index = None
        for i, builder in enumerate(state.builders):
            if builder.pubkey == deposit_request.pubkey:
                builder_index = i
                break

        assert builder_index is not None, (
            f"Builder with pubkey {deposit_request.pubkey[:8]}... should exist after deposit"
        )

        # Check if this was a new builder or top-up
        pre_builder_index = None
        for i, builder in enumerate(pre_state.builders):
            if builder.pubkey == deposit_request.pubkey:
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
            assert post_balance == pre_balance + deposit_request.amount, (
                f"Builder balance should increase by deposit amount: "
                f"pre={pre_balance}, post={post_balance}, amount={deposit_request.amount}"
            )
            # All other builders should remain unchanged
            for i in range(len(pre_state.builders)):
                if i != pre_builder_index:
                    assert state.builders[i] == pre_state.builders[i], (
                        f"Builder at index {i} should be unchanged during top-up"
                    )

        # INVARIANT: Validator count unchanged
        assert len(state.validators) == len(pre_state.validators), (
            "Validator count should not change during builder deposit processing"
        )

        # INVARIANT: Validator balances unchanged
        assert list(state.balances) == list(pre_state.balances), (
            "Validator balances should not change during builder deposit processing"
        )

        # Test-specific checks for builders
        if expected_builder_balance is not None:
            assert state.builders[builder_index].balance == expected_builder_balance

        if expected_builder_balance_delta is not None:
            if pre_builder_index is not None:
                pre_balance = pre_state.builders[pre_builder_index].balance
            else:
                pre_balance = 0
            assert (
                state.builders[builder_index].balance
                == pre_balance + expected_builder_balance_delta
            )

        if expected_builder_count is not None:
            assert len(state.builders) == expected_builder_count, (
                f"expected_builder_count: expected={expected_builder_count}, "
                f"got={len(state.builders)}"
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
                state.builders[builder_index].withdrawable_epoch
                == expected_builder_withdrawable_epoch
            ), (
                f"expected_builder_withdrawable_epoch: expected={expected_builder_withdrawable_epoch}, "
                f"got={state.builders[builder_index].withdrawable_epoch}"
            )

        if slot_reused is True:
            assert len(state.builders) == len(pre_state.builders), (
                f"slot_reused=True: builder count should be unchanged: "
                f"pre={len(pre_state.builders)}, post={len(state.builders)}"
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

    else:
        # VALIDATOR DEPOSIT ASSERTIONS

        # INVARIANT: pending_deposits increases by exactly 1
        assert len(state.pending_deposits) == len(pre_state.pending_deposits) + 1, (
            f"pending_deposits should increase by 1: "
            f"pre={len(pre_state.pending_deposits)}, post={len(state.pending_deposits)}"
        )

        # INVARIANT: New pending deposit matches deposit request fields
        # Use len()-1 as SSZ Lists may not support negative indexing
        new_pending_deposit = state.pending_deposits[len(state.pending_deposits) - 1]

        assert new_pending_deposit.pubkey == deposit_request.pubkey, (
            "Pending deposit pubkey must match deposit request"
        )
        assert (
            new_pending_deposit.withdrawal_credentials == deposit_request.withdrawal_credentials
        ), "Pending deposit withdrawal_credentials must match deposit request"
        assert new_pending_deposit.amount == deposit_request.amount, (
            "Pending deposit amount must match deposit request"
        )
        assert new_pending_deposit.signature == deposit_request.signature, (
            "Pending deposit signature must match deposit request"
        )

        # INVARIANT: New pending deposit slot equals state.slot (at time of processing)
        assert new_pending_deposit.slot == state.slot, (
            f"Pending deposit slot must equal state.slot: "
            f"deposit.slot={new_pending_deposit.slot}, state.slot={state.slot}"
        )

        # INVARIANT: deposit_requests_start_index logic (Electra/Fulu only, removed in Gloas)
        if not is_post_gloas(spec):
            was_unset = (
                pre_state.deposit_requests_start_index == spec.UNSET_DEPOSIT_REQUESTS_START_INDEX
            )
            if was_unset:
                # Should be set to deposit_request.index
                assert state.deposit_requests_start_index == deposit_request.index, (
                    f"deposit_requests_start_index should be set to request index: "
                    f"expected={deposit_request.index}, got={state.deposit_requests_start_index}"
                )
            else:
                # Should remain unchanged
                assert (
                    state.deposit_requests_start_index == pre_state.deposit_requests_start_index
                ), "deposit_requests_start_index should not change when already set"
        else:
            # In Gloas+, deposit_requests_start_index is not modified by process_deposit_request
            assert state.deposit_requests_start_index == pre_state.deposit_requests_start_index, (
                "deposit_requests_start_index should not change in Gloas+"
            )

        # INVARIANT: Builder count unchanged
        assert len(state.builders) == len(pre_state.builders), (
            "Builder count should not change during validator deposit processing"
        )

        # INVARIANT: Validator count unchanged (new validators created during epoch processing)
        assert len(state.validators) == len(pre_state.validators), (
            "Validator count should not change during deposit request processing"
        )

        # INVARIANT: Balances unchanged (balance applied during epoch processing)
        assert list(state.balances) == list(pre_state.balances), (
            "Balances should not change during deposit request processing"
        )

        # Test-specific checks for validators
        if expected_pending_deposit_pubkey is not None:
            assert new_pending_deposit.pubkey == expected_pending_deposit_pubkey

        if expected_pending_deposit_amount is not None:
            assert new_pending_deposit.amount == expected_pending_deposit_amount

        if expected_pending_deposit_slot is not None:
            assert new_pending_deposit.slot == expected_pending_deposit_slot

        if expected_pending_deposit_credentials is not None:
            assert (
                new_pending_deposit.withdrawal_credentials == expected_pending_deposit_credentials
            )

    # Common test-specific checks
    if expected_deposit_requests_start_index is not None:
        assert state.deposit_requests_start_index == expected_deposit_requests_start_index, (
            f"deposit_requests_start_index: expected={expected_deposit_requests_start_index}, "
            f"got={state.deposit_requests_start_index}"
        )
