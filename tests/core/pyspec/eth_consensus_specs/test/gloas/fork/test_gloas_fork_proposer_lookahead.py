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
def test_fork_proposer_lookahead_no_slashed_validators(spec, phases, state):
    """
    [EIP-8045] When there are no slashed validators before the fork, the
    proposer lookahead carried across the fork contains no slashed validators,
    and it stays slashed-free as Gloas epoch transitions recompute it.
    """
    gloas = phases[GLOAS]
    fork_epoch = _transition_to_last_slot_before_fork(spec, state)

    assert not any(v.slashed for v in state.validators)

    state, _ = yield from do_fork_generate(state, spec, gloas, fork_epoch, with_block=False)

    # Nothing was slashed, so the carried-over lookahead is clean.
    for validator_index in state.proposer_lookahead:
        assert not state.validators[validator_index].slashed

    # And it stays clean as the lookahead is recomputed under Gloas.
    post_state = state.copy()
    for _ in range(gloas.MIN_SEED_LOOKAHEAD + 1):
        next_epoch(gloas, post_state)
        for validator_index in post_state.proposer_lookahead:
            assert not post_state.validators[validator_index].slashed


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_proposer_lookahead_slashed_validators_carried_over(spec, phases, state):
    """
    [EIP-8045] Slashed validators that were already committed to the proposer
    lookahead before the fork are carried across the fork verbatim.

    Both lookahead epochs are computed under the pre-fork (Fulu) rules: the
    first half two epochs before the fork, and the second half by the epoch
    transition that runs immediately before ``upgrade_to_gloas``. EIP-8045 only
    filters *newly* computed entries, so these pre-fork assignments are not
    retroactively rewritten and the slashed validators remain.
    """
    gloas = phases[GLOAS]
    fork_epoch = _transition_to_last_slot_before_fork(spec, state)

    # Slash every validator that appears anywhere in the pre-fork lookahead, so
    # both lookahead epochs reference slashed validators.
    pre_fork_lookahead = list(state.proposer_lookahead)
    for validator_index in set(pre_fork_lookahead):
        state.validators[validator_index].slashed = True

    # The fork-slot proposer is now slashed and cannot produce a valid block.
    state, _ = yield from do_fork_generate(state, spec, gloas, fork_epoch, with_block=False)

    # The first lookahead epoch is the pre-fork second half shifted down: it was
    # committed before the fork and still references the same slashed validators.
    half = gloas.SLOTS_PER_EPOCH
    assert list(state.proposer_lookahead[:half]) == pre_fork_lookahead[half:]
    assert all(state.validators[v].slashed for v in state.proposer_lookahead[:half])


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_proposer_lookahead_excludes_slashed_in_new_half(spec, phases, state):
    """
    [EIP-8045] Scenario where slashed validators would be selected into the
    newly computed (second) half of the lookahead under the pre-fork rules.

    The validators slashed here are exactly those that the pre-fork (Fulu)
    ``get_beacon_proposer_indices`` selects for that half -- the proposers that
    would be included "without this change". Slashing them does not change the
    Fulu selection (which ignores the slashed flag), so the pre-fork rules still
    fill the half with slashed validators, while EIP-8045's modified
    ``get_beacon_proposer_indices`` excludes them.
    """
    gloas = phases[GLOAS]
    fork_epoch = _transition_to_last_slot_before_fork(spec, state)

    # The epoch whose proposers form the newly computed half of the lookahead
    # that the epoch transition fills in right before upgrade_to_gloas.
    new_half_epoch = spec.get_current_epoch(state) + spec.MIN_SEED_LOOKAHEAD + 1

    # Slash exactly the validators the pre-fork rules would select for that half.
    for validator_index in set(spec.get_beacon_proposer_indices(state, new_half_epoch)):
        state.validators[validator_index].slashed = True

    # Without EIP-8045, the new half is entirely slashed validators.
    pre_fork_new_half = spec.get_beacon_proposer_indices(state, new_half_epoch)
    assert all(state.validators[v].slashed for v in pre_fork_new_half)

    # With EIP-8045, the same computation excludes the slashed validators.
    post_fork_new_half = gloas.get_beacon_proposer_indices(state, new_half_epoch)
    assert not any(state.validators[v].slashed for v in post_fork_new_half)

    state, _ = yield from do_fork_generate(state, spec, gloas, fork_epoch, with_block=False)
