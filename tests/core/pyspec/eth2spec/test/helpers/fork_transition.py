from enum import Enum, auto

from eth2spec.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth2spec.test.helpers.attestations import next_slots_with_attestations
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    build_empty_block,
    sign_block,
)
from eth2spec.test.helpers.constants import (
    ALTAIR,
    BELLATRIX,
)
from eth2spec.test.helpers.deposits import (
    prepare_state_and_deposit,
)
from eth2spec.test.helpers.proposer_slashings import (
    get_valid_proposer_slashing,
)
from eth2spec.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
    transition_to,
)
from eth2spec.test.helpers.voluntary_exits import (
    prepare_signed_exits,
)


class OperationType(Enum):
    PROPOSER_SLASHING = auto()
    ATTESTER_SLASHING = auto()
    DEPOSIT = auto()
    VOLUNTARY_EXIT = auto()


def _set_operations_by_dict(block, operation_dict):
    for key, value in operation_dict.items():
        setattr(block.body, key, value)


def _state_transition_and_sign_block_at_slot(spec,
                                             state,
                                             operation_dict=None):
    """
    Cribbed from ``transition_unsigned_block`` helper
    where the early parts of the state transition have already
    been applied to ``state``.

    Used to produce a block during an irregular state transition.

    The optional `operation_dict` is a dict of {'<BeaconBlockBody field>': <value>}.
    This is used for assigning the block operations.
    p.s. we can't just pass `body` and assign it because randao_reveal and eth1_data was set in `build_empty_block`
    Thus use dict to pass operations.
    """
    block = build_empty_block(spec, state)

    if operation_dict:
        _set_operations_by_dict(block, operation_dict)

    assert state.latest_block_header.slot < block.slot
    assert state.slot == block.slot
    spec.process_block(state, block)
    block.state_root = state.hash_tree_root()
    return sign_block(spec, state, block)


def _all_blocks(_):
    return True


def skip_slots(*slots):
    """
    Skip making a block if its slot is
    passed as an argument to this filter
    """
    def f(state_at_prior_slot):
        return state_at_prior_slot.slot + 1 not in slots
    return f


def no_blocks(_):
    return False


def only_at(slot):
    """
    Only produce a block if its slot is ``slot``.
    """
    def f(state_at_prior_slot):
        return state_at_prior_slot.slot + 1 == slot
    return f


def state_transition_across_slots(spec, state, to_slot, block_filter=_all_blocks):
    assert state.slot < to_slot
    while state.slot < to_slot:
        should_make_block = block_filter(state)
        if should_make_block:
            block = build_empty_block_for_next_slot(spec, state)
            signed_block = state_transition_and_sign_block(spec, state, block)
            yield signed_block
        else:
            next_slot(spec, state)


def state_transition_across_slots_with_ignoring_proposers(spec,
                                                          state,
                                                          to_slot,
                                                          ignoring_proposers,
                                                          only_last_block=False):
    """
    The slashed validators can't be proposers. Here we ignore the given `ignoring_proposers`
    and ensure that the result state was computed with a block with slot >= to_slot.
    """
    assert state.slot < to_slot

    found_valid = False
    while state.slot < to_slot or not found_valid:
        if state.slot + 1 < to_slot and only_last_block:
            next_slot(spec, state)
            continue

        future_state = state.copy()
        next_slot(spec, future_state)
        proposer_index = spec.get_beacon_proposer_index(future_state)
        if proposer_index not in ignoring_proposers:
            block = build_empty_block_for_next_slot(spec, state)
            signed_block = state_transition_and_sign_block(spec, state, block)
            yield signed_block
            if state.slot >= to_slot:
                found_valid = True
        else:
            next_slot(spec, state)


