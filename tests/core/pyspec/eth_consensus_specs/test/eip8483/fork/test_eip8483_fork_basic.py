from eth_consensus_specs.test.context import (
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import (
    EIP8483,
    GLOAS,
)
from eth_consensus_specs.test.helpers.eip8483.fork import (
    EIP8483_FORK_TEST_META_TAGS,
    run_fork_test,
)
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    next_epoch_via_block,
)
from eth_consensus_specs.test.utils import with_meta_tags


@with_phases(phases=[GLOAS], other_phases=[EIP8483])
@spec_test
@with_state
@with_meta_tags(EIP8483_FORK_TEST_META_TAGS)
def test_fork_base_state(spec, phases, state):
    yield from run_fork_test(phases[EIP8483], state)


@with_phases(phases=[GLOAS], other_phases=[EIP8483])
@spec_test
@with_state
@with_meta_tags(EIP8483_FORK_TEST_META_TAGS)
def test_fork_next_epoch(spec, phases, state):
    next_epoch(spec, state)
    yield from run_fork_test(phases[EIP8483], state)


@with_phases(phases=[GLOAS], other_phases=[EIP8483])
@spec_test
@with_state
@with_meta_tags(EIP8483_FORK_TEST_META_TAGS)
def test_fork_next_epoch_with_block(spec, phases, state):
    next_epoch_via_block(spec, state)
    yield from run_fork_test(phases[EIP8483], state)
