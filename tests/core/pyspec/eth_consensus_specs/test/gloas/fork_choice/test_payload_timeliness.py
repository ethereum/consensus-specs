from eth_consensus_specs.test.context import (
    default_activation_threshold,
    single_phase,
    spec_test,
    with_custom_state,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_payload_vote_checks,
    output_head_check,
)
from eth_consensus_specs.test.helpers.payload_attestation import (
    ptc_size_balances,
    setup_verified_parent_with_distinct_ptc,
    vote_via_child_block,
)


@with_gloas_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_payload_timeliness_at_threshold_returns_false(spec, state):
    """
    Test that PAYLOAD_TIMELY_THRESHOLD timely votes return False.
    """
    store, block_root, block_state, test_steps = yield from setup_verified_parent_with_distinct_ptc(
        spec, state
    )

    yield from vote_via_child_block(
        spec,
        store,
        block_root,
        block_state,
        positions=range(spec.PAYLOAD_TIMELY_THRESHOLD),
        test_steps=test_steps,
    )

    assert not spec.payload_timeliness(store, block_root, timely=True)
    add_payload_vote_checks(store, block_root, test_steps)
    output_head_check(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_payload_timeliness_above_threshold_returns_true(spec, state):
    """
    Test that PAYLOAD_TIMELY_THRESHOLD + 1 timely votes return True.
    """
    store, block_root, block_state, test_steps = yield from setup_verified_parent_with_distinct_ptc(
        spec, state
    )

    yield from vote_via_child_block(
        spec,
        store,
        block_root,
        block_state,
        positions=range(spec.PAYLOAD_TIMELY_THRESHOLD + 1),
        test_steps=test_steps,
    )

    assert spec.payload_timeliness(store, block_root, timely=True)
    add_payload_vote_checks(store, block_root, test_steps)
    output_head_check(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_payload_timeliness_single_vote_returns_false(spec, state):
    """
    Test that None votes are not counted as timely.
    """
    store, block_root, block_state, test_steps = yield from setup_verified_parent_with_distinct_ptc(
        spec, state
    )

    yield from vote_via_child_block(
        spec,
        store,
        block_root,
        block_state,
        positions=[0],
        test_steps=test_steps,
    )

    assert not spec.payload_timeliness(store, block_root, timely=True)
    add_payload_vote_checks(store, block_root, test_steps)
    output_head_check(spec, store, test_steps)
    yield "steps", test_steps