def do_fork(state, spec, post_spec, fork_epoch, with_block=True, operation_dict=None):
    spec.process_slots(state, state.slot + 1)

    assert state.slot % spec.SLOTS_PER_EPOCH == 0
    assert spec.get_current_epoch(state) == fork_epoch

    if post_spec.fork == ALTAIR:
        state = post_spec.upgrade_to_altair(state)
    elif post_spec.fork == BELLATRIX:
        state = post_spec.upgrade_to_bellatrix(state)

    assert state.fork.epoch == fork_epoch

    if post_spec.fork == ALTAIR:
        assert state.fork.previous_version == post_spec.config.GENESIS_FORK_VERSION
        assert state.fork.current_version == post_spec.config.ALTAIR_FORK_VERSION
    elif post_spec.fork == BELLATRIX:
        assert state.fork.previous_version == post_spec.config.ALTAIR_FORK_VERSION
        assert state.fork.current_version == post_spec.config.BELLATRIX_FORK_VERSION

    if with_block:
        return state, _state_transition_and_sign_block_at_slot(post_spec, state, operation_dict=operation_dict)
    else:
        return state, None


def transition_until_fork(spec, state, fork_epoch):
    to_slot = fork_epoch * spec.SLOTS_PER_EPOCH - 1
    transition_to(spec, state, to_slot)


def _transition_until_fork_minus_one(spec, state, fork_epoch):
    to_slot = fork_epoch * spec.SLOTS_PER_EPOCH - 2
    transition_to(spec, state, to_slot)


def transition_to_next_epoch_and_append_blocks(spec,
                                               state,
                                               post_tag,
                                               blocks,
                                               only_last_block=False,
                                               ignoring_proposers=None):
    to_slot = spec.SLOTS_PER_EPOCH + state.slot

    if only_last_block:
        block_filter = only_at(to_slot)
    else:
        block_filter = _all_blocks

    if ignoring_proposers is None:
        result_blocks = state_transition_across_slots(spec, state, to_slot, block_filter=block_filter)
    else:
        result_blocks = state_transition_across_slots_with_ignoring_proposers(
            spec,
            state,
            to_slot,
            ignoring_proposers,
            only_last_block=only_last_block,
        )

    blocks.extend([
        post_tag(block) for block in
        result_blocks
    ])


