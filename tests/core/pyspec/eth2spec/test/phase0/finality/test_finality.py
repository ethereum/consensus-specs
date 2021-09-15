from eth2spec.test.helpers.constants import MAINNET
from eth2spec.test.context import spec_state_test, with_all_phases, with_presets
from eth2spec.test.helpers.state import next_epoch_via_block
from eth2spec.test.helpers.attestations import next_epoch_with_attestations

from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
)


def check_finality(spec,
                   state,
                   prev_state,
                   current_justified_changed,
                   previous_justified_changed,
                   finalized_changed):
    if current_justified_changed:
        assert state.current_justified_checkpoint.epoch > prev_state.current_justified_checkpoint.epoch
        assert state.current_justified_checkpoint.root != prev_state.current_justified_checkpoint.root
    else:
        assert state.current_justified_checkpoint == prev_state.current_justified_checkpoint

    if previous_justified_changed:
        assert state.previous_justified_checkpoint.epoch > prev_state.previous_justified_checkpoint.epoch
        assert state.previous_justified_checkpoint.root != prev_state.previous_justified_checkpoint.root
    else:
        assert state.previous_justified_checkpoint == prev_state.previous_justified_checkpoint

    if finalized_changed:
        assert state.finalized_checkpoint.epoch > prev_state.finalized_checkpoint.epoch
        assert state.finalized_checkpoint.root != prev_state.finalized_checkpoint.root
    else:
        assert state.finalized_checkpoint == prev_state.finalized_checkpoint


@with_all_phases
@spec_state_test
def test_finality_no_updates_at_genesis(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    yield 'pre', state

    blocks = []
    for epoch in range(2):
        prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, False)
        blocks += new_blocks

        # justification/finalization skipped at GENESIS_EPOCH
        if epoch == 0:
            check_finality(spec, state, prev_state, False, False, False)
        # justification/finalization skipped at GENESIS_EPOCH + 1
        elif epoch == 1:
            check_finality(spec, state, prev_state, False, False, False)

    yield 'blocks', blocks
    yield 'post', state


@with_all_phases
@spec_state_test
def test_finality_rule_4(spec, state):
    # get past first two epochs that finality does not run on
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    yield 'pre', state

    blocks = []
    for epoch in range(2):
        prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, False)
        blocks += new_blocks

        if epoch == 0:
            check_finality(spec, state, prev_state, True, False, False)
        elif epoch == 1:
            # rule 4 of finality
            check_finality(spec, state, prev_state, True, True, True)
            assert state.finalized_checkpoint == prev_state.current_justified_checkpoint

    yield 'blocks', blocks
    yield 'post', state


@with_all_phases
@spec_state_test
def test_finality_rule_1(spec, state):
    # get past first two epochs that finality does not run on
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    yield 'pre', state

    blocks = []
    for epoch in range(3):
        prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, False, True)
        blocks += new_blocks

        if epoch == 0:
            check_finality(spec, state, prev_state, True, False, False)
        elif epoch == 1:
            check_finality(spec, state, prev_state, True, True, False)
        elif epoch == 2:
            # finalized by rule 1
            check_finality(spec, state, prev_state, True, True, True)
            assert state.finalized_checkpoint == prev_state.previous_justified_checkpoint

    yield 'blocks', blocks
    yield 'post', state


@with_all_phases
@spec_state_test
def test_finality_rule_2(spec, state):
    # get past first two epochs that finality does not run on
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    yield 'pre', state

    blocks = []
    for epoch in range(3):
        if epoch == 0:
            prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, False)
            check_finality(spec, state, prev_state, True, False, False)
        elif epoch == 1:
            prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, False, False)
            check_finality(spec, state, prev_state, False, True, False)
        elif epoch == 2:
            prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, False, True)
            # finalized by rule 2
            check_finality(spec, state, prev_state, True, False, True)
            assert state.finalized_checkpoint == prev_state.previous_justified_checkpoint

        blocks += new_blocks

    yield 'blocks', blocks
    yield 'post', state


