from frozendict import frozendict

from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import EIP8198, MINIMAL
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


@with_phases([EIP8198])
@with_presets([MINIMAL])
@spec_configured_state_test(
    {
        "EIP8198_FORK_EPOCH": 0,
        "SLOT_DURATION_SCHEDULE": (
            frozendict({"EPOCH": 1, "SLOT_DURATION_MS": 5000}),
            frozendict({"EPOCH": 2, "SLOT_DURATION_MS": 4000}),
        ),
    },
    activate_at_genesis=True,
)
def test_slot_duration_changes(spec, state):
    yield "pre", state

    blocks = []
    while state.slot < 3 * spec.SLOTS_PER_EPOCH:
        block = build_empty_block_for_next_slot(spec, state)
        blocks.append(state_transition_and_sign_block(spec, state, block))

    yield "blocks", blocks
    yield "post", state
