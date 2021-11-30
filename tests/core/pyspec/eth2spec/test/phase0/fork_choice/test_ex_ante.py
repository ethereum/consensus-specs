from eth2spec.test.context import (
    MAINNET,
    spec_configured_state_test,
    spec_state_test,
    with_all_phases,
    with_presets,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
    sign_attestation,
)
from eth2spec.test.helpers.block import (
    build_empty_block,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    add_attestation,
    add_block,
    tick_and_add_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)


def _apply_base_block_a(spec, state, store, test_steps):
    # On receiving block A at slot `N`
    block = build_empty_block(spec, state, slot=state.slot + 1)
    signed_block_a = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block_a, test_steps)
    assert spec.get_head(store) == signed_block_a.message.hash_tree_root()


@with_all_phases
@spec_state_test
def test_ex_ante_secnario_1_with_boost(spec, state):
    """
    With a single adversarial attestation

    Block A - slot N
    Block B (parent A) - slot N+1
    Block C (parent A) - slot N+2
    Attestation_1 (Block B) - slot N+1 – size 1
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving block A at slot `N`
    yield from _apply_base_block_a(spec, state, store, test_steps)
    state_a = state.copy()

    # Block B at slot `N + 1`, parent is A
    state_b = state_a.copy()
    block = build_empty_block(spec, state_a, slot=state_a.slot + 1)
    signed_block_b = state_transition_and_sign_block(spec, state_b, block)

    # Block C at slot `N + 2`, parent is A
    state_c = state_a.copy()
    block = build_empty_block(spec, state_c, slot=state_a.slot + 2)
    signed_block_c = state_transition_and_sign_block(spec, state_c, block)

    # Attestation_1 received at N+2 — B is head due to boost proposer
    def _filter_participant_set(participants):
        return [next(iter(participants))]

    attestation = get_valid_attestation(
        spec, state_b, slot=state_b.slot, signed=False, filter_participant_set=_filter_participant_set
    )
    attestation.data.beacon_block_root = signed_block_b.message.hash_tree_root()
    assert len([i for i in attestation.aggregation_bits if i == 1]) == 1
    sign_attestation(spec, state_b, attestation)

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    # Block B received at N+2 — C is head that has higher proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    # Attestation_1 received at N+2 — C is head
    yield from add_attestation(spec, store, attestation, test_steps)
    assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    yield 'steps', test_steps


@with_all_phases
@spec_configured_state_test({
    'PROPOSER_SCORE_BOOST': 0,
})
def test_ex_ante_secnario_1_without_boost(spec, state):
    """
    With a single adversarial attestation

    NOTE: this case disabled proposer score boost by setting config `PROPOSER_SCORE_BOOST` to `0`

    Block A - slot N
    Block B (parent A) - slot N+1
    Block C (parent A) - slot N+2
    Attestation_1 (Block B) - slot N+1 – size 1
    """
    # For testing `PROPOSER_SCORE_BOOST = 0` case
    yield 'PROPOSER_SCORE_BOOST', 'meta', 0

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving block A at slot `N`
    yield from _apply_base_block_a(spec, state, store, test_steps)
    state_a = state.copy()

    # Block B at slot `N + 1`, parent is A
    state_b = state_a.copy()
    block = build_empty_block(spec, state_a, slot=state_a.slot + 1)
    signed_block_b = state_transition_and_sign_block(spec, state_b, block)

    # Block C at slot `N + 2`, parent is A
    state_c = state_a.copy()
    block = build_empty_block(spec, state_c, slot=state_a.slot + 2)
    signed_block_c = state_transition_and_sign_block(spec, state_c, block)

    # Attestation_1 received at N+2 — B is head due to boost proposer
    def _filter_participant_set(participants):
        return [next(iter(participants))]

    attestation = get_valid_attestation(
        spec, state_b, slot=state_b.slot, signed=False, filter_participant_set=_filter_participant_set
    )
    attestation.data.beacon_block_root = signed_block_b.message.hash_tree_root()
    assert len([i for i in attestation.aggregation_bits if i == 1]) == 1
    sign_attestation(spec, state_b, attestation)

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    # Block B received at N+2
    # Block B and C has the same score 0. Use a lexicographical order for tie-breaking.
    yield from add_block(spec, store, signed_block_b, test_steps)
    if signed_block_b.message.hash_tree_root() >= signed_block_c.message.hash_tree_root():
        assert spec.get_head(store) == signed_block_b.message.hash_tree_root()
    else:
        assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    # Attestation_1 received at N+2 — B is head
    yield from add_attestation(spec, store, attestation, test_steps)
    assert spec.get_head(store) == signed_block_b.message.hash_tree_root()

    yield 'steps', test_steps


@with_all_phases
@with_presets([MAINNET], reason="to create larger committee")
@spec_state_test
def test_ex_ante_attestations_is_greater_than_proposer_boost_with_boost(spec, state):
    """
    Adversarial attestations > proposer boost

    Block A - slot N
    Block B (parent A) - slot N+1
    Block C (parent A) - slot N+2
    Attestation_1 (Block B) - slot N+1 – size > proposer_boost
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving block A at slot `N`
    yield from _apply_base_block_a(spec, state, store, test_steps)
    state_a = state.copy()

    # Block B at slot `N + 1`, parent is A
    state_b = state_a.copy()
    block = build_empty_block(spec, state_a, slot=state_a.slot + 1)
    signed_block_b = state_transition_and_sign_block(spec, state_b, block)

    # Block C at slot `N + 2`, parent is A
    state_c = state_a.copy()
    block = build_empty_block(spec, state_c, slot=state_a.slot + 2)
    signed_block_c = state_transition_and_sign_block(spec, state_c, block)

    # Full attestation received at N+2 — B is head due to boost proposer
    attestation = get_valid_attestation(spec, state_b, slot=state_b.slot, signed=False)
    attestation.data.beacon_block_root = signed_block_b.message.hash_tree_root()
    assert len([i for i in attestation.aggregation_bits if i == 1]) > 1
    sign_attestation(spec, state_b, attestation)

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    # Block B received at N+2 — C is head that has higher proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    # Attestation_1 received at N+2 — B is head because B's attestation_score > C's proposer_score.
    # (B's proposer_score = C's attestation_score = 0)
    yield from add_attestation(spec, store, attestation, test_steps)
    assert spec.get_head(store) == signed_block_b.message.hash_tree_root()

    yield 'steps', test_steps