@with_all_phases
@spec_state_test
def test_finality_rule_3(spec, state):
    """
    Test scenario described here
    https://github.com/ethereum/eth2.0-specs/issues/611#issuecomment-463612892
    """
    # get past first two epochs that finality does not run on
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    yield 'pre', state

    blocks = []
    prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, False)
    blocks += new_blocks
    check_finality(spec, state, prev_state, True, False, False)

    # In epoch N, JE is set to N, prev JE is set to N-1
    prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, False)
    blocks += new_blocks
    check_finality(spec, state, prev_state, True, True, True)

    # In epoch N+1, JE is N, prev JE is N-1, and not enough messages get in to do anything
    prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, False, False)
    blocks += new_blocks
    check_finality(spec, state, prev_state, False, True, False)

    # In epoch N+2, JE is N, prev JE is N, and enough messages from the previous epoch get in to justify N+1.
    # N+1 now becomes the JE. Not enough messages from epoch N+2 itself get in to justify N+2
    prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, False, True)
    blocks += new_blocks
    # rule 2
    check_finality(spec, state, prev_state, True, False, True)

    # In epoch N+3, LJE is N+1, prev LJE is N, and enough messages get in to justify epochs N+2 and N+3.
    prev_state, new_blocks, state = next_epoch_with_attestations(spec, state, True, True)
    blocks += new_blocks
    # rule 3
    check_finality(spec, state, prev_state, True, True, True)
    assert state.finalized_checkpoint == prev_state.current_justified_checkpoint

    yield 'blocks', blocks
    yield 'post', state


@with_all_phases
@with_presets([MAINNET], reason="need SLOTS_PER_EPOCH==32 for formula to work")
@spec_state_test
def test_weak_subjectivity_period_formula(spec, state):
    """
    Test that the WS period formula returns the results of the table in
    https://github.com/ethereum/consensus-specs/blob/dev/specs/phase0/weak-subjectivity.md
    """
    N_VALIDATORS = 32768
    AVG_BALANCE = 28

    # Populate state with 32768 validators with 28 ETH average balance.
    # Period should be 504 epochs according to The Table
    validator_balances = [AVG_BALANCE] * N_VALIDATORS
    state.balances = validator_balances
    state.validators = []
    for i in range(N_VALIDATORS):
        state.validators.append(spec.Validator(
            activation_epoch=spec.GENESIS_EPOCH,
            exit_epoch=spec.FAR_FUTURE_EPOCH,
            effective_balance=28000000000))

    weak_subjectivity_period = spec.compute_weak_subjectivity_period(state)
    assert(weak_subjectivity_period == 504)


@with_all_phases
@spec_state_test
def test_is_within_weak_subjectivity_period(spec, state):
    """
    Test that is_within_weak_subjectivity_period() will deny access as intended
    if our WS checkpoint is too old.
    """
    # Initialization
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)

    # Get weak subjectivity period so we know how long to make our chain
    # (For current configuration, WS period is 256)
    weak_subjectivity_period = spec.compute_weak_subjectivity_period(state)

    # Let's pretend that our WS checkpoint is the genesis block #0 and let's
    # move forward in time. While moving, we will be checking whether we are
    # inside or outside the acceptable WS period.
    ws_state = state
    ws_state.slot = spec.get_current_slot(store)
    # Also mark the genesis block as the WS checkpoint
    ws_checkpoint = spec.Checkpoint(
        root=ws_state.latest_block_header.state_root,
        epoch=spec.compute_epoch_at_slot(ws_state.slot))

    # First, let's pretend that the client wakes up at epoch WS_PERIOD. That
    # should be within WS period and access should be granted
    current_time = ((weak_subjectivity_period) * spec.SLOTS_PER_EPOCH) * spec.config.SECONDS_PER_SLOT + \
        store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    assert spec.is_within_weak_subjectivity_period(store, ws_state, ws_checkpoint)

    # Now pretend that the client woke up at epoch WS_PERIOD+1. That should be
    # outside of WS period and access should be denied.
    current_time = ((weak_subjectivity_period + 1) * spec.SLOTS_PER_EPOCH) * spec.config.SECONDS_PER_SLOT + \
        store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    assert not spec.is_within_weak_subjectivity_period(store, ws_state, ws_checkpoint)
