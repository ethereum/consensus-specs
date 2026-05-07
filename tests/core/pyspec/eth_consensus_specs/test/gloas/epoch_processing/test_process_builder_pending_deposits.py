from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.deposits import build_deposit_data
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.keys import (
    builder_pubkey_to_privkey,
    builder_pubkeys,
)


def _builder_withdrawal_credentials(spec, pubkey):
    return spec.BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + spec.hash(pubkey)[12:]


def _make_pending_builder_deposit(spec, pubkey, amount, slot, signed=True):
    """Create a PendingDeposit with builder withdrawal credentials."""
    privkey = builder_pubkey_to_privkey[pubkey]
    withdrawal_credentials = _builder_withdrawal_credentials(spec, pubkey)
    deposit_data = build_deposit_data(
        spec, pubkey, privkey, amount, withdrawal_credentials, signed=signed
    )
    return spec.PendingDeposit(
        pubkey=deposit_data.pubkey,
        withdrawal_credentials=deposit_data.withdrawal_credentials,
        amount=deposit_data.amount,
        signature=deposit_data.signature,
        slot=slot,
    )


def _set_finalized_to_current_epoch(spec, state):
    """Mark the current epoch's start slot as finalized so queued deposits drain."""
    state.finalized_checkpoint.epoch = spec.get_current_epoch(state)


@with_gloas_and_later
@spec_state_test
def test_process_builder_pending_deposits__empty_queue(spec, state):
    """No-op when ``pending_builder_deposits`` is empty."""
    _set_finalized_to_current_epoch(spec, state)
    state.pending_builder_deposits = []

    pre_builder_count = len(state.builders)

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_deposits")

    assert len(state.pending_builder_deposits) == 0
    assert len(state.builders) == pre_builder_count


@with_gloas_and_later
@spec_state_test
def test_process_builder_pending_deposits__creates_new_builder(spec, state):
    """A finalized, valid-signature pending builder deposit is drained and a
    new builder is added to the registry."""
    _set_finalized_to_current_epoch(spec, state)
    pre_builder_count = len(state.builders)
    amount = spec.MIN_DEPOSIT_AMOUNT

    pubkey = builder_pubkeys[pre_builder_count + 0]
    pending = _make_pending_builder_deposit(
        spec, pubkey, amount, slot=spec.GENESIS_SLOT, signed=True
    )
    state.pending_builder_deposits = [pending]

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_deposits")

    assert len(state.pending_builder_deposits) == 0
    assert len(state.builders) == pre_builder_count + 1
    assert state.builders[pre_builder_count].pubkey == pubkey
    assert state.builders[pre_builder_count].balance == amount


@with_gloas_and_later
@spec_state_test
def test_process_builder_pending_deposits__top_up_existing_builder(spec, state):
    """A pending deposit for a pubkey already in the builder registry tops up
    the existing builder's balance (no signature check needed)."""
    _set_finalized_to_current_epoch(spec, state)
    pre_builder_count = len(state.builders)
    builder_index = 0
    pubkey = state.builders[builder_index].pubkey
    pre_balance = state.builders[builder_index].balance
    amount = spec.MIN_DEPOSIT_AMOUNT

    # Top-ups don't need a valid signature for existing builders.
    pending = spec.PendingDeposit(
        pubkey=pubkey,
        withdrawal_credentials=_builder_withdrawal_credentials(spec, pubkey),
        amount=amount,
        signature=spec.bls.G2_POINT_AT_INFINITY,
        slot=spec.GENESIS_SLOT,
    )
    state.pending_builder_deposits = [pending]

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_deposits")

    assert len(state.pending_builder_deposits) == 0
    assert len(state.builders) == pre_builder_count
    assert state.builders[builder_index].balance == pre_balance + amount


