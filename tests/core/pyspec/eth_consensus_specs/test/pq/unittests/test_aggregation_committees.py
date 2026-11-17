from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ


@with_phases([PQ])
@spec_state_test
def test_compute_aggregation_committee_distinct_committee_members(spec, state):
    epoch = spec.get_current_epoch(state)
    for slot in range(state.slot, state.slot + spec.SLOTS_PER_EPOCH):
        for index in range(spec.get_committee_count_per_slot(state, epoch)):
            slot, index = spec.Slot(slot), spec.CommitteeIndex(index)
            committee = spec.get_beacon_committee(state, slot, index)
            aggregators = spec.compute_aggregation_committee(state, slot, index)
            assert len(aggregators) == min(spec.AGGREGATORS_PER_COMMITTEE, len(committee))
            assert len(set(aggregators)) == len(aggregators)
            assert all(aggregator in committee for aggregator in aggregators)


@with_phases([PQ])
@spec_state_test
def test_compute_aggregation_committee_prefers_high_balance(spec, state):
    slot = state.slot
    index = spec.CommitteeIndex(0)
    committee = spec.get_beacon_committee(state, slot, index)
    # The first candidate always passes the balance check at the maximum balance
    state.validators[committee[0]].effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA

    aggregators = spec.compute_aggregation_committee(state, slot, index)

    assert aggregators[0] == committee[0]


@with_phases([PQ])
@spec_state_test
def test_get_aggregation_committee_reads_window(spec, state):
    current_epoch = spec.get_current_epoch(state)
    start_slot = spec.compute_start_slot_at_epoch(current_epoch)
    end_slot = spec.compute_start_slot_at_epoch(current_epoch + spec.MIN_SEED_LOOKAHEAD + 1)
    for slot in range(start_slot, end_slot):
        epoch = spec.compute_epoch_at_slot(slot)
        for index in range(spec.get_committee_count_per_slot(state, epoch)):
            slot, index = spec.Slot(slot), spec.CommitteeIndex(index)
            aggregators = spec.get_aggregation_committee(state, slot, index)
            assert aggregators == spec.compute_aggregation_committee(state, slot, index)


@with_phases([PQ])
@spec_state_test
def test_is_aggregator(spec, state):
    slot = state.slot
    index = spec.CommitteeIndex(0)
    aggregators = spec.get_aggregation_committee(state, slot, index)
    for validator_index in spec.get_beacon_committee(state, slot, index):
        is_aggregator = spec.is_aggregator(state, slot, index, validator_index)
        assert is_aggregator == (validator_index in aggregators)
