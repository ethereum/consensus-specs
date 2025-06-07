from eth2spec.test.context import (
    spec_test,
    with_phases,
    with_state,
)
from eth2spec.test.helpers.constants import (
    ELECTRA,
    FULU,
)
from eth2spec.test.helpers.fulu.fork import (
    FULU_FORK_TEST_META_TAGS,
    run_fork_test,
)
from eth2spec.test.utils import with_meta_tags
from tests.core.pyspec.eth2spec.test.helpers.state import next_epoch, simulate_lookahead
from eth2spec.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential,
)


@with_phases(phases=[ELECTRA], other_phases=[FULU])
@spec_test
@with_state
@with_meta_tags(FULU_FORK_TEST_META_TAGS)
def test_lookahead_consistency_at_fork(spec, phases, state):
    """
    Test that lookahead is consistent before/after the Fulu fork.
    """

    # Calculate the current and next epoch lookahead by simulating the state progression
    # with empty slots and calling `get_beacon_proposer_index` (how it was done pre-Fulu)
    pre_fork_proposers = simulate_lookahead(spec, state)

    # Upgrade to Fulu
    spec = phases[FULU]
    state = yield from run_fork_test(spec, state)

    # Check if the pre-fork simulation matches the post-fork `state.proposer_lookahead`
    assert pre_fork_proposers == state.proposer_lookahead

@with_phases(phases=[ELECTRA], other_phases=[FULU])
@spec_test
@with_state
@with_meta_tags(FULU_FORK_TEST_META_TAGS)
def test_lookahead_consistency_with_effective_balance_change_at_fork(spec, phases, state):
    next_epoch(spec, state)
    next_epoch(spec, state)
    next_epoch(spec, state)
    next_epoch(spec, state)

    # Move to the penultimate slot of the current epoch
    spec.process_slots(state, state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1)
    assert state.slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1

    # Change the balances so the epoch processing will change the effective balances,
    # which will affect the proposers selection.
    current_epoch = spec.get_current_epoch(state)
    active_validator_indices = spec.get_active_validator_indices(state, current_epoch)
    for validator_index in active_validator_indices:
        # Set compounding withdrawal credentials for the validator
        set_compounding_withdrawal_credential(spec, state, validator_index)
        state.validators[validator_index].effective_balance = 32000000000
        # Set balance to close the next hysteresis threshold
        state.balances[validator_index] = 33250000000 - 1

    # Calculate the lookahead after the effective balance change, and before the Electra epoch processing
    pre_fork_proposers = simulate_lookahead(spec, state)

    # This will run electra epoch processing
    spec.process_slots(state, state.slot + 1) 
    assert state.slot % spec.SLOTS_PER_EPOCH == 0
    # Upgrade to Fulu
    spec = phases[FULU]
    state = yield from run_fork_test(spec, state)

    # Because the electra epoch processing is always run right before the fulu upgrade,
    # the proposers lookahead will change depending on the effective balance change.
    assert pre_fork_proposers != state.proposer_lookahead
