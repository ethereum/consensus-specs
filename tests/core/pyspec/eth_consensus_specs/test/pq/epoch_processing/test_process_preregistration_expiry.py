from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.preregistrations import build_pq_stored_preregistration

FRESH_INDEX = len(privkeys) - 1


@with_phases([PQ])
@spec_state_test
def test_expiry_sweep(spec, state):
    state.latest_execution_payload_bid.slot = spec.PREREGISTRATION_EXPIRY_SLOTS
    state.slot = spec.Slot(state.latest_execution_payload_bid.slot + spec.SLOTS_PER_EPOCH - 1)
    state.validator_preregistrations.append(
        build_pq_stored_preregistration(spec, FRESH_INDEX, spec.PREREGISTRATION_EXPIRY_SLOTS)
    )
    state.validator_preregistrations.append(
        build_pq_stored_preregistration(
            spec, FRESH_INDEX - 1, spec.PREREGISTRATION_EXPIRY_SLOTS + 1
        )
    )
    active = state.validator_preregistrations[1]

    yield from run_epoch_processing_with(spec, state, "process_preregistration_expiry")

    assert list(state.validator_preregistrations) == [active]


@with_phases([PQ])
@spec_state_test
def test_expiry_sweep_no_expired_records(spec, state):
    state.slot = spec.Slot(spec.SLOTS_PER_EPOCH - 1)
    state.validator_preregistrations.append(
        build_pq_stored_preregistration(spec, FRESH_INDEX, spec.PREREGISTRATION_EXPIRY_SLOTS)
    )

    yield from run_epoch_processing_with(spec, state, "process_preregistration_expiry")

    assert len(state.validator_preregistrations) == 1


@with_phases([PQ])
@spec_state_test
def test_expiry_sweep_keeps_binding_for_covered_outstanding_payload(spec, state):
    expiry_slot = spec.Slot(1 + spec.PREREGISTRATION_EXPIRY_SLOTS)
    state.validator_preregistrations.append(
        build_pq_stored_preregistration(spec, FRESH_INDEX, expiry_slot)
    )
    next_epoch = spec.Epoch(spec.compute_epoch_at_slot(expiry_slot) + 1)
    state.slot = spec.Slot(spec.compute_start_slot_at_epoch(next_epoch) - 1)
    state.latest_execution_payload_bid.slot = spec.Slot(expiry_slot - 1)

    yield from run_epoch_processing_with(spec, state, "process_preregistration_expiry")

    assert len(state.validator_preregistrations) == 1


@with_phases([PQ])
@spec_state_test
def test_expiry_sweep_multiple_expired(spec, state):
    state.latest_execution_payload_bid.slot = spec.PREREGISTRATION_EXPIRY_SLOTS
    state.slot = spec.Slot(state.latest_execution_payload_bid.slot + spec.SLOTS_PER_EPOCH - 1)
    for index in [FRESH_INDEX, FRESH_INDEX - 1, FRESH_INDEX - 2]:
        state.validator_preregistrations.append(
            build_pq_stored_preregistration(spec, index, spec.PREREGISTRATION_EXPIRY_SLOTS)
        )
    state.validator_preregistrations.append(
        build_pq_stored_preregistration(
            spec, FRESH_INDEX - 3, spec.PREREGISTRATION_EXPIRY_SLOTS + 1
        )
    )
    active = state.validator_preregistrations[3]

    yield from run_epoch_processing_with(spec, state, "process_preregistration_expiry")

    assert list(state.validator_preregistrations) == [active]
