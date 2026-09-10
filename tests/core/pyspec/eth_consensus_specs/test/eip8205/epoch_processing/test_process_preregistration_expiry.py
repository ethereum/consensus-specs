from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8205_and_later,
)
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.keys import pubkeys
from eth_consensus_specs.test.helpers.preregistrations import (
    preregistration_withdrawal_credentials,
)


def _stored_preregistration(spec, pubkey, expiry_slot):
    return spec.StoredPreregistration(
        pubkey=pubkey,
        withdrawal_credentials=preregistration_withdrawal_credentials(spec),
        expiry_slot=spec.Slot(expiry_slot),
    )


@with_eip8205_and_later
@spec_state_test
def test_expiry_sweep(spec, state):
    # A record whose deadline equals the outstanding parent slot is inactive;
    # one with a deadline one slot later is still active
    state.latest_execution_payload_bid.slot = spec.PREREGISTRATION_EXPIRY_SLOTS
    state.slot = spec.Slot(state.latest_execution_payload_bid.slot + spec.SLOTS_PER_EPOCH - 1)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, pubkeys[-1], spec.PREREGISTRATION_EXPIRY_SLOTS)
    )
    state.validator_preregistrations.append(
        _stored_preregistration(spec, pubkeys[-2], spec.PREREGISTRATION_EXPIRY_SLOTS + 1)
    )

    yield from run_epoch_processing_with(spec, state, "process_preregistration_expiry")

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == pubkeys[-2]


@with_eip8205_and_later
@spec_state_test
def test_expiry_sweep_no_expired_records(spec, state):
    state.slot = spec.Slot(spec.SLOTS_PER_EPOCH - 1)
    state.validator_preregistrations.append(
        _stored_preregistration(spec, pubkeys[-1], spec.PREREGISTRATION_EXPIRY_SLOTS)
    )

    yield from run_epoch_processing_with(spec, state, "process_preregistration_expiry")

    assert len(state.validator_preregistrations) == 1


@with_eip8205_and_later
@spec_state_test
def test_expiry_sweep_keeps_binding_for_covered_outstanding_payload(spec, state):
    expiry_slot = spec.Slot(1 + spec.PREREGISTRATION_EXPIRY_SLOTS)
    state.validator_preregistrations.append(_stored_preregistration(spec, pubkeys[-1], expiry_slot))

    # The state may have reached the deadline, but the delayed parent payload
    # is from the final covered slot. Epoch GC must not remove the binding.
    next_epoch = spec.Epoch(spec.compute_epoch_at_slot(expiry_slot) + 1)
    state.slot = spec.Slot(spec.compute_start_slot_at_epoch(next_epoch) - 1)
    state.latest_execution_payload_bid.slot = spec.Slot(expiry_slot - 1)

    yield from run_epoch_processing_with(spec, state, "process_preregistration_expiry")

    assert len(state.validator_preregistrations) == 1


@with_eip8205_and_later
@spec_state_test
def test_expiry_sweep_multiple_expired(spec, state):
    # Every record whose deadline is at or below the outstanding parent slot is
    # swept in a single pass, and the still-active record keeps its position
    state.latest_execution_payload_bid.slot = spec.PREREGISTRATION_EXPIRY_SLOTS
    state.slot = spec.Slot(state.latest_execution_payload_bid.slot + spec.SLOTS_PER_EPOCH - 1)
    for pubkey in [pubkeys[-1], pubkeys[-2], pubkeys[-3]]:
        state.validator_preregistrations.append(
            _stored_preregistration(spec, pubkey, spec.PREREGISTRATION_EXPIRY_SLOTS)
        )
    state.validator_preregistrations.append(
        _stored_preregistration(spec, pubkeys[-4], spec.PREREGISTRATION_EXPIRY_SLOTS + 1)
    )

    yield from run_epoch_processing_with(spec, state, "process_preregistration_expiry")

    assert len(state.validator_preregistrations) == 1
    assert state.validator_preregistrations[0].pubkey == pubkeys[-4]
