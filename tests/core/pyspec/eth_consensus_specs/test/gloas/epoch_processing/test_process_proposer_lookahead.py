from eth_consensus_specs.test.context import spec_state_test, with_gloas_and_later
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.state import next_epoch


@with_gloas_and_later
@spec_state_test
def test_proposer_lookahead_does_not_contain_slashed_validators(spec, state):
    """
    [EIP-8045] The newly appended epoch of ``proposer_lookahead`` must not
    reference slashed validators.
    """
    for _ in range(spec.MIN_SEED_LOOKAHEAD + 1):
        next_epoch(spec, state)

    active = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    to_slash = set(active[: len(active) // 2])
    for validator_index in to_slash:
        state.validators[validator_index].slashed = True

    yield from run_epoch_processing_with(spec, state, "process_proposer_lookahead")

    last_epoch_start = len(state.proposer_lookahead) - spec.SLOTS_PER_EPOCH
    for validator_index in state.proposer_lookahead[last_epoch_start:]:
        assert validator_index not in to_slash
        assert not state.validators[validator_index].slashed


@with_gloas_and_later
@spec_state_test
def test_proposer_lookahead_full_with_many_slashed_validators(spec, state):
    """
    [EIP-8045] The lookahead must still fill its full ``SLOTS_PER_EPOCH`` entries
    when only a small subset of active validators remain unslashed.
    """
    for _ in range(spec.MIN_SEED_LOOKAHEAD + 1):
        next_epoch(spec, state)

    active = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    keep = max(spec.SLOTS_PER_EPOCH, 8)
    assert len(active) > keep
    for validator_index in active[keep:]:
        state.validators[validator_index].slashed = True

    yield from run_epoch_processing_with(spec, state, "process_proposer_lookahead")

    last_epoch_start = len(state.proposer_lookahead) - spec.SLOTS_PER_EPOCH
    last_epoch_proposers = list(state.proposer_lookahead[last_epoch_start:])
    assert len(last_epoch_proposers) == spec.SLOTS_PER_EPOCH
    for validator_index in last_epoch_proposers:
        assert not state.validators[validator_index].slashed
