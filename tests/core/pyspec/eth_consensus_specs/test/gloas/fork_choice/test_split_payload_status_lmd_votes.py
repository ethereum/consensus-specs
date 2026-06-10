"""
Fork-choice scenarios that split LMD votes across the FULL and EMPTY payload
variants of the same beacon block root.

Under EIP-7732 ePBS, each accepted ``LatestMessage`` for a block ``B`` resolves
through ``get_supported_node`` to one of two distinct fork-choice nodes
depending on ``payload_present``:

  * ``ForkChoiceNode(root=B, payload_status=PAYLOAD_STATUS_FULL)``
  * ``ForkChoiceNode(root=B, payload_status=PAYLOAD_STATUS_EMPTY)``

The reference spec recomputes ``get_attestation_score`` from scratch via
``sum(...)`` over ``store.latest_messages`` each time, so it does not maintain
running per-node weights. Implementations that keep incremental running
weights must apply add/subtract operations as ``LatestMessage`` entries
change across the two payload variants.

This module exercises a minimal trace where both payload variants of the same
root receive non-zero LMD weight in the same store, which an incremental
implementation must reflect in two independent running totals.
"""

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_attestation,
    add_execution_payload,
    check_head_against_root,
    output_store_checks,
    setup_one_block_store,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.state import (
    next_slots,
)


def _expected_score(spec, state, store, target_node):
    """Reference computation of ``get_attestation_score`` for ``target_node``."""
    current_epoch = spec.get_current_epoch(state)
    active_indices = spec.get_active_validator_indices(state, current_epoch)
    total = 0
    for i in active_indices:
        if state.validators[i].slashed:
            continue
        if i not in store.latest_messages:
            continue
        if i in store.equivocating_indices:
            continue
        supported = spec.get_supported_node(store, store.latest_messages[i])
        if spec.is_ancestor(store, supported, target_node):
            total += state.validators[i].effective_balance
    return spec.Gwei(total)


