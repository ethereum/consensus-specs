from enum import auto, Enum

from eth2spec.test.helpers.attestations import (
    next_slots_with_attestations,
    state_transition_with_full_block,
)
from eth2spec.test.helpers.attester_slashings import (
    get_valid_attester_slashing_by_indices,
)
from eth2spec.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
    sign_block,
)
from eth2spec.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth2spec.test.helpers.consolidations import (
    prepare_switch_to_compounding_request,
)
from eth2spec.test.helpers.constants import (
    DENEB,
    PHASE0,
    POST_FORK_OF,
    PREVIOUS_FORK_OF,
)
from eth2spec.test.helpers.deposits import (
    prepare_deposit_request,
    prepare_state_and_deposit,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    compute_el_block_hash,
    compute_el_block_hash_for_block,
)
from eth2spec.test.helpers.forks import (
    get_next_fork_transition,
    is_post_bellatrix,
    is_post_electra,
    is_post_gloas,
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
from eth2spec.test.helpers.withdrawals import (
    prepare_withdrawal_request,
)


class OperationType(Enum):
    PROPOSER_SLASHING = auto()
    ATTESTER_SLASHING = auto()
    DEPOSIT = auto()
    VOLUNTARY_EXIT = auto()
    BLS_TO_EXECUTION_CHANGE = auto()
    DEPOSIT_REQUEST = auto()
    WITHDRAWAL_REQUEST = auto()
    CONSOLIDATION_REQUEST = auto()


# TODO(jtraglia): Pretty sure this doesn't play well with Gloas. Needs some work.
def _set_operations_by_dict(spec, block, operation_dict, state):
    for key, value in operation_dict.items():
        # to handle e.g. `execution_requests.deposits` and `deposits`
        obj = block.body
        for attr in key.split(".")[:-1]:
            obj = getattr(obj, attr)
        setattr(obj, key.split(".")[-1], value)
    if is_post_gloas(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.block_hash = compute_el_block_hash(
            spec, payload, state
        )
    elif is_post_bellatrix(spec):
        block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)


def _state_transition_and_sign_block_at_slot(spec, state, sync_aggregate=None, operation_dict=None):
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
    if sync_aggregate is not None:
        block.body.sync_aggregate = sync_aggregate

    if operation_dict:
        _set_operations_by_dict(spec, block, operation_dict, state)

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


def state_transition_across_slots_with_ignoring_proposers(
    spec, state, to_slot, ignoring_proposers, only_last_block=False
):
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


def get_upgrade_fn(spec, fork):
    # pylint: disable=unused-argument
    # NOTE: `spec` is used for the `eval` call
    assert fork in POST_FORK_OF.values()
    try:
        # TODO: make all upgrade_to_* function names consistent?
        fn = eval(f"spec.upgrade_to_{fork}")
        return fn
    except Exception:
        raise ValueError(f"Unknown fork: {fork}")


def do_fork(
    state, spec, post_spec, fork_epoch, with_block=True, sync_aggregate=None, operation_dict=None
):
    spec.process_slots(state, state.slot + 1)

    assert state.slot % spec.SLOTS_PER_EPOCH == 0
    assert spec.get_current_epoch(state) == fork_epoch

    state = get_upgrade_fn(post_spec, post_spec.fork)(state)

    assert state.fork.epoch == fork_epoch

    previous_fork = PREVIOUS_FORK_OF[post_spec.fork]
    if previous_fork == PHASE0:
        previous_version = spec.config.GENESIS_FORK_VERSION
    else:
        previous_version = getattr(post_spec.config, f"{previous_fork.upper()}_FORK_VERSION")
    current_version = getattr(post_spec.config, f"{post_spec.fork.upper()}_FORK_VERSION")

    assert state.fork.previous_version == previous_version
    assert state.fork.current_version == current_version

    if with_block:
        return state, _state_transition_and_sign_block_at_slot(
            post_spec,
            state,
            sync_aggregate=sync_aggregate,
            operation_dict=operation_dict,
        )
    else:
        return state, None


def do_fork_generate(
    state, spec, post_spec, fork_epoch, with_block=True, sync_aggregate=None, operation_dict=None
):
    spec.process_slots(state, state.slot + 1)

    assert state.slot % spec.SLOTS_PER_EPOCH == 0
    assert spec.get_current_epoch(state) == fork_epoch

    yield "pre", state

    state = get_upgrade_fn(post_spec, post_spec.fork)(state)

    yield "post", state

    assert state.fork.epoch == fork_epoch

    previous_fork = PREVIOUS_FORK_OF[post_spec.fork]
    if previous_fork == PHASE0:
        previous_version = spec.config.GENESIS_FORK_VERSION
    else:
        previous_version = getattr(post_spec.config, f"{previous_fork.upper()}_FORK_VERSION")
    current_version = getattr(post_spec.config, f"{post_spec.fork.upper()}_FORK_VERSION")

    assert state.fork.previous_version == previous_version
    assert state.fork.current_version == current_version

    if with_block:
        return state, _state_transition_and_sign_block_at_slot(
            post_spec,
            state,
            sync_aggregate=sync_aggregate,
            operation_dict=operation_dict,
        )
    else:
        return state, None


def transition_until_fork(spec, state, fork_epoch):
    to_slot = fork_epoch * spec.SLOTS_PER_EPOCH - 1
    transition_to(spec, state, to_slot)


def _transition_until_fork_minus_one(spec, state, fork_epoch):
    to_slot = fork_epoch * spec.SLOTS_PER_EPOCH - 2
    transition_to(spec, state, to_slot)


def transition_across_forks(
    spec, state, to_slot, phases=None, with_block=False, sync_aggregate=None
):
    assert to_slot > state.slot
    state = state.copy()
    block = None
    to_epoch = spec.compute_epoch_at_slot(to_slot)
    while state.slot < to_slot:
        assert block is None
        epoch = spec.compute_epoch_at_slot(state.slot)
        post_spec, fork_epoch = get_next_fork_transition(spec, epoch, phases)
        if fork_epoch is None or to_epoch < fork_epoch:
            if with_block and (to_slot == state.slot + 1):
                transition_to(spec, state, to_slot - 1)
                block = state_transition_with_full_block(
                    spec, state, True, True, sync_aggregate=sync_aggregate
                )
            else:
                transition_to(spec, state, to_slot)
        else:
            transition_until_fork(spec, state, fork_epoch)
            state, block = do_fork(
                state,
                spec,
                post_spec,
                fork_epoch,
                with_block=with_block and (to_slot == state.slot + 1),
                sync_aggregate=sync_aggregate,
            )
            spec = post_spec
    return spec, state, block


def transition_to_next_epoch_and_append_blocks(
    spec, state, post_tag, blocks, only_last_block=False, ignoring_proposers=None
):
    to_slot = spec.SLOTS_PER_EPOCH + state.slot

    if only_last_block:
        block_filter = only_at(to_slot)
    else:
        block_filter = _all_blocks

    if ignoring_proposers is None:
        result_blocks = state_transition_across_slots(
            spec, state, to_slot, block_filter=block_filter
        )
    else:
        result_blocks = state_transition_across_slots_with_ignoring_proposers(
            spec,
            state,
            to_slot,
            ignoring_proposers,
            only_last_block=only_last_block,
        )

    blocks.extend([post_tag(block) for block in result_blocks])


def run_transition_with_operation(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag, operation_type, operation_at_slot
):
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

    is_slashing_operation = operation_type in (
        OperationType.PROPOSER_SLASHING,
        OperationType.ATTESTER_SLASHING,
    )
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
                spec, state, slashed_index=selected_validator_index, signed_1=True, signed_2=True
            )
            operation_dict = {"proposer_slashings": [proposer_slashing]}
        else:
            # operation_type == OperationType.ATTESTER_SLASHING:
            if is_at_fork and spec.fork == DENEB:
                # NOTE: attestation format changes between Deneb and Electra
                # so attester slashing must be made with the `post_spec`
                target_spec = post_spec
                target_state = post_spec.upgrade_to_electra(state.copy())
                target_state.fork = state.fork
            else:
                target_spec = spec
                target_state = state

            attester_slashing = get_valid_attester_slashing_by_indices(
                target_spec,
                target_state,
                [selected_validator_index],
                signed_1=True,
                signed_2=True,
            )
            operation_dict = {"attester_slashings": [attester_slashing]}
    elif operation_type == OperationType.DEPOSIT:
        # create a new deposit
        selected_validator_index = len(state.validators)
        amount = spec.MAX_EFFECTIVE_BALANCE
        deposit = prepare_state_and_deposit(
            spec, state, selected_validator_index, amount, signed=True
        )
        operation_dict = {"deposits": [deposit]}
    elif operation_type == OperationType.VOLUNTARY_EXIT:
        selected_validator_index = 0
        signed_exits = prepare_signed_exits(spec, state, [selected_validator_index])
        operation_dict = {"voluntary_exits": signed_exits}
    elif operation_type == OperationType.BLS_TO_EXECUTION_CHANGE:
        selected_validator_index = 0
        bls_to_execution_changes = [
            get_signed_address_change(spec, state, selected_validator_index)
        ]
        operation_dict = {"bls_to_execution_changes": bls_to_execution_changes}
    elif operation_type == OperationType.DEPOSIT_REQUEST:
        # create a new deposit request
        selected_validator_index = len(state.validators)
        amount = post_spec.MIN_ACTIVATION_BALANCE
        deposit_request = prepare_deposit_request(
            post_spec, selected_validator_index, amount, signed=True
        )
        operation_dict = {"execution_requests.deposits": [deposit_request]}
    elif operation_type == OperationType.WITHDRAWAL_REQUEST:
        selected_validator_index = 0
        withdrawal_request = prepare_withdrawal_request(
            post_spec, state, selected_validator_index, amount=post_spec.FULL_EXIT_REQUEST_AMOUNT
        )
        operation_dict = {"execution_requests.withdrawals": [withdrawal_request]}
    elif operation_type == OperationType.CONSOLIDATION_REQUEST:
        selected_validator_index = 0
        consolidation_request = prepare_switch_to_compounding_request(
            post_spec, state, selected_validator_index
        )
        operation_dict = {"execution_requests.consolidations": [consolidation_request]}

    def _check_state():
        if operation_type == OperationType.PROPOSER_SLASHING:
            slashed_proposer = state.validators[
                proposer_slashing.signed_header_1.message.proposer_index
            ]
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
                state.validators[selected_validator_index], post_spec.get_current_epoch(state)
            )
        elif operation_type == OperationType.VOLUNTARY_EXIT:
            validator = state.validators[selected_validator_index]
            assert validator.exit_epoch < post_spec.FAR_FUTURE_EPOCH
        elif operation_type == OperationType.BLS_TO_EXECUTION_CHANGE:
            validator = state.validators[selected_validator_index]
            assert validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        elif operation_type == OperationType.DEPOSIT_REQUEST:
            assert state.pending_deposits == [
                post_spec.PendingDeposit(
                    pubkey=deposit_request.pubkey,
                    withdrawal_credentials=deposit_request.withdrawal_credentials,
                    amount=deposit_request.amount,
                    signature=deposit_request.signature,
                    slot=state.slot,
                )
            ]
        elif operation_type == OperationType.WITHDRAWAL_REQUEST:
            validator = state.validators[selected_validator_index]
            assert validator.exit_epoch < post_spec.FAR_FUTURE_EPOCH
        elif operation_type == OperationType.CONSOLIDATION_REQUEST:
            validator = state.validators[selected_validator_index]
            assert validator.withdrawal_credentials[:1] == post_spec.COMPOUNDING_WITHDRAWAL_PREFIX

    yield "pre", state

    blocks = []

    if is_right_before_fork:
        # add a block with operation.
        block = build_empty_block_for_next_slot(spec, state)
        _set_operations_by_dict(spec, block, operation_dict, state)
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
        state = _transition_until_active(
            post_spec, state, post_tag, blocks, selected_validator_index
        )
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
    epochs_required_to_activate = 2
    if is_post_electra(post_spec):
        # NOTE: an extra epoch is required given the way balance updates
        # changed with electra
        epochs_required_to_activate = 3
    # finalize activation_eligibility_epoch
    _, blocks_in_epoch, state = next_slots_with_attestations(
        post_spec,
        state,
        post_spec.SLOTS_PER_EPOCH * epochs_required_to_activate,
        fill_cur_epoch=True,
        fill_prev_epoch=True,
    )
    blocks.extend([post_tag(block) for block in blocks_in_epoch])
    assert (
        state.finalized_checkpoint.epoch
        >= state.validators[validator_index].activation_eligibility_epoch
    )

    # continue regular state transition with new spec into next epoch
    transition_to_next_epoch_and_append_blocks(
        post_spec, state, post_tag, blocks, only_last_block=True
    )

    assert state.validators[validator_index].activation_epoch < post_spec.FAR_FUTURE_EPOCH

    to_slot = state.validators[validator_index].activation_epoch * post_spec.SLOTS_PER_EPOCH
    blocks.extend(
        [
            post_tag(block)
            for block in state_transition_across_slots(
                post_spec, state, to_slot, block_filter=only_at(to_slot)
            )
        ]
    )
    assert post_spec.is_active_validator(
        state.validators[validator_index], post_spec.get_current_epoch(state)
    )

    return state
