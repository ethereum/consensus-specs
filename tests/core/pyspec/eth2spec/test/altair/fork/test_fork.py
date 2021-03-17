from eth2spec.test.context import (
    PHASE0, ALTAIR,
    MINIMAL,
    with_phases,
    with_custom_state,
    with_configs,
    spec_test, with_state,
    low_balances, misc_balances, large_validator_set,
)
from eth2spec.test.utils import with_meta_tags
from eth2spec.test.helpers.state import (
    next_epoch,
    next_epoch_via_block,
)


ALTAIR_FORK_TEST_META_TAGS = {
    'fork': 'altair',
}


def run_fork_test(post_spec, pre_state):
    yield 'pre', pre_state

    post_state = post_spec.upgrade_to_altair(pre_state)

    # Stable fields
    stable_fields = [
        'genesis_time', 'genesis_validators_root', 'slot',
        # History
        'latest_block_header', 'block_roots', 'state_roots', 'historical_roots',
        # Eth1
        'eth1_data', 'eth1_data_votes', 'eth1_deposit_index',
        # Registry
        'validators', 'balances',
        # Randomness
        'randao_mixes',
        # Slashings
        'slashings',
        # Finality
        'justification_bits', 'previous_justified_checkpoint', 'current_justified_checkpoint', 'finalized_checkpoint',
    ]
    for field in stable_fields:
        assert getattr(pre_state, field) == getattr(post_state, field)

    # Modified fields
    modified_fields = ['fork']
    for field in modified_fields:
        assert getattr(pre_state, field) != getattr(post_state, field)

    assert pre_state.fork.current_version == post_state.fork.previous_version
    assert post_state.fork.current_version == post_spec.ALTAIR_FORK_VERSION
    assert post_state.fork.epoch == post_spec.get_current_epoch(post_state)

    yield 'post', post_state


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_fork_base_state(spec, phases, state):
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_fork_next_epoch(spec, phases, state):
    next_epoch(spec, state)
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_fork_next_epoch_with_block(spec, phases, state):
    next_epoch_via_block(spec, state)
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_fork_many_next_epoch(spec, phases, state):
    for _ in range(3):
        next_epoch(spec, state)
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.EJECTION_BALANCE)
@spec_test
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_fork_random_low_balances(spec, phases, state):
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@with_custom_state(balances_fn=misc_balances, threshold_fn=lambda spec: spec.EJECTION_BALANCE)
@spec_test
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_fork_random_misc_balances(spec, phases, state):
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@with_configs([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@with_custom_state(balances_fn=large_validator_set, threshold_fn=lambda spec: spec.EJECTION_BALANCE)
@spec_test
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_fork_random_large_validator_set(spec, phases, state):
    yield from run_fork_test(phases[ALTAIR], state)
