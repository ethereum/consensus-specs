from eth_consensus_specs.test.context import (
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import (
    FULU,
    GLOAS,
)
from eth_consensus_specs.test.helpers.fork_transition import do_fork_generate
from eth_consensus_specs.test.helpers.gloas.fork import GLOAS_FORK_TEST_META_TAGS
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    transition_to,
)
from eth_consensus_specs.test.utils import with_meta_tags


def _transition_to_last_slot_before_fork(spec, state):
    """
    Advance a couple of epochs so the proposer lookahead is fully populated by
    regular epoch processing, then stop at the last slot of the epoch right
    before the fork (where ``do_fork_generate`` expects to take over).
    """
    for _ in range(2):
        next_epoch(spec, state)
    fork_epoch = spec.get_current_epoch(state) + 1
    transition_to(spec, state, fork_epoch * spec.SLOTS_PER_EPOCH - 1)
    return fork_epoch


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_proposer_lookahead_slashed_validators_carried_over(spec, phases, state):
    """
    Test that both proposer lookahead epochs can contain slashed validators
    after the fork.
    """
    gloas = phases[GLOAS]
    fork_epoch = _transition_to_last_slot_before_fork(spec, state)

    # Slash half of the validator set
    for validator_index in range(len(state.validators) // 2):
        state.validators[validator_index].slashed = True

    state, _ = yield from do_fork_generate(state, spec, gloas, fork_epoch, with_block=False)

    # Both halves were computed under Fulu, so both still have slashed validators
    half = spec.SLOTS_PER_EPOCH
    assert any(state.validators[v].slashed for v in state.proposer_lookahead[:half])
    assert any(state.validators[v].slashed for v in state.proposer_lookahead[half:])
