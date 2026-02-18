from eth_consensus_specs.test.context import (
    always_bls,
    ForkMeta,
    with_fork_metas,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import (
    AFTER_DENEB_PRE_POST_FORKS,
    DENEB,
)
from eth_consensus_specs.test.helpers.fork_transition import (
    do_fork,
    OperationType,
    run_transition_with_operation,
    transition_until_fork,
)
from eth_consensus_specs.test.helpers.state import (
    next_epoch_via_block,
    state_transition_and_sign_block,
    transition_to,
)

#
# BLSToExecutionChange
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in AFTER_DENEB_PRE_POST_FORKS
    ]
)
@always_bls
def test_transition_with_btec_right_after_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a BLS_TO_EXECUTION_CHANGE right *after* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.BLS_TO_EXECUTION_CHANGE,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH,
    )


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in AFTER_DENEB_PRE_POST_FORKS
    ]
)
@always_bls
def test_transition_with_btec_right_before_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a BLS_TO_EXECUTION_CHANGE right *before* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.BLS_TO_EXECUTION_CHANGE,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH - 1,
    )


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in AFTER_DENEB_PRE_POST_FORKS
    ]
)
def test_transition_attestation_from_previous_fork_with_new_range(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    [EIP-7045] test
    """
    # Transition to the epoch prior to the fork epoch
    next_epoch_via_block(spec, state)

    # Generate an attestation for slot 0 of this epoch
    if spec.fork == DENEB:
        # NOTE: attestation format changes from Deneb to Electra
        # so the attestation must be made with the `post_spec`
        target_spec = post_spec
        target_state = post_spec.upgrade_to_electra(state.copy())
        target_state.fork = state.fork
    else:
        target_spec = spec
        target_state = state
    attestation = get_valid_attestation(target_spec, target_state, signed=True)

    yield "pre", state

    # Transition to the fork epoch with a block
    transition_until_fork(spec, state, fork_epoch)
    state, fork_block = do_fork(state, spec, post_spec, fork_epoch)
    current_epoch = spec.get_current_epoch(state)
    assert current_epoch == fork_epoch
    # Transition to second to last slot in `fork_epoch`
    penultimate_slot = post_spec.compute_start_slot_at_epoch(current_epoch + 1) - 2
    transition_to(post_spec, state, penultimate_slot)

    # Ensure the new state is in the increased EIP-7045 slot inclusion range
    assert penultimate_slot - attestation.data.slot > post_spec.SLOTS_PER_EPOCH

    block = build_empty_block_for_next_slot(post_spec, state)
    block.body.attestations.append(attestation)
    signed_block = state_transition_and_sign_block(post_spec, state, block)

    yield "blocks", [post_tag(fork_block), post_tag(signed_block)]
    yield "post", state
