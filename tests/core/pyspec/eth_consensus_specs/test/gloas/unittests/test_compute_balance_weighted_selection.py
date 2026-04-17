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
def test_compute_balance_weighted_selection_excludes_slashed_shuffled(spec, state):
    """
    [EIP-8045] ``compute_balance_weighted_selection`` must never return
    slashed validators when sampling via shuffle.
    """
    active = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    assert len(active) >= 4
    slashed = set(active[::2])
    for validator_index in slashed:
        state.validators[validator_index].slashed = True

    seed = b"\x01" * 32
    size = spec.uint64(max(1, len(active) // 4))
    selected = spec.compute_balance_weighted_selection(
        state,
        indices=active,
        seed=seed,
        size=size,
        shuffle_indices=True,
    )
    assert len(selected) == size
    for validator_index in selected:
        assert validator_index not in slashed
        assert not state.validators[validator_index].slashed


@with_phases([GLOAS])
@spec_test
@with_state
@single_phase
def test_compute_balance_weighted_selection_excludes_slashed_unshuffled(spec, state):
    """
    [EIP-8045] Same guarantee when ``shuffle_indices=False`` (the PTC code
    path): in-order traversal must still skip slashed candidates.
    """
    active = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    assert len(active) >= 4
    slashed = set(active[: len(active) // 2])
    for validator_index in slashed:
        state.validators[validator_index].slashed = True

    seed = b"\x02" * 32
    size = spec.uint64(max(1, len(active) // 8))
    selected = spec.compute_balance_weighted_selection(
        state,
        indices=active,
        seed=seed,
        size=size,
        shuffle_indices=False,
    )
    assert len(selected) == size
    for validator_index in selected:
        assert validator_index not in slashed
