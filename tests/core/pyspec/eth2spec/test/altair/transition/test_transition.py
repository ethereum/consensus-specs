from eth2spec.test.context import (
    fork_transition_test,
    single_phase,
    with_custom_state,
    default_activation_threshold,
    low_balances,
)
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.state import state_transition_and_sign_block
from eth2spec.test.helpers.block import build_empty_block_for_next_slot


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_normal_transition(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    yield "pre", state

    blocks = []
    for slot in range(state.slot, fork_epoch * spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, state)
        state_transition_and_sign_block(spec, state, block)
        blocks.append(pre_tag(block))

    state = post_spec.upgrade_to_altair(state)

    assert state.fork.epoch == fork_epoch
    assert state.fork.previous_version == post_spec.GENESIS_FORK_VERSION
    assert state.fork.current_version == post_spec.ALTAIR_FORK_VERSION

    block = build_empty_block_for_next_slot(post_spec, state)
    state_transition_and_sign_block(post_spec, state, block)
    blocks.append(post_tag(block))

    yield "blocks", blocks
    yield "post", state


@fork_transition_test(PHASE0, ALTAIR)
def test_normal_transition_with_manual_fork_epoch(state, spec, post_spec, pre_tag, post_tag):
    fork_epoch = 2
    yield "fork_epoch", "meta", fork_epoch

    # run test with computed fork_epoch...


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
@with_custom_state(low_balances, default_activation_threshold)
@single_phase
def test_normal_transition_with_low_balances(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    yield "pre", state

    # run test with custom state...
