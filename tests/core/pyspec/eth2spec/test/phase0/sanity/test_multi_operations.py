from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.proposer_slashings import get_valid_proposer_slashing
from eth2spec.test.helpers.voluntary_exits import prepare_signed_exits

from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)


def run_slash_and_exit(spec, state, slash_index, exit_index, valid=True):
    # move state forward SHARD_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slashed_index=slash_index, signed_1=True, signed_2=True)
    signed_exit = prepare_signed_exits(spec, state, [exit_index])[0]

    block.body.proposer_slashings.append(proposer_slashing)
    block.body.voluntary_exits.append(signed_exit)

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=(not valid))

    yield 'blocks', [signed_block]

    if valid:
        yield 'post', state
    else:
        yield 'post', None


@with_all_phases
@spec_state_test
def test_slash_and_exit_same_index(spec, state):
    validator_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    run_slash_and_exit(spec, state, validator_index, validator_index, valid=False)


@with_all_phases
@spec_state_test
def test_slash_and_exit_diff_index(spec, state):
    slash_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-1]
    exit_index = spec.get_active_validator_indices(state, spec.get_current_epoch(state))[-2]
    run_slash_and_exit(spec, state, slash_index, exit_index)