@with_gloas_and_later
@spec_state_test
def test_process_builder_pending_deposits__cap_overflow(spec, state):
    """When more than ``MAX_PENDING_BUILDER_DEPOSITS_PER_EPOCH`` deposits are
    queued, exactly the cap are drained this epoch and the rest stay queued
    for subsequent epochs."""
    _set_finalized_to_current_epoch(spec, state)
    cap = spec.MAX_PENDING_BUILDER_DEPOSITS_PER_EPOCH
    overflow = 3
    pre_builder_count = len(state.builders)
    amount = spec.MIN_DEPOSIT_AMOUNT

    # All deposits unsigned: the cap is enforced regardless of signature
    # validity (apply_deposit_for_builder is still invoked, just doesn't add
    # a builder for invalid sigs). This isolates the cap mechanism.
    deposits = []
    for i in range(cap + overflow):
        pubkey = builder_pubkeys[pre_builder_count + i]
        deposits.append(
            _make_pending_builder_deposit(
                spec, pubkey, amount, slot=spec.GENESIS_SLOT, signed=False
            )
        )
    state.pending_builder_deposits = deposits

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_deposits")

    # First ``cap`` were attempted (none added since unsigned); the prefix is
    # consumed and exactly ``overflow`` entries remain at the front of the
    # queue, in their original order.
    assert len(state.pending_builder_deposits) == overflow
    assert len(state.builders) == pre_builder_count
    for i in range(overflow):
        assert (
            state.pending_builder_deposits[i].pubkey == builder_pubkeys[pre_builder_count + cap + i]
        )


@with_gloas_and_later
@spec_state_test
def test_process_builder_pending_deposits__unfinalized_deposit_blocks(spec, state):
    """A deposit whose slot exceeds the finalized slot blocks the drain — it
    and all later entries stay in the queue this epoch."""
    state.finalized_checkpoint.epoch = spec.Epoch(0)
    finalized_slot = spec.compute_start_slot_at_epoch(state.finalized_checkpoint.epoch)
    pre_builder_count = len(state.builders)
    amount = spec.MIN_DEPOSIT_AMOUNT

    # First entry: finalized (slot <= finalized_slot)
    finalized_pubkey = builder_pubkeys[pre_builder_count + 0]
    finalized_pending = _make_pending_builder_deposit(
        spec, finalized_pubkey, amount, slot=finalized_slot, signed=True
    )

    # Second entry: not finalized (slot > finalized_slot)
    unfinalized_pubkey = builder_pubkeys[pre_builder_count + 1]
    unfinalized_pending = _make_pending_builder_deposit(
        spec,
        unfinalized_pubkey,
        amount,
        slot=spec.Slot(finalized_slot + spec.SLOTS_PER_EPOCH * 2),
        signed=True,
    )

    state.pending_builder_deposits = [finalized_pending, unfinalized_pending]

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_deposits")

    # Only the finalized one was drained; the unfinalized one remains.
    assert len(state.builders) == pre_builder_count + 1
    assert state.builders[pre_builder_count].pubkey == finalized_pubkey
    assert len(state.pending_builder_deposits) == 1
    assert state.pending_builder_deposits[0].pubkey == unfinalized_pubkey


@with_gloas_and_later
@spec_state_test
def test_process_builder_pending_deposits__invalid_signature_skipped(spec, state):
    """An invalid-signature pending deposit for a NEW pubkey is consumed (the
    cap counter advances) but no builder is added to the registry."""
    _set_finalized_to_current_epoch(spec, state)
    pre_builder_count = len(state.builders)
    amount = spec.MIN_DEPOSIT_AMOUNT

    pubkey = builder_pubkeys[pre_builder_count + 0]
    invalid = _make_pending_builder_deposit(
        spec, pubkey, amount, slot=spec.GENESIS_SLOT, signed=False
    )
    state.pending_builder_deposits = [invalid]

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_deposits")

    # Drained from queue but no builder created for invalid signature.
    assert len(state.pending_builder_deposits) == 0
    assert len(state.builders) == pre_builder_count
