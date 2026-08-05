from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
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
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state)
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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


def setup_lookahead_window(spec, state):
    """
    Advance to the start of an epoch, where the proposal slots that pass
    validation are exactly the span of ``state.proposer_lookahead``. Returns the
    store, the blocks, that epoch's start slot, and the first slot past the
    lookahead window.
    """
    epoch = spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 2)
    epoch_start_slot = spec.compute_start_slot_at_epoch(epoch)
    store, blocks = setup_store_with_advanced_state(spec, state, epoch_start_slot)
    past_window_slot = spec.compute_start_slot_at_epoch(
        spec.Epoch(epoch + spec.MIN_SEED_LOOKAHEAD + 1)
    )
    return store, blocks, epoch_start_slot, past_window_slot


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__ignore_slot_before_lookahead(spec, state):
    """Preferences for the slot just below the lookahead window are ignored.

    That slot is the last one of the previous epoch, so at the epoch start it
    has already started.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    store, blocks, epoch_start_slot, _ = setup_lookahead_window(spec, state)

    proposal_block = blocks[-2].message
    assert proposal_block.slot == epoch_start_slot - 1

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_block.slot,
        validator_index=proposal_block.proposer_index,
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, epoch_start_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "proposal slot has already started"
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
def test_gossip_proposer_preferences__valid_at_first_lookahead_slot(spec, state):
    """Preferences for the first slot of the lookahead window are valid.

    That slot starts exactly now, so it counts as neither started nor beyond the
    lookahead.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    store, blocks, epoch_start_slot, _ = setup_lookahead_window(spec, state)

    proposal_block = blocks[-1].message
    assert proposal_block.slot == epoch_start_slot

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_block.slot,
        validator_index=proposal_block.proposer_index,
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, epoch_start_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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
def test_gossip_proposer_preferences__valid_at_last_lookahead_slot(spec, state):
    """Preferences for the last slot of the lookahead window are valid.

    This is the only proposal slot that reaches the final entry of
    ``proposer_lookahead``, pinning the index arithmetic against an overrun.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    store, blocks, epoch_start_slot, past_window_slot = setup_lookahead_window(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    proposal_slot = spec.Slot(past_window_slot - 1)
    lookahead_index = proposal_slot - epoch_start_slot
    assert lookahead_index == len(state.proposer_lookahead) - 1
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=state.proposer_lookahead[lookahead_index],
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, epoch_start_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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
def test_gossip_proposer_preferences__ignore_slot_after_lookahead(spec, state):
    """Preferences for the slot just past the lookahead window are ignored.

    Its lookahead epoch has not started, so no proposer is assigned to it yet.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    store, blocks, epoch_start_slot, past_window_slot = setup_lookahead_window(spec, state)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    # The dependent block for this slot is not in the store yet, so pass a
    # placeholder, this check fires before any dependent_root lookup.
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=past_window_slot,
        validator_index=spec.ValidatorIndex(0),
        dependent_root=spec.Root(),
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, epoch_start_slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "proposer for the proposal slot is not yet known"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


def setup_lookahead_boundary_preferences(spec, state):
    """
    Advance to the start of an epoch and build preferences for a proposal at the
    far end of that epoch's proposer lookahead, signed by the proposer taken from
    the lookahead computed at the epoch transition. Returns the store, the
    blocks, the preferences, and the epoch's start slot, whose start time is the
    lookahead lower bound for the proposal slot.
    """
    lookahead_epoch = spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 3)
    lookahead_epoch_start_slot = spec.compute_start_slot_at_epoch(lookahead_epoch)
    store, blocks = setup_store_with_advanced_state(spec, state, lookahead_epoch_start_slot)

    # The dependent block is the last one before the epoch transition.
    dependent_root = blocks[-2].message.hash_tree_root()
    dependent_state = store.block_states[dependent_root]
    assert spec.get_current_epoch(dependent_state) == spec.Epoch(lookahead_epoch - 1)

    lookahead_state = dependent_state.copy()
    spec.process_slots(lookahead_state, lookahead_epoch_start_slot)
    proposal_slot = spec.compute_start_slot_at_epoch(
        spec.Epoch(lookahead_epoch + spec.MIN_SEED_LOOKAHEAD)
    )
    lookahead_index = proposal_slot - lookahead_epoch_start_slot
    signed_prefs = build_signed_proposer_preferences(
        spec,
        lookahead_state,
        proposal_slot=proposal_slot,
        validator_index=lookahead_state.proposer_lookahead[lookahead_index],
        dependent_root=dependent_root,
    )
    return store, blocks, signed_prefs, lookahead_epoch_start_slot


