import pytest

from eth_consensus_specs.test.helpers.deposits import build_deposit_data
from eth_consensus_specs.test.helpers.keys import privkeys, pubkeys
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
    pubkey=None,
    withdrawal_credentials=None,
    amount=None,
    signed=False,
):
    """
    Prepare a validator deposit request operation with configurable parameters.

    This helper creates a DepositRequest object. process_deposit_request sets
    deposit_requests_start_index if UNSET (Electra only) and appends a
    PendingDeposit.

    Args:
        spec: The spec object.
        state: The beacon state to modify.
        advance_epochs: Number of epochs to advance before setup.
        validator_index: Index for pubkey lookup. If None, uses len(state.validators) for new
            validator.
        pubkey: Explicit BLSPubkey. Default: derived from validator_index.
        withdrawal_credentials: Explicit Bytes32 credentials. Default: BLS prefix (0x00) +
            hash(pubkey)[1:].
        amount: Deposit amount in Gwei. Default: MIN_ACTIVATION_BALANCE.
        signed: If True, sign with valid BLS signature.

    Returns:
        DepositRequest: The deposit request.
    """
    # Phase 1: Advance epochs if requested (before setup)
    if advance_epochs is not None:
        for _ in range(advance_epochs):
            next_epoch(spec, state)

    # Phase 2: Derive effective values
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

    # Phase 3: Build deposit data and optionally sign
    deposit_data = build_deposit_data(
        spec,
        effective_pubkey,
        effective_privkey,
        effective_amount,
        effective_withdrawal_credentials,
        signed=signed,
    )

    # Phase 4: Build deposit request object
    deposit_request = spec.DepositRequest(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        index=0,
    )

    return deposit_request


def assert_process_deposit_request(
    spec,
    state,
    pre_state,
    deposit_request=None,
    state_unchanged=False,
    expected_deposit_requests_start_index=None,
    expected_pending_deposit_pubkey=None,
    expected_pending_deposit_amount=None,
    expected_pending_deposit_slot=None,
    expected_pending_deposit_credentials=None,
):
    """
    Assert expected outcomes from process_deposit_request (validator deposits).

    INVARIANT CHECKS (always run):
    - pending_deposits increases by exactly 1
    - New pending deposit has correct pubkey, withdrawal_credentials, amount, signature
    - New pending deposit slot equals state.slot
    - deposit_requests_start_index is set only if previously UNSET (Electra only)
    - Validator count unchanged (validators created during epoch processing)
    - Balances unchanged (balance applied during epoch processing)

    TEST-SPECIFIC CHECKS (controlled by parameters):
    - expected_deposit_requests_start_index: Exact value check
    - expected_pending_deposit_*: Check specific fields of the new deposit

    Args:
        spec: The spec module for the fork being tested
        state: State after deposit request was processed
        pre_state: State before deposit request was processed
        deposit_request: The deposit request that was processed (required for invariant checks)
        state_unchanged: If True, asserts state equals pre_state (for rejected requests)
        expected_deposit_requests_start_index: Expected value of deposit_requests_start_index
        expected_pending_deposit_pubkey: Expected pubkey of new pending deposit
        expected_pending_deposit_amount: Expected amount of new pending deposit
        expected_pending_deposit_slot: Expected slot of new pending deposit
        expected_pending_deposit_credentials: Expected withdrawal_credentials of new pending deposit
    """
    if state_unchanged:
        assert state == pre_state, "Expected state to be unchanged after rejected deposit request"
        return

    # Invariant checks require deposit_request
    assert deposit_request is not None, "deposit_request required when state_unchanged=False"

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
    assert new_pending_deposit.withdrawal_credentials == deposit_request.withdrawal_credentials, (
        "Pending deposit withdrawal_credentials must match deposit request"
    )
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

    # INVARIANT: deposit_requests_start_index is set only if it was previously UNSET
    was_unset = pre_state.deposit_requests_start_index == spec.UNSET_DEPOSIT_REQUESTS_START_INDEX
    if was_unset:
        # Should be set to deposit_request.index
        assert state.deposit_requests_start_index == deposit_request.index, (
            f"deposit_requests_start_index should be set to request index: "
            f"expected={deposit_request.index}, got={state.deposit_requests_start_index}"
        )
    else:
        # Should remain unchanged
        assert state.deposit_requests_start_index == pre_state.deposit_requests_start_index, (
            "deposit_requests_start_index should not change when already set"
        )

    # INVARIANT: Validator count unchanged (new validators created during epoch processing)
    assert len(state.validators) == len(pre_state.validators), (
        "Validator count should not change during deposit request processing"
    )

    # INVARIANT: Balances unchanged (balance applied during epoch processing)
    assert list(state.balances) == list(pre_state.balances), (
        "Balances should not change during deposit request processing"
    )

    # Test-specific checks
    if expected_pending_deposit_pubkey is not None:
        assert new_pending_deposit.pubkey == expected_pending_deposit_pubkey

    if expected_pending_deposit_amount is not None:
        assert new_pending_deposit.amount == expected_pending_deposit_amount

    if expected_pending_deposit_slot is not None:
        assert new_pending_deposit.slot == expected_pending_deposit_slot

    if expected_pending_deposit_credentials is not None:
        assert new_pending_deposit.withdrawal_credentials == expected_pending_deposit_credentials

    if expected_deposit_requests_start_index is not None:
        assert state.deposit_requests_start_index == expected_deposit_requests_start_index, (
            f"deposit_requests_start_index: expected={expected_deposit_requests_start_index}, "
            f"got={state.deposit_requests_start_index}"
        )
