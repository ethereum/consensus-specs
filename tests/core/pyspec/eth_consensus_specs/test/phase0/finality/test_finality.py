from eth_consensus_specs.test.context import spec_state_test, with_all_phases
from eth_consensus_specs.test.helpers.attestations import next_epoch_with_attestations
from eth_consensus_specs.test.helpers.state import next_epoch_via_block


def check_finality(
    spec,
    state,
    prev_state,
    current_justified_changed,
    previous_justified_changed,
    finalized_changed,
):
    if current_justified_changed:
        assert (
            state.current_justified_checkpoint.epoch > prev_state.current_justified_checkpoint.epoch
        )
        assert (
            state.current_justified_checkpoint.root != prev_state.current_justified_checkpoint.root
        )
    else:
        assert state.current_justified_checkpoint == prev_state.current_justified_checkpoint

    if previous_justified_changed:
        assert (
            state.previous_justified_checkpoint.epoch
            > prev_state.previous_justified_checkpoint.epoch
        )
        assert (
            state.previous_justified_checkpoint.root
            != prev_state.previous_justified_checkpoint.root
        )
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

    yield "pre", state

    blocks = []
    for epoch in range(2):
        prev_state, new_blocks, state = next_epoch_with_attestations(
            spec, state, fill_cur_epoch=True, fill_prev_epoch=False
        )
        blocks += new_blocks

        # justification/finalization skipped at GENESIS_EPOCH
        if epoch == 0 or epoch == 1:
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=False,
                previous_justified_changed=False,
                finalized_changed=False,
            )

    yield "blocks", blocks
    yield "post", state


@with_all_phases
@spec_state_test
def test_finality_rule_4(spec, state):
    # get past first two epochs that finality does not run on
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    yield "pre", state

    blocks = []
    for epoch in range(2):
        prev_state, new_blocks, state = next_epoch_with_attestations(
            spec, state, fill_cur_epoch=True, fill_prev_epoch=False
        )
        blocks += new_blocks

        if epoch == 0:
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=True,
                previous_justified_changed=False,
                finalized_changed=False,
            )
        elif epoch == 1:
            # rule 4 of finality
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=True,
                previous_justified_changed=True,
                finalized_changed=True,
            )
            assert state.finalized_checkpoint == prev_state.current_justified_checkpoint

    yield "blocks", blocks
    yield "post", state


@with_all_phases
@spec_state_test
def test_finality_rule_1(spec, state):
    # get past first two epochs that finality does not run on
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    yield "pre", state

    blocks = []
    for epoch in range(3):
        prev_state, new_blocks, state = next_epoch_with_attestations(
            spec, state, fill_cur_epoch=False, fill_prev_epoch=True
        )
        blocks += new_blocks

        if epoch == 0:
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=True,
                previous_justified_changed=False,
                finalized_changed=False,
            )
        elif epoch == 1:
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=True,
                previous_justified_changed=True,
                finalized_changed=False,
            )
        elif epoch == 2:
            # finalized by rule 1
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=True,
                previous_justified_changed=True,
                finalized_changed=True,
            )
            assert state.finalized_checkpoint == prev_state.previous_justified_checkpoint

    yield "blocks", blocks
    yield "post", state


@with_all_phases
@spec_state_test
def test_finality_rule_2(spec, state):
    # get past first two epochs that finality does not run on
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    yield "pre", state

    blocks = []
    for epoch in range(3):
        if epoch == 0:
            prev_state, new_blocks, state = next_epoch_with_attestations(
                spec, state, fill_cur_epoch=True, fill_prev_epoch=False
            )
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=True,
                previous_justified_changed=False,
                finalized_changed=False,
            )
        elif epoch == 1:
            prev_state, new_blocks, state = next_epoch_with_attestations(
                spec, state, fill_cur_epoch=False, fill_prev_epoch=False
            )
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=False,
                previous_justified_changed=True,
                finalized_changed=False,
            )
        elif epoch == 2:
            prev_state, new_blocks, state = next_epoch_with_attestations(
                spec, state, fill_cur_epoch=False, fill_prev_epoch=True
            )
            # finalized by rule 2
            check_finality(
                spec,
                state,
                prev_state,
                current_justified_changed=True,
                previous_justified_changed=False,
                finalized_changed=True,
            )
            assert state.finalized_checkpoint == prev_state.previous_justified_checkpoint

        blocks += new_blocks

    yield "blocks", blocks
    yield "post", state


@with_all_phases
@spec_state_test
def test_finality_rule_3(spec, state):
    """
    Test scenario described here
    https://github.com/ethereum/consensus-specs/issues/611#issuecomment-463612892
    """
    # get past first two epochs that finality does not run on
    next_epoch_via_block(spec, state)
    next_epoch_via_block(spec, state)

    yield "pre", state

    blocks = []
    prev_state, new_blocks, state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch=True, fill_prev_epoch=False
    )
    blocks += new_blocks
    check_finality(
        spec,
        state,
        prev_state,
        current_justified_changed=True,
        previous_justified_changed=False,
        finalized_changed=False,
    )

    # In epoch N, JE is set to N, prev JE is set to N-1
    prev_state, new_blocks, state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch=True, fill_prev_epoch=False
    )
    blocks += new_blocks
    check_finality(
        spec,
        state,
        prev_state,
        current_justified_changed=True,
        previous_justified_changed=True,
        finalized_changed=True,
    )

    # In epoch N+1, JE is N, prev JE is N-1, and not enough messages get in to do anything
    prev_state, new_blocks, state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch=False, fill_prev_epoch=False
    )
    blocks += new_blocks
    check_finality(
        spec,
        state,
        prev_state,
        current_justified_changed=False,
        previous_justified_changed=True,
        finalized_changed=False,
    )

    # In epoch N+2, JE is N, prev JE is N, and enough messages from the previous epoch get in to justify N+1.
    # N+1 now becomes the JE. Not enough messages from epoch N+2 itself get in to justify N+2
    prev_state, new_blocks, state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch=False, fill_prev_epoch=True
    )
    blocks += new_blocks
    # rule 2
    check_finality(
        spec,
        state,
        prev_state,
        current_justified_changed=True,
        previous_justified_changed=False,
        finalized_changed=True,
    )

    # In epoch N+3, LJE is N+1, prev LJE is N, and enough messages get in to justify epochs N+2 and N+3.
    prev_state, new_blocks, state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch=True, fill_prev_epoch=True
    )
    blocks += new_blocks
    # rule 3
    check_finality(
        spec,
        state,
        prev_state,
        current_justified_changed=True,
        previous_justified_changed=True,
        finalized_changed=True,
    )
    assert state.finalized_checkpoint == prev_state.current_justified_checkpoint

    yield "blocks", blocks
    yield "post", state
