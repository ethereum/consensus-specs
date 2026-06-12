from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gloas.proposer_preferences import (
    build_signed_proposer_preferences,
    find_upcoming_proposal_slot,
)
from eth_consensus_specs.test.helpers.gossip import (
    add_pending_block_to_store,
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def advance_state_with_blocks(spec, state, target_slot):
    """
    Advance ``state`` slot-by-slot to ``target_slot`` with empty blocks.
    Returns the signed blocks and their post-states.
    """
    signed_blocks = []
    post_states = []
    while state.slot < target_slot:
        block = build_empty_block_for_next_slot(spec, state)
        signed_blocks.append(state_transition_and_sign_block(spec, state, block))
        post_states.append(state.copy())
    return signed_blocks, post_states


def setup_store_with_advanced_state(spec, state, target_slot):
    """
    Build a genesis store and advance ``state`` slot-by-slot to ``target_slot``,
    adding each intermediate signed block to ``store.blocks`` and the resulting
    state to ``store.block_states``. Returns the store and the list of blocks.
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    blocks = [signed_anchor]
    signed_blocks, post_states = advance_state_with_blocks(spec, state, target_slot)
    for signed_block, post_state in zip(signed_blocks, post_states, strict=True):
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = post_state
        blocks.append(signed_block)
    return store, blocks


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__valid(spec, state):
    """A well-formed SignedProposerPreferences for an upcoming proposal passes gossip."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state)
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__ignore_past_lookahead(spec, state):
    """Preferences whose proposal slot is past the proposer lookahead are ignored."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    # Pick a slot far past the lookahead window.
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    far_future_slot = spec.Slot(
        proposal_slot + spec.SLOTS_PER_EPOCH * (spec.MIN_SEED_LOOKAHEAD + 2)
    )
    # dependent_root for a far-future slot would underflow get_block_root_at_slot,
    # so pass a placeholder; this check fires before any dependent_root lookup.
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=far_future_slot,
        validator_index=validator_index,
        dependent_root=spec.Root(),
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "proposal slot is past the proposer lookahead"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__ignore_already_passed(spec, state):
    """Preferences whose proposal slot is already current/past are ignored."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state)
    yield get_filename(signed_prefs), signed_prefs

    # Validate at a time well after the proposal slot has started.
    proposal_slot = signed_prefs.message.proposal_slot
    time_ms = spec.compute_time_at_slot_ms(state, proposal_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 1000
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "proposal slot has already passed"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__ignore_dependent_root_unseen(spec, state):
    """Preferences whose dependent_root has no corresponding block in the store are ignored."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    unknown_dependent_root = spec.Root(b"\xab" * 32)
    signed_prefs = build_signed_proposer_preferences(
        spec, state, dependent_root=unknown_dependent_root
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "dependent root block has not been seen"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__ignore_duplicate(spec, state):
    """The second valid preferences for the same dependent_root and proposal slot is ignored."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state)
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    # First validation populates seen.
    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    # Replay should be ignored.
    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "already seen preferences for this dependent root and proposal slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__reject_wrong_proposer(spec, state):
    """Preferences signed by a validator that is not the slot's proposer are rejected."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    proposal_slot, true_proposer = find_upcoming_proposal_slot(spec, state)
    # Pick a different validator that isn't the proposer for this slot.
    wrong_index = spec.ValidatorIndex(
        next(i for i in range(len(state.validators)) if i != true_proposer)
    )
    signed_prefs = build_signed_proposer_preferences(
        spec, state, proposal_slot=proposal_slot, validator_index=wrong_index
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "validator is not the proposer for the given slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__reject_invalid_signature(spec, state):
    """Preferences with an invalid signature are rejected."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state, valid_signature=False)
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "invalid proposer preferences signature"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__ignore_before_current_epoch(spec, state):
    """Preferences whose proposal slot is in a past epoch are ignored."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    # Pick a proposal slot whose epoch is strictly less than the current epoch.
    past_slot = spec.Slot(0)
    _, validator_index = find_upcoming_proposal_slot(spec, state)
    # The dependent_root for genesis epoch is unreachable; use a placeholder
    # since this check fires before the dependent_root lookup.
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=past_slot,
        validator_index=validator_index,
        dependent_root=spec.Root(),
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "proposal slot is before the current epoch"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__ignore_dependent_root_state_unavailable(spec, state):
    """Preferences whose dependent_root has no corresponding state are ignored."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    signed_blocks, post_states = advance_state_with_blocks(spec, state, target_slot)
    yield "state", state

    signed_prefs = build_signed_proposer_preferences(spec, state)
    dependent_root = signed_prefs.message.dependent_root
    assert dependent_root in [b.message.hash_tree_root() for b in signed_blocks]

    # Import every block normally, except the dependent block: it has been
    # seen but not yet imported, so its post-state is unavailable.
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    blocks_meta = [{"block": get_filename(signed_anchor)}]
    for signed_block, post_state in zip(signed_blocks, post_states, strict=True):
        block_root = signed_block.message.hash_tree_root()
        yield get_filename(signed_block), signed_block
        if block_root == dependent_root:
            add_pending_block_to_store(store, signed_block)
            blocks_meta.append({"block": get_filename(signed_block), "pending": True})
        else:
            store.blocks[block_root] = signed_block.message
            store.block_states[block_root] = post_state
            blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "dependent root state is unavailable"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__reject_dependent_root_at_lookahead_epoch_start(spec, state):
    """
    Preferences whose dependent_root points to a block at the proposal slot's
    proposer lookahead epoch are rejected, not crashed. Such a
    dependent_root cannot be the proposer-lookahead dependent block, and
    advancing its post-state would otherwise trip process_slots.
    """
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    yield "state", state

    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    proposal_epoch = spec.compute_epoch_at_slot(proposal_slot)
    lookahead_epoch = spec.Epoch(proposal_epoch - spec.MIN_SEED_LOOKAHEAD)
    lookahead_epoch_start_slot = spec.compute_start_slot_at_epoch(lookahead_epoch)

    boundary_block = next(
        signed_block
        for signed_block in blocks
        if signed_block.message.slot == lookahead_epoch_start_slot
    )
    dependent_root = boundary_block.message.hash_tree_root()
    assert store.block_states[dependent_root].slot == lookahead_epoch_start_slot

    # Sign valid preferences for the upcoming slot's true proposer, but point
    # dependent_root at the first block whose stored state is exactly at the
    # proposal slot's proposer lookahead epoch.
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        dependent_root=dependent_root,
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "dependent root is not before the proposer lookahead epoch"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__reject_validator_index_out_of_range(spec, state):
    """Preferences whose validator index is past the validator registry are rejected."""
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)
    seen = get_seen(spec)

    # Build a valid prefs signed by the real proposer for the upcoming slot.
    signed_prefs = build_signed_proposer_preferences(spec, state)
    validator_index = signed_prefs.message.validator_index
    # Trim the head state's validator registry so the proposer's index is now
    # past the end. The dependent_root's stored state still has the full
    # registry, so is_valid_proposal_slot continues to pass.
    state.validators = type(state.validators)(*list(state.validators)[:validator_index])
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "validator index out of range"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
