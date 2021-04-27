from copy import deepcopy

from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)
from eth2spec.test.helpers.attestations import get_valid_late_attestation
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.fork_choice import (
    tick_and_run_on_block,
    get_anchor_root,
    get_genesis_forkchoice_store_and_block,
    get_formatted_head_output,
)
from eth2spec.test.helpers.state import (
    next_slots,
    state_transition_and_sign_block,
)


@with_all_phases
@spec_state_test
def test_finality_delay_fix(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block

    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    # Progress the chain to a point just before the withheld block
    for i in range(spec.SLOTS_PER_EPOCH - 1):
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_run_on_block(spec, store, signed_block, test_steps)

    attacker_state = deepcopy(state)
    attacker_store = deepcopy(store)

    attacker_blocks = []
    attacker_signed_blocks = []

    attack_length = 2

    for i in range(attack_length):
        attacker_blocks.append(build_empty_block_for_next_slot(spec, attacker_state))
        attacker_signed_blocks.append(state_transition_and_sign_block(spec, attacker_state, attacker_blocks[i]))
        yield from tick_and_run_on_block(spec, attacker_store, attacker_signed_blocks[i], test_steps)

    # Build attestation from honest node, for an empty slot
    next_slots(spec, state, attack_length + 1)
    spec.on_tick(store, store.genesis_time + state.slot * spec.SECONDS_PER_SLOT)
    attestation = get_valid_late_attestation(spec, state, slot=attacker_blocks[-1].slot,
                                             index=None, signed=True)
    spec.on_attestation(store, attestation)
    honest_head_block_root = spec.get_head(store)
    for signed_attack_block in attacker_signed_blocks:
        spec.on_block(store, signed_attack_block)

    # Check that the honest node's head block has not changed
    assert spec.get_head(store) == honest_head_block_root
