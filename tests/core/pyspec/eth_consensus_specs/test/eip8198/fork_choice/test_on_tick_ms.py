from frozendict import frozendict

from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import EIP8198
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_ms_and_append_step,
)

FORK_EPOCH = 2
POST_DURATION_MS = 5000
FORK_CONFIG = {
    "EIP8198_FORK_EPOCH": FORK_EPOCH,
    "SLOT_DURATION_SCHEDULE": (
        frozendict({"EPOCH": FORK_EPOCH, "SLOT_DURATION_MS": POST_DURATION_MS}),
    ),
}


@with_phases([EIP8198])
@spec_configured_state_test(FORK_CONFIG, activate_at_genesis=True)
def test_on_tick_ms_fork_boundary_and_deadlines(spec, state):
    # The generic state factory initializes the module's own fork version.
    # This vector starts before EIP-8198, so make the anchor an internally
    # consistent post-Heze, pre-EIP-8198 state.
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