@with_all_phases
@spec_configured_state_test({
    'PROPOSER_SCORE_BOOST': 0,
})
@with_presets([MAINNET], reason="to create larger committee")
def test_ex_ante_attestations_is_greater_than_proposer_boost_without_boost(spec, state):
    """
    Adversarial attestations > proposer boost

    Block A - slot N
    Block B (parent A) - slot N+1
    Block C (parent A) - slot N+2
    Attestation_1 (Block B) - slot N+1 – size > proposer_boost
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving block A at slot `N`
    yield from _apply_base_block_a(spec, state, store, test_steps)
    state_a = state.copy()

    # Block B at slot `N + 1`, parent is A
    state_b = state_a.copy()
    block = build_empty_block(spec, state_a, slot=state_a.slot + 1)
    signed_block_b = state_transition_and_sign_block(spec, state_b, block)

    # Block C at slot `N + 2`, parent is A
    state_c = state_a.copy()
    block = build_empty_block(spec, state_c, slot=state_a.slot + 2)
    signed_block_c = state_transition_and_sign_block(spec, state_c, block)

    # Full attestation received at N+2 — B is head due to boost proposer
    attestation = get_valid_attestation(spec, state_b, slot=state_b.slot, signed=False)
    attestation.data.beacon_block_root = signed_block_b.message.hash_tree_root()
    assert len([i for i in attestation.aggregation_bits if i == 1]) > 1
    sign_attestation(spec, state_b, attestation)

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    # Block B received at N+2
    # Block B and C has the same score 0. Use a lexicographical order for tie-breaking.
    yield from add_block(spec, store, signed_block_b, test_steps)
    if signed_block_b.message.hash_tree_root() >= signed_block_c.message.hash_tree_root():
        assert spec.get_head(store) == signed_block_b.message.hash_tree_root()
    else:
        assert spec.get_head(store) == signed_block_c.message.hash_tree_root()

    # Attestation_1 received at N+2 — B is head because B's attestation_score > C's attestation_score
    yield from add_attestation(spec, store, attestation, test_steps)
    assert spec.get_head(store) == signed_block_b.message.hash_tree_root()

    yield 'steps', test_steps