def run_transition_with_operation(state,
                                  fork_epoch,
                                  spec,
                                  post_spec,
                                  pre_tag,
                                  post_tag,
                                  operation_type,
                                  operation_at_slot):
    """
    Generate `operation_type` operation with the spec before fork.
    The operation would be included into the block at `operation_at_slot`.
    """
    is_at_fork = operation_at_slot == fork_epoch * spec.SLOTS_PER_EPOCH
    is_right_before_fork = operation_at_slot == fork_epoch * spec.SLOTS_PER_EPOCH - 1
    assert is_at_fork or is_right_before_fork

    if is_at_fork:
        transition_until_fork(spec, state, fork_epoch)
    elif is_right_before_fork:
        _transition_until_fork_minus_one(spec, state, fork_epoch)

    is_slashing_operation = operation_type in (OperationType.PROPOSER_SLASHING, OperationType.ATTESTER_SLASHING)
    # prepare operation
    selected_validator_index = None
    if is_slashing_operation:
        # avoid slashing the next proposer
        future_state = state.copy()
        next_slot(spec, future_state)
        proposer_index = spec.get_beacon_proposer_index(future_state)
        selected_validator_index = (proposer_index + 1) % len(state.validators)
        if operation_type == OperationType.PROPOSER_SLASHING:
            proposer_slashing = get_valid_proposer_slashing(
                spec, state, slashed_index=selected_validator_index, signed_1=True, signed_2=True)
            operation_dict = {'proposer_slashings': [proposer_slashing]}
        else:
            # operation_type == OperationType.ATTESTER_SLASHING:
            attester_slashing = get_valid_attester_slashing_by_indices(
                spec, state,
                [selected_validator_index],
                signed_1=True, signed_2=True,
            )
            operation_dict = {'attester_slashings': [attester_slashing]}
    elif operation_type == OperationType.DEPOSIT:
        # create a new deposit
        selected_validator_index = len(state.validators)
        amount = spec.MAX_EFFECTIVE_BALANCE
        deposit = prepare_state_and_deposit(spec, state, selected_validator_index, amount, signed=True)
        operation_dict = {'deposits': [deposit]}
    elif operation_type == OperationType.VOLUNTARY_EXIT:
        selected_validator_index = 0
        signed_exits = prepare_signed_exits(spec, state, [selected_validator_index])
        operation_dict = {'voluntary_exits': signed_exits}

    def _check_state():
        if operation_type == OperationType.PROPOSER_SLASHING:
            slashed_proposer = state.validators[proposer_slashing.signed_header_1.message.proposer_index]
            assert slashed_proposer.slashed
        elif operation_type == OperationType.ATTESTER_SLASHING:
            indices = set(attester_slashing.attestation_1.attesting_indices).intersection(
                attester_slashing.attestation_2.attesting_indices
            )
            assert selected_validator_index in indices
            assert len(indices) > 0
            for validator_index in indices:
                assert state.validators[validator_index].slashed
        elif operation_type == OperationType.DEPOSIT:
            assert not post_spec.is_active_validator(
                state.validators[selected_validator_index],
                post_spec.get_current_epoch(state)
            )
        elif operation_type == OperationType.VOLUNTARY_EXIT:
            validator = state.validators[selected_validator_index]
            assert validator.exit_epoch < post_spec.FAR_FUTURE_EPOCH

    yield "pre", state

    blocks = []

    if is_right_before_fork:
        # add a block with operation.
        block = build_empty_block_for_next_slot(spec, state)
        _set_operations_by_dict(block, operation_dict)
        signed_block = state_transition_and_sign_block(spec, state, block)
        blocks.append(pre_tag(signed_block))

        _check_state()

    # irregular state transition to handle fork:
    _operation_at_slot = operation_dict if is_at_fork else None
    state, block = do_fork(state, spec, post_spec, fork_epoch, operation_dict=_operation_at_slot)
    blocks.append(post_tag(block))

    if is_at_fork:
        _check_state()

    # after the fork
    if operation_type == OperationType.DEPOSIT:
        state = _transition_until_active(post_spec, state, post_tag, blocks, selected_validator_index)
    else:
        # avoid using the slashed validators as block proposers
        ignoring_proposers = [selected_validator_index] if is_slashing_operation else None

        # continue regular state transition with new spec into next epoch
        transition_to_next_epoch_and_append_blocks(
            post_spec,
            state,
            post_tag,
            blocks,
            only_last_block=True,
            ignoring_proposers=ignoring_proposers,
        )

    yield "blocks", blocks
    yield "post", state


def _transition_until_active(post_spec, state, post_tag, blocks, validator_index):
    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(post_spec, state, post_tag, blocks)
    # finalize activation_eligibility_epoch
    _, blocks_in_epoch, state = next_slots_with_attestations(
        post_spec,
        state,
        post_spec.SLOTS_PER_EPOCH * 2,
        fill_cur_epoch=True,
        fill_prev_epoch=True,
    )
    blocks.extend([post_tag(block) for block in blocks_in_epoch])
    assert state.finalized_checkpoint.epoch >= state.validators[validator_index].activation_eligibility_epoch

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(post_spec, state, post_tag, blocks, only_last_block=True)

    assert state.validators[validator_index].activation_epoch < post_spec.FAR_FUTURE_EPOCH

    to_slot = state.validators[validator_index].activation_epoch * post_spec.SLOTS_PER_EPOCH
    blocks.extend([
        post_tag(block) for block in
        state_transition_across_slots(post_spec, state, to_slot, block_filter=only_at(to_slot))
    ])
    assert post_spec.is_active_validator(state.validators[validator_index], post_spec.get_current_epoch(state))

    return state
