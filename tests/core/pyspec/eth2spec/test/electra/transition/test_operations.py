from eth2spec.test.context import (
    ForkMeta,
    always_bls,
    with_fork_metas,
    with_presets,
)
from eth2spec.test.helpers.constants import (
    AFTER_ELECTRA_PRE_POST_FORKS,
    MINIMAL,
)
from eth2spec.test.helpers.fork_transition import (
    OperationType,
    run_transition_with_operation,
)


#
# DepositRequest
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in AFTER_ELECTRA_PRE_POST_FORKS
    ]
)
@always_bls
def test_transition_with_deposit_request_right_after_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a DEPOSIT_REQUEST right *after* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.DEPOSIT_REQUEST,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH,
    )


#
# WithdrawalRequest
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=66)
        for pre, post in AFTER_ELECTRA_PRE_POST_FORKS
    ]
)
@with_presets([MINIMAL], reason="too slow")
@always_bls
def test_transition_with_full_withdrawal_request_right_after_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a WITHDRAWAL_REQUEST right *after* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.WITHDRAWAL_REQUEST,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH,
    )


#
# ConsolidationRequest
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in AFTER_ELECTRA_PRE_POST_FORKS
    ]
)
@always_bls
def test_transition_with_consolidation_request_right_after_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a CONSOLIDATION_REQUEST right *after* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.CONSOLIDATION_REQUEST,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH,
    )
