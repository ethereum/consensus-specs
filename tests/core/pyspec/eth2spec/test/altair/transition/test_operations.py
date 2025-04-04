from eth2spec.test.context import (
    ForkMeta,
    always_bls,
    with_fork_metas,
    with_presets,
)
from eth2spec.test.helpers.constants import (
    ALL_PRE_POST_FORKS,
    MINIMAL,
)
from eth2spec.test.helpers.fork_transition import (
    OperationType,
    run_transition_with_operation,
)


#
# PROPOSER_SLASHING
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
@always_bls
def test_transition_with_proposer_slashing_right_after_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create an attester slashing right *after* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.PROPOSER_SLASHING,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH,
    )


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
@always_bls
def test_transition_with_proposer_slashing_right_before_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create an attester slashing right *before* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.PROPOSER_SLASHING,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH - 1,
    )


#
# ATTESTER_SLASHING
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
@always_bls
def test_transition_with_attester_slashing_right_after_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create an attester slashing right *after* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.ATTESTER_SLASHING,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH,
    )


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
@always_bls
def test_transition_with_attester_slashing_right_before_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create an attester slashing right *after* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.ATTESTER_SLASHING,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH - 1,
    )


#
# DEPOSIT
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
def test_transition_with_deposit_right_after_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a deposit right *after* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.DEPOSIT,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH,
    )


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=2)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
def test_transition_with_deposit_right_before_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a deposit right *before* the transition
    """
    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.DEPOSIT,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH - 1,
    )


#
# VOLUNTARY_EXIT
#


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=66)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
@with_presets([MINIMAL], reason="too slow")
def test_transition_with_voluntary_exit_right_after_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a voluntary exit right *after* the transition.
    fork_epoch=66 because minimal preset `SHARD_COMMITTEE_PERIOD` is 64 epochs.
    """
    # Fast forward to the future epoch so that validator can do voluntary exit
    state.slot = spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.VOLUNTARY_EXIT,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH,
    )


@with_fork_metas(
    [
        ForkMeta(pre_fork_name=pre, post_fork_name=post, fork_epoch=66)
        for pre, post in ALL_PRE_POST_FORKS
    ]
)
@with_presets([MINIMAL], reason="too slow")
def test_transition_with_voluntary_exit_right_before_fork(
    state, fork_epoch, spec, post_spec, pre_tag, post_tag
):
    """
    Create a voluntary exit right *before* the transition.
    fork_epoch=66 because minimal preset `SHARD_COMMITTEE_PERIOD` is 64 epochs.
    """
    # Fast forward to the future epoch so that validator can do voluntary exit
    state.slot = spec.config.SHARD_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    yield from run_transition_with_operation(
        state,
        fork_epoch,
        spec,
        post_spec,
        pre_tag,
        post_tag,
        operation_type=OperationType.VOLUNTARY_EXIT,
        operation_at_slot=fork_epoch * spec.SLOTS_PER_EPOCH - 1,
    )