@with_gloas_and_later
@spec_state_test
def test_gossip_proposer_preferences__ignore_outside_lookahead_disparity(spec, state):
    """Preferences validated 1ms before the lookahead lower bound are ignored.

    One ms earlier, the lookahead epoch is still in the future even for a peer
    whose clock is ahead by ``DISPARITY``, so the proposer is not yet known.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    store, blocks, signed_prefs, lookahead_epoch_start_slot = setup_lookahead_boundary_preferences(
        spec, state
    )

    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield get_filename(signed_prefs), signed_prefs

    time_ms = (
        spec.compute_time_at_slot_ms(store, lookahead_epoch_start_slot)
        - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
        - 1
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=get_seen(spec),
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "proposer for the proposal slot is not yet known"
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
def test_gossip_proposer_preferences__valid_at_lookahead_disparity_edge(spec, state):
    """Preferences validated exactly at the lookahead lower bound are valid.

    The proposal slot's proposer is only known once its lookahead epoch starts,
    so that start minus ``DISPARITY`` is the earliest time preferences for it are
    accepted.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    store, blocks, signed_prefs, lookahead_epoch_start_slot = setup_lookahead_boundary_preferences(
        spec, state
    )

    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield get_filename(signed_prefs), signed_prefs

    time_ms = (
        spec.compute_time_at_slot_ms(store, lookahead_epoch_start_slot)
        - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=get_seen(spec),
        store=store,
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
def test_gossip_proposer_preferences__valid_at_slot_start_disparity_edge(spec, state):
    """Preferences validated exactly at the clock-disparity edge are still valid.

    The proposal slot counts as started only once ``current_time_ms`` is more
    than ``DISPARITY`` past its start, so that edge itself is still valid.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state)
    yield get_filename(signed_prefs), signed_prefs

    proposal_slot = signed_prefs.message.proposal_slot
    time_ms = (
        spec.compute_time_at_slot_ms(store, proposal_slot)
        + spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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
def test_gossip_proposer_preferences__ignore_outside_slot_start_disparity(spec, state):
    """Preferences validated 1ms past the clock-disparity window are ignored as started."""
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state)
    yield get_filename(signed_prefs), signed_prefs

    # Past start(proposal_slot) + DISPARITY the slot has started even for a peer
    # whose clock is behind, so the preferences are ignored.
    proposal_slot = signed_prefs.message.proposal_slot
    time_ms = (
        spec.compute_time_at_slot_ms(store, proposal_slot)
        + spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
        + 1
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "proposal slot has already started"
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
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    unknown_dependent_root = spec.Root(b"\xab" * 32)
    signed_prefs = build_signed_proposer_preferences(
        spec, state, dependent_root=unknown_dependent_root
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "dependent block has not been seen"
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
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state)
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    # First validation populates seen.
    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
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

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    signed_prefs = build_signed_proposer_preferences(spec, state, valid_signature=False)
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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
def test_gossip_proposer_preferences__ignore_slot_from_past_epoch(spec, state):
    """Preferences whose proposal slot is in a past epoch are ignored as started.

    The proposal slot is in an epoch below ``MIN_SEED_LOOKAHEAD``, so the
    started-slot check must fire before the proposer lookahead epoch is
    computed for it.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    # Pick a proposal slot whose epoch is strictly less than the current epoch.
    past_slot = spec.Slot(0)
    _, validator_index = find_upcoming_proposal_slot(spec, state)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=past_slot,
        validator_index=validator_index,
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "proposal slot has already started"
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
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    # Build a fork block off the head that has been seen but not yet imported,
    # so its post-state is unavailable. The pending block must be a chain tip:
    # descendants of an unimported block cannot be imported.
    fork_state = state.copy()
    fork_block = build_empty_block_for_next_slot(spec, fork_state)
    fork_block.body.graffiti = spec.Bytes32(b"\x42" * 32)
    signed_fork_block = state_transition_and_sign_block(spec, fork_state, fork_block)
    add_pending_block_to_store(store, signed_fork_block)
    dependent_root = signed_fork_block.message.hash_tree_root()

    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield get_filename(signed_fork_block), signed_fork_block
    yield (
        "blocks",
        "meta",
        [{"block": get_filename(b)} for b in blocks]
        + [{"block": get_filename(signed_fork_block), "pending": True}],
    )

    seen = get_seen(spec)
    signed_prefs = build_signed_proposer_preferences(spec, state, dependent_root=dependent_root)
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "dependent block failed validation"
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
    proposer lookahead epoch are rejected. Such a dependent_root cannot be the
    proposer-lookahead dependent block, since the lookahead for the proposal
    epoch is computed at the start of the lookahead epoch.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
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

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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
def test_gossip_proposer_preferences__ignore_dependent_root_not_possible(spec, state):
    """Preferences whose dependent_root is superseded on every branch are ignored.

    The dependent block is old enough, but its only child is also before the
    lookahead epoch start and it is not the current head, so on no branch can
    it be, or become, the latest block prior to the epoch start.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    # Sign valid preferences for the upcoming slot's true proposer, but point
    # dependent_root at the block two slots before the lookahead epoch start.
    # Its child is at the slot right before the epoch start, so it is already
    # superseded on the only branch.
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    proposal_epoch = spec.compute_epoch_at_slot(proposal_slot)
    lookahead_epoch = spec.Epoch(proposal_epoch - spec.MIN_SEED_LOOKAHEAD)
    superseded_slot = spec.Slot(spec.compute_start_slot_at_epoch(lookahead_epoch) - 2)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        dependent_root=spec.get_block_root_at_slot(state, superseded_slot),
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "dependent root is not a possible dependent block"
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
def test_gossip_proposer_preferences__valid_dependent_root_on_fork(spec, state):
    """Preferences whose dependent_root is a non-canonical fork block are valid.

    On the fork branch, the dependent block's child crosses the lookahead
    epoch start, so on that branch it is the latest block prior to the epoch
    start even though it is not the head.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    store, blocks = setup_store_with_advanced_state(spec, state, target_slot)

    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    proposal_epoch = spec.compute_epoch_at_slot(proposal_slot)
    lookahead_epoch = spec.Epoch(proposal_epoch - spec.MIN_SEED_LOOKAHEAD)
    lookahead_epoch_start_slot = spec.compute_start_slot_at_epoch(lookahead_epoch)

    # Fork off two slots before the lookahead epoch start and build a branch
    # whose first block stays before the epoch start and whose second block
    # crosses it.
    fork_parent_root = spec.get_block_root_at_slot(state, spec.Slot(lookahead_epoch_start_slot - 2))
    fork_state = store.block_states[fork_parent_root].copy()
    fork_blocks = []
    for _ in range(2):
        block = build_empty_block_for_next_slot(spec, fork_state)
        block.body.graffiti = spec.Bytes32(b"\x42" * 32)
        signed_fork_block = state_transition_and_sign_block(spec, fork_state, block)
        block_root = signed_fork_block.message.hash_tree_root()
        store.blocks[block_root] = signed_fork_block.message
        store.block_states[block_root] = fork_state.copy()
        fork_blocks.append(signed_fork_block)
    dependent_root = fork_blocks[0].message.hash_tree_root()
    assert store.blocks[dependent_root].slot == lookahead_epoch_start_slot - 1
    assert fork_blocks[1].message.slot == lookahead_epoch_start_slot

    yield "state", anchor_state
    seen = get_seen(spec)
    for signed in blocks + fork_blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks + fork_blocks]

    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        dependent_root=dependent_root,
    )
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
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
def test_gossip_proposer_preferences__valid_dependent_root_across_empty_epochs(spec, state):
    """
    Preferences remain valid when two empty epochs reuse the same dependent
    root. Validation must advance that root's post-state to the lookahead epoch.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "proposer_preferences"

    current_epoch = spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 2)
    lookahead_epoch_start_slot = spec.compute_start_slot_at_epoch(current_epoch)

    # Build the canonical chain to the slot before two fully empty epochs.
    first_empty_epoch = spec.Epoch(current_epoch - 2)
    dependent_block_slot = spec.Slot(spec.compute_start_slot_at_epoch(first_empty_epoch) - 1)
    store, blocks = setup_store_with_advanced_state(spec, state, dependent_block_slot)
    dependent_root = blocks[-1].message.hash_tree_root()
    dependent_state = state.copy()

    # Skip both epochs, then import the first block at the lookahead boundary.
    boundary_block = build_empty_block(spec, state, slot=lookahead_epoch_start_slot)
    signed_boundary_block = state_transition_and_sign_block(spec, state, boundary_block)
    boundary_root = signed_boundary_block.message.hash_tree_root()
    store.blocks[boundary_root] = signed_boundary_block.message
    store.block_states[boundary_root] = state.copy()
    blocks.append(signed_boundary_block)
    validation_state = state.copy()

    proposal_epoch = spec.Epoch(current_epoch + 1)
    assert spec.get_shuffling_dependent_root(store, boundary_root, current_epoch) == dependent_root
    assert spec.get_shuffling_dependent_root(store, boundary_root, proposal_epoch) == dependent_root

    lookahead_state = dependent_state.copy()
    spec.process_slots(lookahead_state, lookahead_epoch_start_slot)
    # Pick a slot that distinguishes the advanced lookahead from the stale
    # lookahead in the dependent block's post-state.
    for slot_offset in range(spec.SLOTS_PER_EPOCH):
        lookahead_index = spec.MIN_SEED_LOOKAHEAD * spec.SLOTS_PER_EPOCH + slot_offset
        validator_index = lookahead_state.proposer_lookahead[lookahead_index]
        stale_validator_index = dependent_state.proposer_lookahead[lookahead_index]
        if validator_index != stale_validator_index:
            break
    else:
        raise AssertionError("expected advanced proposer lookahead to differ")

    proposal_slot = spec.Slot(spec.compute_start_slot_at_epoch(proposal_epoch) + slot_offset)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        validation_state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        dependent_root=dependent_root,
    )

    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(block)} for block in blocks]
    yield get_filename(signed_prefs), signed_prefs

    time_ms = spec.compute_time_at_slot_ms(store, validation_state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=get_seen(spec),
        store=store,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    yield (
        "messages",
        "meta",
        [
            {
                "current_time_ms": int(time_ms),
                "message": get_filename(signed_prefs),
                "expected": result,
            }
        ],
    )
