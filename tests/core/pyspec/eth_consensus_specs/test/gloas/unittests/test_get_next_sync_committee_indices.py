from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import GLOAS


@with_phases([GLOAS])
@spec_test
@with_state
@single_phase
def test_sync_committee_excludes_slashed_validators(spec, state):
    """
    [EIP-8045] ``get_next_sync_committee_indices`` must not include any
    slashed validator in its output.
    """
    next_epoch_value = spec.Epoch(spec.get_current_epoch(state) + 1)
    active = spec.get_active_validator_indices(state, next_epoch_value)
    slashed = set(active[: len(active) // 2])
    for validator_index in slashed:
        state.validators[validator_index].slashed = True

    indices = spec.get_next_sync_committee_indices(state)
    assert len(indices) == spec.SYNC_COMMITTEE_SIZE
    for validator_index in indices:
        assert validator_index not in slashed
        assert not state.validators[validator_index].slashed


@with_phases([GLOAS])
@spec_test
@with_state
@single_phase
def test_sync_committee_fills_with_many_slashed(spec, state):
    """
    [EIP-8045] A full ``SYNC_COMMITTEE_SIZE`` sync committee is still
    generated when the majority of candidates are slashed, as long as
    enough unslashed validators remain.
    """
    next_epoch_value = spec.Epoch(spec.get_current_epoch(state) + 1)
    active = spec.get_active_validator_indices(state, next_epoch_value)
    keep = max(4, len(active) // 8)
    assert len(active) > keep
    for validator_index in active[keep:]:
        state.validators[validator_index].slashed = True

    indices = spec.get_next_sync_committee_indices(state)
    assert len(indices) == spec.SYNC_COMMITTEE_SIZE
    for validator_index in indices:
        assert not state.validators[validator_index].slashed