@with_gloas_and_later
@spec_state_test
def test_lmd_vote_split_across_payload_status_variants(spec, state):
    """
    Both payload variants of the same beacon block root receive LMD weight.

    Trace:
      1. Apply ``block_1`` at slot 1 and reveal its execution payload envelope,
         so ``(block_1, FULL)`` is a viable fork-choice node.
      2. Tick to slot 2; a full beacon committee attests ``beacon_block_root =
         block_1`` with ``payload_index = 1`` (``payload_present = True``).
         These attesters' ``LatestMessage`` entries resolve to
         ``(block_1, FULL)``.
      3. Tick to slot 3; a separate full beacon committee attests
         ``beacon_block_root = block_1`` with ``payload_index = 0``
         (``payload_present = False``). These attesters' ``LatestMessage``
         entries resolve to ``(block_1, EMPTY)``.

    The reference spec, being stateless in weight computation, simply returns
    a non-zero ``get_attestation_score`` for each variant. Incremental
    fork-choice implementations must independently maintain a running weight
    for ``(block_1, FULL)`` and ``(block_1, EMPTY)`` from this same trace.
    """
    # --- Initialisation -----------------------------------------------------
    store, block_1_root, _, signed_block_1, test_steps = yield from setup_one_block_store(
        spec, state
    )

    # --- Reveal block_1's execution payload --------------------------------
    envelope = build_signed_execution_payload_envelope(spec, state, block_1_root, signed_block_1)
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=True)

    # Sanity: payload is verified, FULL variant is now the head node.
    assert block_1_root in store.payloads
    assert spec.is_payload_verified(store, block_1_root)
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL
    check_head_against_root(spec, store, block_1_root)

    # --- Slot 2: a committee credits (block_1, FULL) -----------------------
    state_slot_2 = state.copy()
    next_slots(spec, state_slot_2, spec.Slot(2) - state_slot_2.slot)
    tick_store_to_slot(spec, store, state_slot_2.slot + 1, test_steps)

    full_attestation = get_valid_attestation(
        spec,
        state_slot_2,
        slot=state_slot_2.slot,
        index=0,
        payload_index=1,
        beacon_block_root=block_1_root,
        signed=True,
    )
    full_voters = list(spec.get_attesting_indices(state_slot_2, full_attestation))
    assert len(full_voters) >= 1, "FULL attestation must have at least one voter"
    yield from add_attestation(spec, store, full_attestation, test_steps)

    # Every FULL attester's LatestMessage records payload_present=True.
    for v in full_voters:
        assert v in store.latest_messages
        assert store.latest_messages[v].root == block_1_root
        assert store.latest_messages[v].payload_present is True
        assert store.latest_messages[v].slot == state_slot_2.slot

    # --- Slot 3: a different committee credits (block_1, EMPTY) ------------
    state_slot_3 = state_slot_2.copy()
    next_slots(spec, state_slot_3, 1)
    tick_store_to_slot(spec, store, state_slot_3.slot + 1, test_steps)

    empty_attestation = get_valid_attestation(
        spec,
        state_slot_3,
        slot=state_slot_3.slot,
        index=0,
        payload_index=0,
        beacon_block_root=block_1_root,
        signed=True,
    )
    empty_voters = list(spec.get_attesting_indices(state_slot_3, empty_attestation))
    assert len(empty_voters) >= 1, "EMPTY attestation must have at least one voter"
    yield from add_attestation(spec, store, empty_attestation, test_steps)

    # FULL voters that are not also in the slot-3 committee keep
    # payload_present=True. Any overlap moves to payload_present=False because
    # the slot-3 message strictly supersedes the slot-2 one (slot > previous).
    for v in empty_voters:
        assert v in store.latest_messages
        assert store.latest_messages[v].root == block_1_root
        assert store.latest_messages[v].payload_present is False
        assert store.latest_messages[v].slot == state_slot_3.slot

    full_minus_empty = [v for v in full_voters if v not in set(empty_voters)]
    for v in full_minus_empty:
        assert store.latest_messages[v].payload_present is True
        assert store.latest_messages[v].slot == state_slot_2.slot

    # --- Spec-level invariants on the split LMD vote -----------------------
    justified_state = store.checkpoint_states[store.justified_checkpoint]
    full_node = spec.ForkChoiceNode(root=block_1_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    empty_node = spec.ForkChoiceNode(root=block_1_root, payload_status=spec.PAYLOAD_STATUS_EMPTY)
    full_score = spec.get_attestation_score(store, full_node, justified_state)
    empty_score = spec.get_attestation_score(store, empty_node, justified_state)

    # Pre-calculate the expected per-variant weights directly from the LMD
    # state: each variant's score is the sum of effective balances of the
    # validators whose LatestMessage resolves to that variant.
    expected_full_score = _expected_score(spec, justified_state, store, full_node)
    expected_empty_score = _expected_score(spec, justified_state, store, empty_node)

    assert full_score == expected_full_score
    assert empty_score == expected_empty_score
    assert expected_empty_score > 0
    if full_minus_empty:
        assert expected_full_score > 0
    else:
        # If every FULL voter also appeared in the slot-3 committee they have
        # all moved to EMPTY and FULL ends up empty. Still a valid trace.
        assert expected_full_score == 0

    # The total weight in flight is the union of voters; never more.
    union_balance = sum(
        justified_state.validators[v].effective_balance
        for v in set(full_voters) | set(empty_voters)
        if not justified_state.validators[v].slashed
    )
    assert full_score + empty_score <= union_balance, (
        "Sum of FULL and EMPTY attestation_score must not exceed the union "
        "of attester effective balances; double-counting is a fork-choice bug."
    )

    # Emit per-viable-leaf weights so consumers can compare their incremental
    # running totals for (block_1, FULL) and (block_1, EMPTY) against the
    # reference values produced by the stateless spec computation.
    output_store_checks(spec, store, test_steps, with_viable_for_head_weights=True)

    yield "steps", test_steps
