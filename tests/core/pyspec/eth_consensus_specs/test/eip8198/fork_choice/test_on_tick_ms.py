from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import EIP8198
from eth_consensus_specs.test.helpers.eip8198.schedule import slot_duration_schedule_entry
from eth_consensus_specs.test.helpers.fork_choice import (
    add_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_ms_and_append_step,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block

FORK_EPOCH = 2
POST_DURATION_MS = 5000
FORK_CONFIG = {
    "EIP8198_FORK_EPOCH": FORK_EPOCH,
    "SLOT_DURATION_SCHEDULE": (
        slot_duration_schedule_entry(0, 6000),
        slot_duration_schedule_entry(FORK_EPOCH, POST_DURATION_MS),
    ),
}


@with_phases([EIP8198])
@spec_configured_state_test(FORK_CONFIG, activate_at_genesis=True)
def test_on_tick_ms_fork_boundary_and_deadlines(spec, state):
    # This vector starts before EIP-8198, so give the anchor a pre-EIP-8198
    # fork version
    state.fork = spec.Fork(
        previous_version=spec.config.GLOAS_FORK_VERSION,
        current_version=spec.config.HEZE_FORK_VERSION,
        epoch=spec.config.HEZE_FORK_EPOCH,
    )
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    test_steps = []
    fork_slot = spec.Slot(FORK_EPOCH * spec.SLOTS_PER_EPOCH)
    fork_time_ms = spec.compute_slot_start_time_ms(state.genesis_time, fork_slot)

    on_tick_ms_and_append_step(spec, store, fork_time_ms, test_steps)
    assert spec.get_current_slot(store) == fork_slot
    assert spec.get_time_into_slot_ms(store) == 0

    second_post_slot_start_ms = fork_time_ms + POST_DURATION_MS
    on_tick_ms_and_append_step(spec, store, second_post_slot_start_ms, test_steps)
    assert spec.get_current_slot(store) == fork_slot + 1
    assert spec.get_time_into_slot_ms(store) == 0

    second_post_slot = spec.Slot(fork_slot + 1)
    offsets_ms = (
        spec.get_proposer_reorg_cutoff_ms(second_post_slot),
        spec.get_proposer_reorg_cutoff_ms(second_post_slot) + 1,
        spec.get_inclusion_list_due_ms(second_post_slot),
        spec.get_inclusion_list_due_ms(second_post_slot) + 1,
    )
    for offset_ms in offsets_ms:
        on_tick_ms_and_append_step(spec, store, second_post_slot_start_ms + offset_ms, test_steps)
        assert spec.get_current_slot(store) == fork_slot + 1
        assert spec.get_time_into_slot_ms(store) == offset_ms

    yield "steps", test_steps


def run_block_at_attestation_deadline(spec, state, offset):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    fork_slot = spec.Slot(FORK_EPOCH * spec.SLOTS_PER_EPOCH)
    spec.process_slots(state, fork_slot)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_time_ms = spec.compute_time_at_slot_ms(store, block.slot)
    deadline_ms = spec.get_attestation_due_ms(block.slot)
    test_steps = []
    on_tick_ms_and_append_step(spec, store, block_time_ms + deadline_ms + offset, test_steps)
    yield from add_block(spec, store, signed_block, test_steps)

    root = spec.hash_tree_root(block)
    assert store.block_timeliness[root][0] == (offset < 0)
    assert store.proposer_boost_root == (root if offset < 0 else spec.Root())
    yield "steps", test_steps


@with_phases([EIP8198])
@spec_configured_state_test(FORK_CONFIG, activate_at_genesis=True)
def test_block_before_scheduled_attestation_deadline(spec, state):
    yield from run_block_at_attestation_deadline(spec, state, -1)


@with_phases([EIP8198])
@spec_configured_state_test(FORK_CONFIG, activate_at_genesis=True)
def test_block_at_scheduled_attestation_deadline(spec, state):
    yield from run_block_at_attestation_deadline(spec, state, 0)


@with_phases([EIP8198])
@spec_configured_state_test(FORK_CONFIG, activate_at_genesis=True)
def test_block_after_scheduled_attestation_deadline(spec, state):
    yield from run_block_at_attestation_deadline(spec, state, 1)
