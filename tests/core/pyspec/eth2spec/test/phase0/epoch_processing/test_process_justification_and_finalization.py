from random import Random
from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with,
)
from eth2spec.test.helpers.forks import is_post_altair
from eth2spec.test.helpers.state import transition_to, next_epoch_via_block, next_slot
from eth2spec.test.helpers.voluntary_exits import get_unslashed_exited_validators


def run_process_just_and_fin(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_justification_and_finalization")


def add_mock_attestations(
    spec, state, epoch, source, target, sufficient_support=False, messed_up_target=False
):
    # we must be at the end of the epoch
    assert (state.slot + 1) % spec.SLOTS_PER_EPOCH == 0

    previous_epoch = spec.get_previous_epoch(state)
    current_epoch = spec.get_current_epoch(state)

    if not is_post_altair(spec):
        if current_epoch == epoch:
            attestations = state.current_epoch_attestations
        elif previous_epoch == epoch:
            attestations = state.previous_epoch_attestations
        else:
            raise Exception(
                f"cannot include attestations in epoch ${epoch} from epoch ${current_epoch}"
            )
    else:
        if current_epoch == epoch:
            epoch_participation = state.current_epoch_participation
        elif previous_epoch == epoch:
            epoch_participation = state.previous_epoch_participation
        else:
            raise Exception(
                f"cannot include attestations in epoch ${epoch} from epoch ${current_epoch}"
            )

    total_balance = spec.get_total_active_balance(state)
    remaining_balance = int(total_balance * 2 // 3)  # can become negative

    start_slot = spec.compute_start_slot_at_epoch(epoch)
    committees_per_slot = spec.get_committee_count_per_slot(state, epoch)
    for slot in range(start_slot, start_slot + spec.SLOTS_PER_EPOCH):
        for index in range(committees_per_slot):
            # Check if we already have had sufficient balance. (and undone if we don't want it).
            # If so, do not create more attestations. (we do not have empty pending attestations normally anyway)
            if remaining_balance < 0:
                return

            committee = spec.get_beacon_committee(state, slot, index)
            # Create a bitfield filled with the given count per attestation,
            #  exactly on the right-most part of the committee field.

            aggregation_bits = [0] * len(committee)
            for v in range(len(committee) * 2 // 3 + 1):
                if remaining_balance > 0:
                    remaining_balance -= int(state.validators[v].effective_balance)
                    aggregation_bits[v] = 1
                else:
                    break

            # remove 1/5th of attesters so that support is insufficient
            if not sufficient_support:
                for i in range(max(len(committee) // 5, 1)):
                    aggregation_bits[i] = 0

            # Update state
            if not is_post_altair(spec):
                attestations.append(
                    spec.PendingAttestation(
                        aggregation_bits=aggregation_bits,
                        data=spec.AttestationData(
                            slot=slot,
                            beacon_block_root=b"\xff" * 32,  # irrelevant to testing
                            source=source,
                            target=target,
                            index=index,
                        ),
                        inclusion_delay=1,
                    )
                )
                if messed_up_target:
                    attestations[len(attestations) - 1].data.target.root = b"\x99" * 32
            else:
                for i, index in enumerate(committee):
                    if aggregation_bits[i]:
                        epoch_participation[index] |= spec.ParticipationFlags(
                            2**spec.TIMELY_HEAD_FLAG_INDEX
                        )
                        epoch_participation[index] |= spec.ParticipationFlags(
                            2**spec.TIMELY_SOURCE_FLAG_INDEX
                        )
                        if not messed_up_target:
                            epoch_participation[index] |= spec.ParticipationFlags(
                                2**spec.TIMELY_TARGET_FLAG_INDEX
                            )


def get_checkpoints(spec, epoch):
    c1 = None if epoch < 1 else spec.Checkpoint(epoch=epoch - 1, root=b"\xaa" * 32)
    c2 = None if epoch < 2 else spec.Checkpoint(epoch=epoch - 2, root=b"\xbb" * 32)
    c3 = None if epoch < 3 else spec.Checkpoint(epoch=epoch - 3, root=b"\xcc" * 32)
    c4 = None if epoch < 4 else spec.Checkpoint(epoch=epoch - 4, root=b"\xdd" * 32)
    c5 = None if epoch < 5 else spec.Checkpoint(epoch=epoch - 5, root=b"\xee" * 32)
    return c1, c2, c3, c4, c5


def put_checkpoints_in_block_roots(spec, state, checkpoints):
    for c in checkpoints:
        state.block_roots[
            spec.compute_start_slot_at_epoch(c.epoch) % spec.SLOTS_PER_HISTORICAL_ROOT
        ] = c.root


def finalize_on_234(spec, state, epoch, sufficient_support):
    assert epoch > 4
    transition_to(spec, state, spec.SLOTS_PER_EPOCH * epoch - 1)  # skip ahead to just before epoch

    # 43210 -- epochs ago
    # 3210x -- justification bitfield indices
    # 11*0. -- justification bitfield contents, . = this epoch, * is being justified now
    # checkpoints for the epochs ago:
    c1, c2, c3, c4, _ = get_checkpoints(spec, epoch)
    put_checkpoints_in_block_roots(spec, state, [c1, c2, c3, c4])

    old_finalized = state.finalized_checkpoint
    state.previous_justified_checkpoint = c4
    state.current_justified_checkpoint = c3
    state.justification_bits = spec.Bitvector[spec.JUSTIFICATION_BITS_LENGTH]()
    state.justification_bits[1:3] = [
        1,
        1,
    ]  # mock 3rd and 4th latest epochs as justified (indices are pre-shift)
    # mock the 2nd latest epoch as justifiable, with 4th as source
    add_mock_attestations(
        spec, state, epoch=epoch - 2, source=c4, target=c2, sufficient_support=sufficient_support
    )

    # process!
    yield from run_process_just_and_fin(spec, state)

    assert state.previous_justified_checkpoint == c3  # changed to old current
    if sufficient_support:
        assert state.current_justified_checkpoint == c2  # changed to 2nd latest
        assert state.finalized_checkpoint == c4  # finalized old previous justified epoch
    else:
        assert state.current_justified_checkpoint == c3  # still old current
        assert state.finalized_checkpoint == old_finalized  # no new finalized


def finalize_on_23(spec, state, epoch, sufficient_support):
    assert epoch > 3
    transition_to(spec, state, spec.SLOTS_PER_EPOCH * epoch - 1)  # skip ahead to just before epoch

    # 43210 -- epochs ago
    # 210xx  -- justification bitfield indices (pre shift)
    # 3210x -- justification bitfield indices (post shift)
    # 01*0. -- justification bitfield contents, . = this epoch, * is being justified now
    # checkpoints for the epochs ago:
    c1, c2, c3, _, _ = get_checkpoints(spec, epoch)
    put_checkpoints_in_block_roots(spec, state, [c1, c2, c3])

    old_finalized = state.finalized_checkpoint
    state.previous_justified_checkpoint = c3
    state.current_justified_checkpoint = c3
    state.justification_bits = spec.Bitvector[spec.JUSTIFICATION_BITS_LENGTH]()
    state.justification_bits[1] = 1  # mock 3rd latest epoch as justified (index is pre-shift)
    # mock the 2nd latest epoch as justifiable, with 3rd as source
    add_mock_attestations(
        spec, state, epoch=epoch - 2, source=c3, target=c2, sufficient_support=sufficient_support
    )

    # process!
    yield from run_process_just_and_fin(spec, state)

    assert state.previous_justified_checkpoint == c3  # changed to old current
    if sufficient_support:
        assert state.current_justified_checkpoint == c2  # changed to 2nd latest
        assert state.finalized_checkpoint == c3  # finalized old previous justified epoch
    else:
        assert state.current_justified_checkpoint == c3  # still old current
        assert state.finalized_checkpoint == old_finalized  # no new finalized


def finalize_on_123(spec, state, epoch, sufficient_support):
    assert epoch > 5
    state.slot = (spec.SLOTS_PER_EPOCH * epoch) - 1  # skip ahead to just before epoch

    # 43210 -- epochs ago
    # 210xx  -- justification bitfield indices (pre shift)
    # 3210x -- justification bitfield indices (post shift)
    # 011*. -- justification bitfield contents, . = this epoch, * is being justified now
    # checkpoints for the epochs ago:
    c1, c2, c3, c4, c5 = get_checkpoints(spec, epoch)
    put_checkpoints_in_block_roots(spec, state, [c1, c2, c3, c4, c5])

    old_finalized = state.finalized_checkpoint
    state.previous_justified_checkpoint = c5
    state.current_justified_checkpoint = c3
    state.justification_bits = spec.Bitvector[spec.JUSTIFICATION_BITS_LENGTH]()
    state.justification_bits[1] = 1  # mock 3rd latest epochs as justified (index is pre-shift)
    # mock the 2nd latest epoch as justifiable, with 5th as source
    add_mock_attestations(
        spec, state, epoch=epoch - 2, source=c5, target=c2, sufficient_support=sufficient_support
    )
    # mock the 1st latest epoch as justifiable, with 3rd as source
    add_mock_attestations(
        spec, state, epoch=epoch - 1, source=c3, target=c1, sufficient_support=sufficient_support
    )

    # process!
    yield from run_process_just_and_fin(spec, state)

    assert state.previous_justified_checkpoint == c3  # changed to old current
    if sufficient_support:
        assert state.current_justified_checkpoint == c1  # changed to 1st latest
        assert state.finalized_checkpoint == c3  # finalized old current
    else:
        assert state.current_justified_checkpoint == c3  # still old current
        assert state.finalized_checkpoint == old_finalized  # no new finalized


def finalize_on_12(spec, state, epoch, sufficient_support, messed_up_target):
    assert epoch > 2
    transition_to(spec, state, spec.SLOTS_PER_EPOCH * epoch - 1)  # skip ahead to just before epoch

    # 43210 -- epochs ago
    # 210xx  -- justification bitfield indices (pre shift)
    # 3210x -- justification bitfield indices (post shift)
    # 001*. -- justification bitfield contents, . = this epoch, * is being justified now
    # checkpoints for the epochs ago:
    c1, c2, _, _, _ = get_checkpoints(spec, epoch)
    put_checkpoints_in_block_roots(spec, state, [c1, c2])

    old_finalized = state.finalized_checkpoint
    state.previous_justified_checkpoint = c2
    state.current_justified_checkpoint = c2
    state.justification_bits = spec.Bitvector[spec.JUSTIFICATION_BITS_LENGTH]()
    state.justification_bits[0] = 1  # mock 2nd latest epoch as justified (this is pre-shift)
    # mock the 1st latest epoch as justifiable, with 2nd as source
    add_mock_attestations(
        spec,
        state,
        epoch=epoch - 1,
        source=c2,
        target=c1,
        sufficient_support=sufficient_support,
        messed_up_target=messed_up_target,
    )

    # process!
    yield from run_process_just_and_fin(spec, state)

    assert state.previous_justified_checkpoint == c2  # changed to old current
    if sufficient_support and not messed_up_target:
        assert state.current_justified_checkpoint == c1  # changed to 1st latest
        assert state.finalized_checkpoint == c2  # finalized previous justified epoch
    else:
        assert state.current_justified_checkpoint == c2  # still old current
        assert state.finalized_checkpoint == old_finalized  # no new finalized


@with_all_phases
@spec_state_test
def test_234_ok_support(spec, state):
    yield from finalize_on_234(spec, state, 5, True)


@with_all_phases
@spec_state_test
def test_234_poor_support(spec, state):
    yield from finalize_on_234(spec, state, 5, False)


@with_all_phases
@spec_state_test
def test_23_ok_support(spec, state):
    yield from finalize_on_23(spec, state, 4, True)


@with_all_phases
@spec_state_test
def test_23_poor_support(spec, state):
    yield from finalize_on_23(spec, state, 4, False)


@with_all_phases
@spec_state_test
def test_123_ok_support(spec, state):
    yield from finalize_on_123(spec, state, 6, True)


@with_all_phases
@spec_state_test
def test_123_poor_support(spec, state):
    yield from finalize_on_123(spec, state, 6, False)


@with_all_phases
@spec_state_test
def test_12_ok_support(spec, state):
    yield from finalize_on_12(spec, state, 3, True, False)


@with_all_phases
@spec_state_test
def test_12_ok_support_messed_target(spec, state):
    yield from finalize_on_12(spec, state, 3, True, True)


@with_all_phases
@spec_state_test
def test_12_poor_support(spec, state):
    yield from finalize_on_12(spec, state, 3, False, False)


@with_all_phases
@spec_state_test
def test_balance_threshold_with_exited_validators(spec, state):
    """
    This test exercises a very specific failure mode where
    exited validators are incorrectly included in the total active balance
    when weighing justification.
    """
    rng = Random(133333)
    # move past genesis conditions
    for _ in range(3):
        next_epoch_via_block(spec, state)

    # mock attestation helper requires last slot of epoch
    for _ in range(spec.SLOTS_PER_EPOCH - 1):
        next_slot(spec, state)

    # Step 1: Exit ~1/2 vals in current epoch
    epoch = spec.get_current_epoch(state)
    for index in spec.get_active_validator_indices(state, epoch):
        if rng.choice([True, False]):
            continue

        validator = state.validators[index]
        validator.exit_epoch = epoch
        validator.withdrawable_epoch = epoch + 1
        validator.withdrawable_epoch = (
            validator.exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        )

    exited_validators = get_unslashed_exited_validators(spec, state)
    assert len(exited_validators) != 0

    source = state.current_justified_checkpoint
    target = spec.Checkpoint(epoch=epoch, root=spec.get_block_root(state, epoch))
    add_mock_attestations(
        spec,
        state,
        epoch,
        source,
        target,
        sufficient_support=False,
    )

    if not is_post_altair(spec):
        current_attestations = spec.get_matching_target_attestations(state, epoch)
        total_active_balance = spec.get_total_active_balance(state)
        current_target_balance = spec.get_attesting_balance(state, current_attestations)
        # Check we will not justify the current checkpoint
        does_justify = current_target_balance * 3 >= total_active_balance * 2
        assert not does_justify
        # Ensure we would have justified the current checkpoint w/ the exited validators
        current_exited_balance = spec.get_total_balance(state, exited_validators)
        does_justify = (
            current_target_balance + current_exited_balance
        ) * 3 >= total_active_balance * 2
        assert does_justify
    else:
        current_indices = spec.get_unslashed_participating_indices(
            state, spec.TIMELY_TARGET_FLAG_INDEX, epoch
        )
        total_active_balance = spec.get_total_active_balance(state)
        current_target_balance = spec.get_total_balance(state, current_indices)
        # Check we will not justify the current checkpoint
        does_justify = current_target_balance * 3 >= total_active_balance * 2
        assert not does_justify
        # Ensure we would have justified the current checkpoint w/ the exited validators
        current_exited_balance = spec.get_total_balance(state, exited_validators)
        does_justify = (
            current_target_balance + current_exited_balance
        ) * 3 >= total_active_balance * 2
        assert does_justify

    yield from run_process_just_and_fin(spec, state)

    assert state.current_justified_checkpoint.epoch != epoch
