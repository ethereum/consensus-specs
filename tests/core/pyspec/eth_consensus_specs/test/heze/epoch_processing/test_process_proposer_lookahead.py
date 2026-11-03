from eth_consensus_specs.test.context import spec_state_test, with_heze_and_later
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.state import next_epoch


def _expected_new_lookahead_epoch(spec, state):
    return spec.get_current_epoch(state) + spec.MIN_SEED_LOOKAHEAD + 1


def _new_lookahead_epoch(spec, state):
    return list(state.proposer_lookahead[-spec.SLOTS_PER_EPOCH :])


@with_heze_and_later
@spec_state_test
def test_proposer_lookahead_slashing_non_proposer_does_not_reshuffle(spec, state):
    for _ in range(spec.MIN_SEED_LOOKAHEAD + 1):
        next_epoch(spec, state)

    epoch = _expected_new_lookahead_epoch(spec, state)
    baseline = list(spec.get_beacon_proposer_indices(state, epoch))
    active = spec.get_active_validator_indices(state, spec.get_current_epoch(state))
    to_slash = next(index for index in active if index not in baseline)
    state.validators[to_slash].slashed = True

    yield from run_epoch_processing_with(spec, state, "process_proposer_lookahead")

    assert _new_lookahead_epoch(spec, state) == baseline


@with_heze_and_later
@spec_state_test
def test_proposer_lookahead_slashing_proposer_only_changes_its_slots(spec, state):
    for _ in range(spec.MIN_SEED_LOOKAHEAD + 1):
        next_epoch(spec, state)

    epoch = _expected_new_lookahead_epoch(spec, state)
    baseline = list(spec.get_beacon_proposer_indices(state, epoch))
    to_slash = baseline[0]
    state.validators[to_slash].slashed = True

    yield from run_epoch_processing_with(spec, state, "process_proposer_lookahead")

    new_epoch = _new_lookahead_epoch(spec, state)
    assert to_slash not in new_epoch
    for before, after in zip(baseline, new_epoch, strict=True):
        if before != to_slash:
            assert after == before
