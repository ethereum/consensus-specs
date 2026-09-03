from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import state_transition_with_full_block
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import EIP8198, MINIMAL
from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.eip8198.schedule import slot_duration_schedule_entry
from eth_consensus_specs.test.helpers.rewards import transition_state_to_leak
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


@with_phases([EIP8198])
@with_presets([MINIMAL])
@spec_configured_state_test(
    {
        "EIP8198_FORK_EPOCH": 0,
        "SLOT_DURATION_SCHEDULE": (
            slot_duration_schedule_entry(0, 6000),
            slot_duration_schedule_entry(1, 5000),
            slot_duration_schedule_entry(2, 4000),
        ),
    },
    activate_at_genesis=True,
)
def test_slot_duration_changes_with_attestations(spec, state):
    """
    As the slot duration reduces, so does ``get_base_reward_per_increment``.
    """
    yield "pre", state

    blocks = []
    base_reward = spec.get_base_reward_per_increment(state)
    while spec.get_current_epoch(state) < 2:
        blocks.append(
            state_transition_with_full_block(
                spec,
                state,
                fill_cur_epoch=True,
                fill_prev_epoch=True,
            )
        )
        if state.slot % spec.SLOTS_PER_EPOCH == 0:
            previous_base_reward = base_reward
            base_reward = spec.get_base_reward_per_increment(state)
            assert base_reward < previous_base_reward

    yield "blocks", blocks
    yield "post", state


@with_phases([EIP8198])
@with_presets([MINIMAL])
@spec_configured_state_test(
    {
        "EIP8198_FORK_EPOCH": 0,
        "SLOT_DURATION_SCHEDULE": (
            slot_duration_schedule_entry(0, 6000),
            slot_duration_schedule_entry(7, 5000),
            slot_duration_schedule_entry(8, 4000),
        ),
    },
    activate_at_genesis=True,
)
def test_slot_duration_changes_in_inactivity_leak(spec, state):
    """
    As the slot duration reduces, ``get_inactivity_penalty_deltas`` increases.
    """
    transition_state_to_leak(spec, state)
    assert spec.is_in_inactivity_leak(state)
    assert spec.get_current_epoch(state) == 6

    yield "pre", state

    blocks = []
    penalty = spec.get_inactivity_penalty_deltas(state)[1][0]
    while spec.get_current_epoch(state) < 8:
        block = build_empty_block_for_next_slot(spec, state)
        blocks.append(state_transition_and_sign_block(spec, state, block))
        if state.slot % spec.SLOTS_PER_EPOCH == 0:
            previous_penalty = penalty
            penalty = spec.get_inactivity_penalty_deltas(state)[1][0]
            assert penalty > previous_penalty

    yield "blocks", blocks
    yield "post", state


@with_phases([EIP8198])
@with_presets([MINIMAL])
@spec_configured_state_test(
    {
        "EIP8198_FORK_EPOCH": 0,
        "SLOT_DURATION_SCHEDULE": (
            slot_duration_schedule_entry(0, 6000),
            slot_duration_schedule_entry(1, 5000),
            slot_duration_schedule_entry(2, 4000),
        ),
    },
    activate_at_genesis=True,
)
def test_slot_duration_changes_with_pending_deposits(spec, state):
    """
    As the slot duration reduces, so does ``get_activation_churn_limit``.
    """
    for index in range(16):
        state.pending_deposits.append(
            prepare_pending_deposit(
                spec,
                index,
                spec.MIN_ACTIVATION_BALANCE,
            )
        )

    yield "pre", state

    blocks = []
    churn = spec.get_activation_churn_limit(state)
    while spec.get_current_epoch(state) < 2:
        block = build_empty_block_for_next_slot(spec, state)
        blocks.append(state_transition_and_sign_block(spec, state, block))
        if state.slot % spec.SLOTS_PER_EPOCH == 0:
            previous_churn = churn
            churn = spec.get_activation_churn_limit(state)
            assert churn < previous_churn

    yield "blocks", blocks
    yield "post", state


@with_phases([EIP8198])
@with_presets([MINIMAL])
@spec_configured_state_test(
    {
        "EIP8198_FORK_EPOCH": 0,
        "SLOT_DURATION_SCHEDULE": (
            slot_duration_schedule_entry(0, 6000),
            slot_duration_schedule_entry(1, 5000),
            slot_duration_schedule_entry(2, 4000),
        ),
    },
    activate_at_genesis=True,
)
def test_slot_duration_changes_with_ejections(spec, state):
    """
    As the slot duration reduces, so does ``get_exit_churn_limit``.
    """
    for index in range(8):
        state.balances[index] = spec.config.EJECTION_BALANCE

    yield "pre", state

    blocks = []
    churn = spec.get_exit_churn_limit(state)
    while spec.get_current_epoch(state) < 2:
        block = build_empty_block_for_next_slot(spec, state)
        blocks.append(state_transition_and_sign_block(spec, state, block))
        if state.slot % spec.SLOTS_PER_EPOCH == 0:
            previous_churn = churn
            churn = spec.get_exit_churn_limit(state)
            assert churn < previous_churn

    yield "blocks", blocks
    yield "post", state
