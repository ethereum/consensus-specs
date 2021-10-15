from eth2spec.test.context import (
    always_bls,
    fork_transition_test,
)
from eth2spec.test.helpers.constants import PHASE0, ALTAIR
from eth2spec.test.helpers.fork_transition import (
    OperationType,
    run_transition_with_operation,
)


#
# PROPOSER_SLASHING
#

@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
@always_bls
def test_transition_with_proposer_slashing_right_after_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
@always_bls
def test_transition_with_proposer_slashing_right_before_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
@always_bls
def test_transition_with_attester_slashing_right_after_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
@always_bls
def test_transition_with_attester_slashing_right_before_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_deposit_right_after_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=2)
def test_transition_with_deposit_right_before_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=260)
def test_transition_with_voluntary_exit_right_after_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create a voluntary exit right *after* the transition.
    fork_epoch=260 because mainnet `SHARD_COMMITTEE_PERIOD` is 256 epochs.
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


@fork_transition_test(PHASE0, ALTAIR, fork_epoch=260)
def test_transition_with_voluntary_exit_right_before_fork(state, fork_epoch, spec, post_spec, pre_tag, post_tag):
    """
    Create a voluntary exit right *before* the transition.
    fork_epoch=260 because mainnet `SHARD_COMMITTEE_PERIOD` is 256 epochs.
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
