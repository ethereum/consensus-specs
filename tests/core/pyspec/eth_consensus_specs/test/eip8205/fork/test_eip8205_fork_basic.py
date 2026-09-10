from eth_consensus_specs.test.context import (
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import (
    EIP8205,
    HEZE,
)
from eth_consensus_specs.test.helpers.eip8205.fork import (
    EIP8205_FORK_TEST_META_TAGS,
    run_fork_test,
)
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    next_epoch_via_block,
)
from eth_consensus_specs.test.utils import with_meta_tags


@with_phases(phases=[HEZE], other_phases=[EIP8205])
@spec_test
@with_state
@with_meta_tags(EIP8205_FORK_TEST_META_TAGS)
def test_fork_base_state(spec, phases, state):
    yield from run_fork_test(phases[EIP8205], state)


@with_phases(phases=[HEZE], other_phases=[EIP8205])
@spec_test
@with_state
@with_meta_tags(EIP8205_FORK_TEST_META_TAGS)
def test_fork_next_epoch(spec, phases, state):
    next_epoch(spec, state)
    yield from run_fork_test(phases[EIP8205], state)


@with_phases(phases=[HEZE], other_phases=[EIP8205])
@spec_test
@with_state
@with_meta_tags(EIP8205_FORK_TEST_META_TAGS)
def test_fork_next_epoch_with_block(spec, phases, state):
    next_epoch_via_block(spec, state)
    yield from run_fork_test(phases[EIP8205], state)


@with_phases(phases=[HEZE], other_phases=[EIP8205])
@spec_test
@with_state
@with_meta_tags(EIP8205_FORK_TEST_META_TAGS)
def test_fork_many_next_epoch(spec, phases, state):
    for _ in range(3):
        next_epoch(spec, state)
    yield from run_fork_test(phases[EIP8205], state)
