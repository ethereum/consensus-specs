from eth_consensus_specs.test.context import (
    spec_state_test,
    with_all_phases_from_to,
    with_altair_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    sign_attestation,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
)
from eth_consensus_specs.test.helpers.constants import (
    ALTAIR,
    GLOAS,
    MAINNET,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_attestation,
    add_block,
    check_head_against_root,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def _apply_base_block_a(spec, state, store, test_steps):
    # On receiving block A at slot `N`
    block = build_empty_block(spec, state, slot=state.slot + 1)
    signed_block_a = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block_a, test_steps)
    head = spec.get_head(store)
    expected_root = signed_block_a.message.hash_tree_root()
    if is_post_gloas(spec):
        assert head.root == expected_root
    else:
        check_head_against_root(spec, store, signed_block_a.message.hash_tree_root())


@with_altair_and_later
@spec_state_test
def test_ex_ante_vanilla(spec, state):
    """
    With a single adversarial attestation
    Objects:
        Block A - slot N
        Block B (parent A) - slot N+1
        Block C (parent A) - slot N+2
        Attestation_1 (Block B); size `1` - slot N+1
    Steps:
        Block A received at N — A is head
        Block C received at N+2 — C is head
        Block B received at N+2 — C is head
        Attestation_1 received at N+2 — C is head
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
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

    # Attestation_1 at slot `N + 1` voting for block B
    def _filter_participant_set(participants):
        return [next(iter(participants))]

    attestation = get_valid_attestation(
        spec,
        state_b,
        slot=state_b.slot,
        signed=False,
        filter_participant_set=_filter_participant_set,
    )
    attestation.data.beacon_block_root = signed_block_b.message.hash_tree_root()
    assert len([i for i in attestation.aggregation_bits if i == 1]) == 1
    sign_attestation(spec, state_b, attestation)

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block B received at N+2 — C is head due to proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Attestation_1 received at N+2 — C is head
    yield from add_attestation(spec, store, attestation, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    yield "steps", test_steps


def _get_greater_than_proposer_boost_score(spec, store, state, proposer_boost_root, root):
    """
    Return the minimum attestation participant count such that attestation_score > proposer_score
    """
    # calculate proposer boost score
    block = store.blocks[root]
    proposer_score = 0
    if spec.get_ancestor(store, root, block.slot) == proposer_boost_root:
        num_validators = len(
            spec.get_active_validator_indices(state, spec.get_current_epoch(state))
        )
        avg_balance = spec.get_total_active_balance(state) // num_validators
        committee_size = num_validators // spec.SLOTS_PER_EPOCH
        committee_weight = committee_size * avg_balance
        proposer_score = (committee_weight * spec.config.PROPOSER_SCORE_BOOST) // 100

    # calculate minimum participant count such that attestation_score > proposer_score
    base_effective_balance = state.validators[0].effective_balance

    return proposer_score // base_effective_balance + 1


# TODO(jtraglia): Investigate why this doesn't work with Gloas
@with_all_phases_from_to(ALTAIR, GLOAS)
@with_presets([MAINNET], reason="to create non-duplicate committee")
@spec_state_test
def test_ex_ante_attestations_is_greater_than_proposer_boost_with_boost(spec, state):
    """
    Adversarial attestations > proposer boost
    Objects:
        Block A - slot N
        Block B (parent A) - slot N+1
        Block C (parent A) - slot N+2
        Attestation_set_1 (Block B); size `proposer_boost + 1` - slot N+1
    Steps:
        Block A received at N — A is head
        Block C received at N+2 — C is head
        Block B received at N+2 — C is head
        Attestation_1 received at N+2 — B is head
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
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

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block B received at N+2 — C is head due to proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Attestation_set_1 at slot `N + 1` voting for block B
    proposer_boost_root = signed_block_b.message.hash_tree_root()
    root = signed_block_b.message.hash_tree_root()
    participant_num = _get_greater_than_proposer_boost_score(
        spec, store, state, proposer_boost_root, root
    )

    def _filter_participant_set(participants):
        return [index for i, index in enumerate(participants) if i < participant_num]

    attestation = get_valid_attestation(
        spec,
        state_b,
        slot=state_b.slot,
        signed=False,
        filter_participant_set=_filter_participant_set,
    )
    attestation.data.beacon_block_root = signed_block_b.message.hash_tree_root()
    assert len([i for i in attestation.aggregation_bits if i == 1]) == participant_num
    sign_attestation(spec, state_b, attestation)

    # Attestation_set_1 received at N+2 — B is head because B's attestation_score > C's proposer_score.
    # (B's proposer_score = C's attestation_score = 0)
    yield from add_attestation(spec, store, attestation, test_steps)
    check_head_against_root(spec, store, signed_block_b.message.hash_tree_root())

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_ex_ante_sandwich_without_attestations(spec, state):
    """
    Simple Sandwich test with boost and no attestations.
    Objects:
        Block A - slot N
        Block B (parent A) - slot N+1
        Block C (parent A) - slot N+2
        Block D (parent B) - slot N+3
    Steps:
        Block A received at N — A is head
        Block C received at N+2 — C is head
        Block B received at N+2 — C is head (with boost)
        Block D received at N+3 — D is head (with boost)
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
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

    # Block D at slot `N + 3`, parent is B
    state_d = state_b.copy()
    block = build_empty_block(spec, state_d, slot=state_a.slot + 3)
    signed_block_d = state_transition_and_sign_block(spec, state_d, block)

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block B received at N+2 — C is head, it has proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block D received at N+3 - D is head, it has proposer score boost
    time = state_d.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_d, test_steps)
    check_head_against_root(spec, store, signed_block_d.message.hash_tree_root())

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_ex_ante_sandwich_with_honest_attestation(spec, state):
    """
    Boosting necessary to sandwich attack.
    Objects:
        Block A - slot N
        Block B (parent A) - slot N+1
        Block C (parent A) - slot N+2
        Block D (parent B) - slot N+3
        Attestation_1 (Block C); size 1 - slot N+2 (honest)
    Steps:
        Block A received at N — A is head
        Block C received at N+2 — C is head
        Block B received at N+2 — C is head
        Attestation_1 received at N+3 — C is head
        Block D received at N+3 — D is head

    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
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

    # Attestation_1 at N+2 voting for block C
    def _filter_participant_set(participants):
        return [next(iter(participants))]

    attestation = get_valid_attestation(
        spec,
        state_c,
        slot=state_c.slot,
        signed=False,
        filter_participant_set=_filter_participant_set,
    )
    attestation.data.beacon_block_root = signed_block_c.message.hash_tree_root()
    assert len([i for i in attestation.aggregation_bits if i == 1]) == 1
    sign_attestation(spec, state_c, attestation)

    # Block D at slot `N + 3`, parent is B
    state_d = state_b.copy()
    block = build_empty_block(spec, state_d, slot=state_a.slot + 3)
    signed_block_d = state_transition_and_sign_block(spec, state_d, block)

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block B received at N+2 — C is head, it has proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Attestation_1 received at N+3 — C is head
    time = state_d.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_attestation(spec, store, attestation, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block D received at N+3 - D is head, it has proposer score boost
    yield from add_block(spec, store, signed_block_d, test_steps)
    check_head_against_root(spec, store, signed_block_d.message.hash_tree_root())

    yield "steps", test_steps


# TODO(jtraglia): Investigate why this doesn't work with Gloas
@with_all_phases_from_to(ALTAIR, GLOAS)
@with_presets([MAINNET], reason="to create non-duplicate committee")
@spec_state_test
def test_ex_ante_sandwich_with_boost_not_sufficient(spec, state):
    """
    Boost not sufficient to sandwich attack.
    Objects:
        Block A - slot N
        Block B (parent A) - slot N+1
        Block C (parent A) - slot N+2
        Block D (parent B) - slot N+3
        Attestation_set_1 (Block C); size proposer_boost + 1 - slot N+2
    Steps:
        Block A received at N — A is head
        Block C received at N+2 — C is head
        Block B received at N+2 — C is head
        Attestation_set_1 received — C is head
        Block D received at N+3 — C is head
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
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

    # Block D at slot `N + 3`, parent is B
    state_d = state_b.copy()
    block = build_empty_block(spec, state_d, slot=state_a.slot + 3)
    signed_block_d = state_transition_and_sign_block(spec, state_d, block)

    # Block C received at N+2 — C is head
    time = state_c.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_c, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block B received at N+2 — C is head, it has proposer score boost
    yield from add_block(spec, store, signed_block_b, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Attestation_set_1 at N+2 voting for block C
    proposer_boost_root = signed_block_c.message.hash_tree_root()
    root = signed_block_c.message.hash_tree_root()
    participant_num = _get_greater_than_proposer_boost_score(
        spec, store, state, proposer_boost_root, root
    )

    def _filter_participant_set(participants):
        return [index for i, index in enumerate(participants) if i < participant_num]

    attestation = get_valid_attestation(
        spec,
        state_c,
        slot=state_c.slot,
        signed=False,
        filter_participant_set=_filter_participant_set,
    )
    attestation.data.beacon_block_root = signed_block_c.message.hash_tree_root()
    assert len([i for i in attestation.aggregation_bits if i == 1]) == participant_num
    sign_attestation(spec, state_c, attestation)

    # Attestation_1 received at N+3 — B is head because B's attestation_score > C's proposer_score.
    # (B's proposer_score = C's attestation_score = 0)
    time = state_d.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_attestation(spec, store, attestation, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    # Block D received at N+3 - C is head, D's boost not sufficient!
    yield from add_block(spec, store, signed_block_d, test_steps)
    check_head_against_root(spec, store, signed_block_c.message.hash_tree_root())

    yield "steps", test_steps
