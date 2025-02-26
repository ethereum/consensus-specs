from random import Random

from eth2spec.test.context import (
    spec_state_test, expect_assertion_error, always_bls, with_all_phases,
    with_custom_state, spec_test, single_phase,
    low_balances, misc_balances,
)
from eth2spec.test.helpers.attestations import sign_indexed_attestation
from eth2spec.test.helpers.attester_slashings import (
    get_valid_attester_slashing, get_valid_attester_slashing_by_indices,
    get_indexed_attestation_participants, get_attestation_2_data, get_attestation_1_data,
)
from eth2spec.test.helpers.proposer_slashings import (
    get_min_slashing_penalty_quotient,
    get_whistleblower_reward_quotient,
)
from eth2spec.test.helpers.state import (
    get_balance,
    next_epoch_via_block,
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

    slashed_indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)

    proposer_index = spec.get_beacon_proposer_index(state)
    pre_proposer_balance = get_balance(state, proposer_index)
    pre_slashing_balances = {slashed_index: get_balance(state, slashed_index) for slashed_index in slashed_indices}
    pre_slashing_effectives = {
        slashed_index: state.validators[slashed_index].effective_balance
        for slashed_index in slashed_indices
    }
    pre_withdrawalable_epochs = {
        slashed_index: state.validators[slashed_index].withdrawable_epoch
        for slashed_index in slashed_indices
    }

    total_proposer_rewards = sum(
        effective_balance // get_whistleblower_reward_quotient(spec)
        for effective_balance in pre_slashing_effectives.values()
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
        if slashed_index != proposer_index:
            # NOTE: check proposer balances below
            assert get_balance(state, slashed_index) < pre_slashing_balances[slashed_index]

    if proposer_index not in slashed_indices:
        # gained whistleblower reward
        assert get_balance(state, proposer_index) == pre_proposer_balance + total_proposer_rewards
    else:
        # gained rewards for all slashings, which may include others. And only lost that of themselves.
        expected_balance = (
            pre_proposer_balance
            + total_proposer_rewards
            - pre_slashing_effectives[proposer_index] // get_min_slashing_penalty_quotient(spec)
        )

        assert get_balance(state, proposer_index) == expected_balance

    yield 'post', state


@with_all_phases
@spec_state_test
def test_basic_double(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@spec_state_test
def test_basic_surround(spec, state):
    next_epoch_via_block(spec, state)

    state.current_justified_checkpoint.epoch += 1
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)
    att_1_data = get_attestation_1_data(spec, attester_slashing)
    att_2_data = get_attestation_2_data(spec, attester_slashing)

    # set attestation1 to surround attestation 2
    att_1_data.source.epoch = att_2_data.source.epoch - 1
    att_1_data.target.epoch = att_2_data.target.epoch + 1

    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@spec_state_test
@always_bls
def test_already_exited_recent(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    slashed_indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)
    for index in slashed_indices:
        spec.initiate_validator_exit(state, index)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@spec_state_test
@always_bls
def test_proposer_index_slashed(spec, state):
    # Transition past genesis slot because generally doesn't have a proposer
    next_epoch_via_block(spec, state)

    proposer_index = spec.get_beacon_proposer_index(state)
    attester_slashing = get_valid_attester_slashing_by_indices(
        spec, state,
        [proposer_index],
        signed_1=True, signed_2=True,
    )

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@spec_state_test
def test_attestation_from_future(spec, state):
    # Transition state to future to enable generation of a "future" attestation
    future_state = state.copy()
    next_epoch_via_block(spec, future_state)
    # Generate slashing using the future state
    attester_slashing = get_valid_attester_slashing(
        spec, future_state,
        slot=state.slot + 5,  # Slot is in the future wrt `state`
        signed_1=True, signed_2=True
    )

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@single_phase
def test_low_balances(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@with_custom_state(balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@single_phase
def test_misc_balances(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@with_custom_state(balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@single_phase
def test_with_effective_balance_disparity(spec, state):
    # Jitter balances to be different from effective balances
    rng = Random(12345)
    for i in range(len(state.balances)):
        pre = int(state.balances[i])
        state.balances[i] += rng.randrange(max(pre - 5000, 0), pre + 5000)

    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@spec_state_test
@always_bls
def test_already_exited_long_ago(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)
    slashed_indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)
    for index in slashed_indices:
        spec.initiate_validator_exit(state, index)
        state.validators[index].withdrawable_epoch = spec.get_current_epoch(state) + 2

    yield from run_attester_slashing_processing(spec, state, attester_slashing)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_1(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)
    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_2(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=False)
    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_incorrect_sig_1_and_2(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=False)
    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_same_data(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    indexed_att_1 = attester_slashing.attestation_1
    att_2_data = get_attestation_2_data(spec, attester_slashing)
    indexed_att_1.data = att_2_data
    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_no_double_or_surround(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    att_1_data = get_attestation_1_data(spec, attester_slashing)
    att_1_data.target.epoch += 1

    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_participants_already_slashed(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    # set all indices to slashed
    validator_indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)
    for index in validator_indices:
        state.validators[index].slashed = True

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att1_high_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)
    indices.append(spec.ValidatorIndex(len(state.validators)))  # off by 1
    attester_slashing.attestation_1.attesting_indices = indices

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att2_high_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_2)
    indices.append(spec.ValidatorIndex(len(state.validators)))  # off by 1
    attester_slashing.attestation_2.attesting_indices = indices

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att1_empty_indices(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    attester_slashing.attestation_1.attesting_indices = []
    attester_slashing.attestation_1.signature = spec.bls.G2_POINT_AT_INFINITY

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att2_empty_indices(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=False)

    attester_slashing.attestation_2.attesting_indices = []
    attester_slashing.attestation_2.signature = spec.bls.G2_POINT_AT_INFINITY

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_all_empty_indices(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=False)

    attester_slashing.attestation_1.attesting_indices = []
    attester_slashing.attestation_1.signature = spec.bls.G2_POINT_AT_INFINITY

    attester_slashing.attestation_2.attesting_indices = []
    attester_slashing.attestation_2.signature = spec.bls.G2_POINT_AT_INFINITY

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att1_bad_extra_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = get_indexed_attestation_participants(spec, attester_slashing.attestation_1)
    options = list(set(range(len(state.validators))) - set(indices))
    indices.append(options[len(options) // 2])  # add random index, not previously in attestation.
    attester_slashing.attestation_1.attesting_indices = sorted(indices)
    # Do not sign the modified attestation (it's ok to slash if attester signed, not if they did not),
    # see if the bad extra index is spotted, and slashing is aborted.

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att1_bad_replaced_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = attester_slashing.attestation_1.attesting_indices
    options = list(set(range(len(state.validators))) - set(indices))
    indices[3] = options[len(options) // 2]  # replace with random index, not previously in attestation.
    attester_slashing.attestation_1.attesting_indices = sorted(indices)
    # Do not sign the modified attestation (it's ok to slash if attester signed, not if they did not),
    # see if the bad replaced index is spotted, and slashing is aborted.

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att2_bad_extra_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = attester_slashing.attestation_2.attesting_indices
    options = list(set(range(len(state.validators))) - set(indices))
    indices.append(options[len(options) // 2])  # add random index, not previously in attestation.
    attester_slashing.attestation_2.attesting_indices = sorted(indices)
    # Do not sign the modified attestation (it's ok to slash if attester signed, not if they did not),
    # see if the bad extra index is spotted, and slashing is aborted.

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att2_bad_replaced_index(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=True)

    indices = attester_slashing.attestation_2.attesting_indices
    options = list(set(range(len(state.validators))) - set(indices))
    indices[3] = options[len(options) // 2]  # replace with random index, not previously in attestation.
    attester_slashing.attestation_2.attesting_indices = sorted(indices)
    # Do not sign the modified attestation (it's ok to slash if attester signed, not if they did not),
    # see if the bad replaced index is spotted, and slashing is aborted.

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att1_duplicate_index_normal_signed(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    indices = list(attester_slashing.attestation_1.attesting_indices)
    indices.pop(1)  # remove an index, make room for the additional duplicate index.
    attester_slashing.attestation_1.attesting_indices = sorted(indices)

    # The signature will be valid for a single occurrence. If the transition accidentally ignores the duplicate.
    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    indices.append(indices[0])  # add one of the indices a second time
    attester_slashing.attestation_1.attesting_indices = sorted(indices)

    # it will just appear normal, unless the double index is spotted
    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att2_duplicate_index_normal_signed(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=False)

    indices = list(attester_slashing.attestation_2.attesting_indices)
    indices.pop(2)  # remove an index, make room for the additional duplicate index.
    attester_slashing.attestation_2.attesting_indices = sorted(indices)

    # The signature will be valid for a single occurrence. If the transition accidentally ignores the duplicate.
    sign_indexed_attestation(spec, state, attester_slashing.attestation_2)

    indices.append(indices[1])  # add one of the indices a second time
    attester_slashing.attestation_2.attesting_indices = sorted(indices)

    # it will just appear normal, unless the double index is spotted
    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att1_duplicate_index_double_signed(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    indices = list(attester_slashing.attestation_1.attesting_indices)
    indices.pop(1)  # remove an index, make room for the additional duplicate index.
    indices.append(indices[2])  # add one of the indices a second time
    attester_slashing.attestation_1.attesting_indices = sorted(indices)
    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)  # will have one attester signing it double

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_att2_duplicate_index_double_signed(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=False)

    indices = list(attester_slashing.attestation_2.attesting_indices)
    indices.pop(1)  # remove an index, make room for the additional duplicate index.
    indices.append(indices[2])  # add one of the indices a second time
    attester_slashing.attestation_2.attesting_indices = sorted(indices)
    sign_indexed_attestation(spec, state, attester_slashing.attestation_2)  # will have one attester signing it double

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_unsorted_att_1(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    indices = attester_slashing.attestation_1.attesting_indices
    assert len(indices) >= 3
    indices[1], indices[2] = indices[2], indices[1]  # unsort second and third index
    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_unsorted_att_2(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=True, signed_2=False)

    indices = attester_slashing.attestation_2.attesting_indices
    assert len(indices) >= 3
    indices[1], indices[2] = indices[2], indices[1]  # unsort second and third index
    sign_indexed_attestation(spec, state, attester_slashing.attestation_2)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, valid=False)
