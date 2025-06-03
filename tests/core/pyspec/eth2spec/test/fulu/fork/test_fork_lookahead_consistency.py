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
from tests.core.pyspec.eth2spec.test.helpers.state import simulate_lookahead


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
