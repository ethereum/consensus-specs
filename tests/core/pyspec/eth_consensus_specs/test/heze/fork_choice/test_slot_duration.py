from eth_utils import encode_hex

from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_heze_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_block_file_name,
    get_formatted_head_output,
)
from eth_consensus_specs.test.helpers.state import (
    next_slots,
    state_transition_and_sign_block,
)


@with_heze_and_later
@spec_configured_state_test({"HEZE_FORK_EPOCH": 1}, activate_at_genesis=True)
def test_on_block_across_slot_duration_change(spec, state):
    """
    Anchor at the first slot of the fork epoch, skip until the shuffling
    dependent root is a descendant of the anchor, then add a block at the start
    of every slot for two epochs, so block timeliness and proposer boost follow
    the slot clock across the slot duration change.
    """
    fork_epoch = spec.config.HEZE_FORK_EPOCH
    assert spec.get_slot_duration_ms(fork_epoch) != spec.get_slot_duration_ms(fork_epoch - 1)

    fork_slot = spec.compute_start_slot_at_epoch(fork_epoch)
    next_slots(spec, state, fork_slot - state.slot - 1)
    anchor_block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, anchor_block)
    assert state.slot == fork_slot

    yield "anchor_state", state
    yield "anchor_block", anchor_block

    test_steps = []
    store = spec.get_forkchoice_store(state, anchor_block)

    first_block_slot = spec.compute_start_slot_at_epoch(fork_epoch + 2)
    next_slots(spec, state, first_block_slot - state.slot - 1)

    for _ in range(2 * spec.SLOTS_PER_EPOCH):
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        slot_time_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, block.slot)
        spec.on_tick(store, slot_time_ms)
        test_steps.append({"tick": int(spec.milliseconds_to_seconds(slot_time_ms))})
        spec.on_block(store, signed_block)
        yield get_block_file_name(signed_block), signed_block
        test_steps.append({"block": get_block_file_name(signed_block)})

        block_root = signed_block.message.hash_tree_root()
        assert store.proposer_boost_root == block_root
        test_steps.append(
            {
                "checks": {
                    "time": int(spec.milliseconds_to_seconds(store.time_ms)),
                    "head": get_formatted_head_output(spec, store),
                    "proposer_boost_root": encode_hex(block_root),
                }
            }
        )

    yield "steps", test_steps
