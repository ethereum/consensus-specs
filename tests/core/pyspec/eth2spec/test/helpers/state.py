from eth2spec.test.context import expect_assertion_error, is_post_altair
from eth2spec.test.helpers.block import apply_empty_block, sign_block, transition_unsigned_block
from eth2spec.test.helpers.voluntary_exits import get_unslashed_exited_validators


def get_balance(state, index):
    return state.balances[index]


def next_slot(spec, state):
    """
    Transition to the next slot.
    """
    spec.process_slots(state, state.slot + 1)


def next_slots(spec, state, slots):
    """
    Transition given slots forward.
    """
    if slots > 0:
        spec.process_slots(state, state.slot + slots)


def transition_to(spec, state, slot):
    """
    Transition to ``slot``.
    """
    assert state.slot <= slot
    for _ in range(slot - state.slot):
        next_slot(spec, state)
    assert state.slot == slot


def transition_to_slot_via_block(spec, state, slot):
    """
    Transition to ``slot`` via an empty block transition
    """
    assert state.slot < slot
    apply_empty_block(spec, state, slot)
    assert state.slot == slot


def transition_to_valid_shard_slot(spec, state):
    """
    Transition to slot `compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH) + 1`
    and fork at `compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH)`.
    """
    transition_to(spec, state, spec.compute_epoch_at_slot(spec.config.SHARDING_FORK_EPOCH))
    next_slot(spec, state)


def next_epoch(spec, state):
    """
    Transition to the start slot of the next epoch
    """
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    if slot > state.slot:
        spec.process_slots(state, slot)


def next_epoch_via_block(spec, state, insert_state_root=False):
    """
    Transition to the start slot of the next epoch via a full block transition
    """
    block = apply_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH)
    if insert_state_root:
        block.state_root = state.hash_tree_root()
    return block


def next_epoch_via_signed_block(spec, state):
    block = next_epoch_via_block(spec, state, insert_state_root=True)
    return sign_block(spec, state, block)


def get_state_root(spec, state, slot) -> bytes:
    """
    Return the state root at a recent ``slot``.
    """
    assert slot < state.slot <= slot + spec.SLOTS_PER_HISTORICAL_ROOT
    return state.state_roots[slot % spec.SLOTS_PER_HISTORICAL_ROOT]


def state_transition_and_sign_block(spec, state, block, expect_fail=False):
    """
    State transition via the provided ``block``
    then package the block with the correct state root and signature.
    """
    if expect_fail:
        expect_assertion_error(lambda: transition_unsigned_block(spec, state, block))
    else:
        transition_unsigned_block(spec, state, block)
    block.state_root = state.hash_tree_root()
    return sign_block(spec, state, block)


#
# WARNING: The following functions can only be used post-altair due to the manipulation of participation flags directly
#


def _set_full_participation(spec, state, current=True, previous=True):
    assert is_post_altair(spec)

    full_flags = spec.ParticipationFlags(0)
    for flag_index in range(len(spec.PARTICIPATION_FLAG_WEIGHTS)):
        full_flags = spec.add_flag(full_flags, flag_index)

    for index in range(len(state.validators)):
        if current:
            state.current_epoch_participation[index] = full_flags.copy()
        if previous:
            state.previous_epoch_participation[index] = full_flags.copy()


def set_full_participation(spec, state, rng=None):
    _set_full_participation(spec, state)


def set_full_participation_previous_epoch(spec, state, rng=None):
    _set_full_participation(spec, state, current=False, previous=True)


def _set_empty_participation(spec, state, current=True, previous=True):
    assert is_post_altair(spec)

    for index in range(len(state.validators)):
        if current:
            state.current_epoch_participation[index] = spec.ParticipationFlags(0)
        if previous:
            state.previous_epoch_participation[index] = spec.ParticipationFlags(0)


def set_empty_participation(spec, state, rng=None):
    _set_empty_participation(spec, state)


def ensure_state_has_validators_across_lifecycle(spec, state):
    """
    Scan the validator registry to ensure there is at least 1 validator
    for each of the following lifecycle states:
        1. Pending / deposited
        2. Active
        3. Exited (but not slashed)
        4. Slashed
    """
    has_pending = any(filter(spec.is_eligible_for_activation_queue, state.validators))

    current_epoch = spec.get_current_epoch(state)
    has_active = any(filter(lambda v: spec.is_active_validator(v, current_epoch), state.validators))

    has_exited = any(get_unslashed_exited_validators(spec, state))

    has_slashed = any(filter(lambda v: v.slashed, state.validators))

    return has_pending and has_active and has_exited and has_slashed


def has_active_balance_differential(spec, state):
    """
    Ensure there is a difference between the total balance of
    all _active_ validators and _all_ validators.
    """
    active_balance = spec.get_total_active_balance(state)
    total_balance = spec.get_total_balance(state, set(range(len(state.validators))))
    return active_balance // spec.EFFECTIVE_BALANCE_INCREMENT != total_balance // spec.EFFECTIVE_BALANCE_INCREMENT
