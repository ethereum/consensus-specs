from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with


@with_phases([PQ])
@spec_state_test
def test_process_aggregation_committee_window__shifts_all_epochs(spec, state):
    spec.process_slots(state, state.slot + 2 * spec.SLOTS_PER_EPOCH - 1)

    slots_per_epoch = spec.SLOTS_PER_EPOCH
    current_epoch_committees = list(
        state.aggregation_committee_window[slots_per_epoch : 2 * slots_per_epoch]
    )
    next_epoch_committees = list(state.aggregation_committee_window[2 * slots_per_epoch :])

    yield from run_epoch_processing_with(spec, state, "process_aggregation_committee_window")

    assert list(state.aggregation_committee_window[:slots_per_epoch]) == current_epoch_committees
    assert (
        list(state.aggregation_committee_window[slots_per_epoch : 2 * slots_per_epoch])
        == next_epoch_committees
    )
    lookahead_start_slot = spec.compute_start_slot_at_epoch(
        spec.get_current_epoch(state) + spec.MIN_SEED_LOOKAHEAD + 1
    )
    for offset in range(slots_per_epoch):
        slot = spec.Slot(lookahead_start_slot + offset)
        assert state.aggregation_committee_window[2 * slots_per_epoch + offset] == (
            spec.compute_aggregation_committees(state, slot)
        )


@with_phases([PQ])
@spec_state_test
def test_process_aggregation_committee_window__keeps_aggregators_after_balance_change(spec, state):
    spec.process_slots(state, state.slot + spec.SLOTS_PER_EPOCH - 1)

    lookahead_epoch = spec.get_current_epoch(state) + spec.MIN_SEED_LOOKAHEAD
    slot = spec.compute_start_slot_at_epoch(lookahead_epoch)
    aggregators = spec.get_aggregation_committee(state, slot, spec.CommitteeIndex(0))

    # A change in effective balance does not change aggregators already in the window
    for validator in state.validators:
        validator.effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA

    yield from run_epoch_processing_with(spec, state, "process_aggregation_committee_window")

    state.slot += 1
    assert spec.get_aggregation_committee(state, slot, spec.CommitteeIndex(0)) == aggregators
