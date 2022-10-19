from eth2spec.test.context import (
    with_phases,
    spec_state_test,
)
from eth2spec.test.helpers.constants import WHISK
from eth2spec.test.helpers.state import next_epoch


@with_phases([WHISK])
@spec_state_test
def test_whisk_process_epoch(spec, state):
    spec.process_epoch(state)
    assert 1 == 0



    # assert spec.get_committee_count_delta(state, 0, 0) == 0
    # assert spec.get_committee_count_per_slot(state, 0) != 0
    # assert spec.get_committee_count_delta(state, 0, 1) == spec.get_committee_count_per_slot(state, 0)
    # assert spec.get_committee_count_delta(state, 1, 2) == spec.get_committee_count_per_slot(state, 0)
    # assert spec.get_committee_count_delta(state, 0, 2) == spec.get_committee_count_per_slot(state, 0) * 2
    # assert spec.get_committee_count_delta(state, 0, spec.SLOTS_PER_EPOCH) == (
    #     spec.get_committee_count_per_slot(state, 0) * spec.SLOTS_PER_EPOCH
    # )
    # assert spec.get_committee_count_delta(state, 0, 2 * spec.SLOTS_PER_EPOCH) == (
    #     spec.get_committee_count_per_slot(state, 0) * spec.SLOTS_PER_EPOCH
    #     + spec.get_committee_count_per_slot(state, 1) * spec.SLOTS_PER_EPOCH
    # )
