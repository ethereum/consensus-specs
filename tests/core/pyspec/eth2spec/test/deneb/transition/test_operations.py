from eth2spec.test.context import (
    ForkMeta,
    always_bls,
    with_fork_metas,
)
from eth2spec.test.helpers.constants import (
    AFTER_DENEB_PRE_POST_FORKS,
)
from eth2spec.test.helpers.fork_transition import (
    OperationType,
    run_transition_with_operation,
)


#
# BLSToExecutionChange
#

@with_fork_metas([ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
                  for pre, post in AFTER_DENEB_PRE_POST_FORKS])
@always_bls
def test_transition_with_btec_right_after_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
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


@with_fork_metas([ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
                  for pre, post in AFTER_DENEB_PRE_POST_FORKS])
@always_bls
def test_transition_with_btec_right_before_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
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
