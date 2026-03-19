from eth_consensus_specs.test.context import (
    expect_assertion_error,
    single_phase,
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import GLOAS
from eth_consensus_specs.test.helpers.state import next_epoch


def _compute_first_ptc_assignments(spec, state, epoch):
    assignments = {}
    start_slot = spec.compute_start_slot_at_epoch(epoch)
    for slot in range(start_slot, start_slot + spec.SLOTS_PER_EPOCH):
        for validator_index in spec.compute_ptc(state, spec.Slot(slot)):
            assignments.setdefault(validator_index, spec.Slot(slot))
    return assignments


def _assert_get_ptc_assignments(spec, state, epoch, assignments):
    assert len(assignments) > 0

    for validator_index, expected_slot in assignments.items():
        assert spec.get_ptc_assignment(state, epoch, validator_index) == expected_slot

    unassigned_validator = next(
        (spec.ValidatorIndex(i) for i in range(len(state.validators)) if i not in assignments),
        None,
    )
    if unassigned_validator is not None:
        assert spec.get_ptc_assignment(state, epoch, unassigned_validator) is None


@with_phases([GLOAS])
@spec_test
@with_state
@single_phase
def test_get_ptc_assignment__previous_epoch(spec, state):
    next_epoch(spec, state)

    epoch = spec.Epoch(spec.get_current_epoch(state) - 1)
    expect_assertion_error(lambda: spec.get_ptc_assignment(state, epoch, spec.ValidatorIndex(0)))


@with_phases([GLOAS])
@spec_test
@with_state
@single_phase
def test_get_ptc_assignment__current_epoch(spec, state):
    epoch = spec.get_current_epoch(state)
    assignments = _compute_first_ptc_assignments(spec, state, epoch)
    _assert_get_ptc_assignments(spec, state, epoch, assignments)


@with_phases([GLOAS])
@spec_test
@with_state
@single_phase
def test_get_ptc_assignment__next_epoch(spec, state):
    epoch = spec.Epoch(spec.get_current_epoch(state) + 1)
    expect_assertion_error(lambda: spec.get_ptc_assignment(state, epoch, spec.ValidatorIndex(0)))
