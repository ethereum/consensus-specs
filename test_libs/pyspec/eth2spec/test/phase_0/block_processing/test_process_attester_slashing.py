from eth2spec.test.context import spec_state_test, expect_assertion_error, always_bls, with_all_phases
from eth2spec.test.helpers.attestations import sign_indexed_attestation
from eth2spec.test.helpers.attester_slashings import get_valid_attester_slashing
from eth2spec.test.helpers.block import apply_empty_block
from eth2spec.test.helpers.state import (
    get_balance,
    next_epoch,
)


def run_attester_slashing_processing(spec, state, attester_slashing, valid=True):
    """
    Run ``process_attester_slashing``, yielding:
      - pre-state ('pre')
      - attester_slashing ('attester_slashing')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    yield 'pre', state
    yield 'attester_slashing', attester_slashing

    if not valid:
        expect_assertion_error(lambda: spec.process_attester_slashing(state, attester_slashing))
        yield 'post', None
        return

    slashed_indices = (
        attester_slashing.attestation_1.custody_bit_0_indices
        + attester_slashing.attestation_1.custody_bit_1_indices
    )

    proposer_index = spec.get_beacon_proposer_index(state)
    pre_proposer_balance = get_balance(state, proposer_index)
    pre_slashings = {slashed_index: get_balance(state, slashed_index) for slashed_index in slashed_indices}
    pre_withdrawalable_epochs = {
        slashed_index: state.validators[slashed_index].withdrawable_epoch
        for slashed_index in slashed_indices
    }

    total_proposer_rewards = sum(
        balance // spec.WHISTLEBLOWER_REWARD_QUOTIENT
        for balance in pre_slashings.values()
    )

    # Process slashing
    spec.process_attester_slashing(state, attester_slashing)

    for slashed_index in slashed_indices:
        pre_withdrawalable_epoch = pre_withdrawalable_epochs[slashed_index]
        slashed_validator = state.validators[slashed_index]

        # Check slashing
        assert slashed_validator.slashed
        assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        if pre_withdrawalable_epoch < spec.FAR_FUTURE_EPOCH:
            expected_withdrawable_epoch = max(
                pre_withdrawalable_epoch,
                spec.get_current_epoch(state) + spec.EPOCHS_PER_SLASHINGS_VECTOR
            )
            assert slashed_validator.withdrawable_epoch == expected_withdrawable_epoch
        else:
            assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
        assert get_balance(state, slashed_index) < pre_slashings[slashed_index]

    if proposer_index not in slashed_indices:
        # gained whistleblower reward
        assert get_balance(state, proposer_index) == pre_proposer_balance + total_proposer_rewards
    else:
        # gained rewards for all slashings, which may include others. And only lost that of themselves.
        expected_balance = (
            pre_proposer_balance
            + total_proposer_rewards
            - pre_slashings[proposer_index] // spec.MIN_SLASHING_PENALTY_QUOTIENT
        )

        assert get_balance(state, proposer_index) == expected_balance

    yield 'post', state


@with_all_phases
@spec_state_test
def test_success_double(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@spec_state_test
def test_success_surround(spec, state):
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    state.current_justified_checkpoint.epoch += 1
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)
    attestation_1 = attester_slashing.attestation_1
    attestation_2 = attester_slashing.attestation_2

    # set attestion1 to surround attestation 2
    attestation_1.data.source.epoch = attestation_2.data.source.epoch - 1
    attestation_1.data.target.epoch = attestation_2.data.target.epoch + 1

    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@always_bls
@spec_state_test
def test_success_already_exited_recent(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    slashed_indices = (
        attester_slashing.attestation_1.custody_bit_0_indices
        + attester_slashing.attestation_1.custody_bit_1_indices
    )
    for index in slashed_indices:
        spec.initiate_validator_exit(state, index)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@always_bls
@spec_state_test
def test_success_already_exited_long_ago(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    slashed_indices = (
        attester_slashing.attestation_1.custody_bit_0_indices
        + attester_slashing.attestation_1.custody_bit_1_indices
    )
    for index in slashed_indices:
        spec.initiate_validator_exit(state, index)
        state.validators[index].withdrawable_epoch = spec.get_current_epoch(state) + 2

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@always_bls
@spec_state_test
def test_invalid_sig_1(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)
    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@with_all_phases
@always_bls
@spec_state_test
def test_invalid_sig_2(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=False)
    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@with_all_phases
@always_bls
@spec_state_test
def test_invalid_sig_1_and_2(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=False)
    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@with_all_phases
@spec_state_test
def test_same_data(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    attester_slashing.attestation_1.data = attester_slashing.attestation_2.data
    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@with_all_phases
@spec_state_test
def test_no_double_or_surround(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    attester_slashing.attestation_1.data.target.epoch += 1
    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@with_all_phases
@spec_state_test
def test_participants_already_slashed(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    # set all indices to slashed
    attestation_1 = attester_slashing.attestation_1
    validator_indices = attestation_1.custody_bit_0_indices + attestation_1.custody_bit_1_indices
    for index in validator_indices:
        state.validators[index].slashed = True

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@with_all_phases
@spec_state_test
def test_custody_bit_0_and_1_intersect(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    attester_slashing.attestation_1.custody_bit_1_indices.append(
        attester_slashing.attestation_1.custody_bit_0_indices[0]
    )

    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@always_bls
@with_all_phases
@spec_state_test
def test_att1_bad_extra_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = attester_slashing.attestation_1.custody_bit_0_indices
    options = list(set(range(len(state.validators))) - set(indices))
    indices.append(options[len(options) // 2])  # add random index, not previously in attestation.
    attester_slashing.attestation_1.custody_bit_0_indices = sorted(indices)
    # Do not sign the modified attestation (it's ok to slash if attester signed, not if they did not),
    # see if the bad extra index is spotted, and slashing is aborted.

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@always_bls
@with_all_phases
@spec_state_test
def test_att1_bad_replaced_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = attester_slashing.attestation_1.custody_bit_0_indices
    options = list(set(range(len(state.validators))) - set(indices))
    indices[3] = options[len(options) // 2]  # replace with random index, not previously in attestation.
    attester_slashing.attestation_1.custody_bit_0_indices = sorted(indices)
    # Do not sign the modified attestation (it's ok to slash if attester signed, not if they did not),
    # see if the bad replaced index is spotted, and slashing is aborted.

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@always_bls
@with_all_phases
@spec_state_test
def test_att2_bad_extra_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = attester_slashing.attestation_2.custody_bit_0_indices
    options = list(set(range(len(state.validators))) - set(indices))
    indices.append(options[len(options) // 2])  # add random index, not previously in attestation.
    attester_slashing.attestation_2.custody_bit_0_indices = sorted(indices)
    # Do not sign the modified attestation (it's ok to slash if attester signed, not if they did not),
    # see if the bad extra index is spotted, and slashing is aborted.

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@always_bls
@with_all_phases
@spec_state_test
def test_att2_bad_replaced_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = attester_slashing.attestation_2.custody_bit_0_indices
    options = list(set(range(len(state.validators))) - set(indices))
    indices[3] = options[len(options) // 2]  # replace with random index, not previously in attestation.
    attester_slashing.attestation_2.custody_bit_0_indices = sorted(indices)
    # Do not sign the modified attestation (it's ok to slash if attester signed, not if they did not),
    # see if the bad replaced index is spotted, and slashing is aborted.

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@with_all_phases
@spec_state_test
def test_unsorted_att_1_bit0(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    indices = attester_slashing.attestation_1.custody_bit_0_indices
    assert len(indices) >= 3
    indices[1], indices[2] = indices[2], indices[1]  # unsort second and third index
    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


@with_all_phases
@spec_state_test
def test_unsorted_att_2_bit0(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=False)

    indices = attester_slashing.attestation_2.custody_bit_0_indices
    assert len(indices) >= 3
    indices[1], indices[2] = indices[2], indices[1]  # unsort second and third index
    sign_indexed_attestation(spec, state, attester_slashing.attestation_2)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)


# note: unsorted indices for custody bit 0 are to be introduced in phase 1 testing.
