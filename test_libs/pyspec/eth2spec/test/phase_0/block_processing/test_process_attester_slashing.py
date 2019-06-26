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
    pre_slashed_balances = {slashed_index: get_balance(state, slashed_index) for slashed_index in slashed_indices}
    total_proposer_rewards = sum(
        balance // spec.WHISTLEBLOWING_REWARD_QUOTIENT
        for balance in pre_slashed_balances.values()
    )


    # Process slashing
    spec.process_attester_slashing(state, attester_slashing)

    for slashed_index in slashed_indices:
        slashed_validator = state.validators[slashed_index]

        # Check slashing
        assert slashed_validator.slashed
        assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
        assert get_balance(state, slashed_index) < pre_slashed_balances[slashed_index]

    if proposer_index not in slashed_indices:
        # gained whistleblower reward
        assert get_balance(state, proposer_index) == pre_proposer_balance + total_proposer_rewards
    else:
        # gained rewards for all slashings, which may include others. And only lost that of themselves.
        expected_balance = (
            pre_proposer_balance
            + total_proposer_rewards
            - pre_slashed_balances[proposer_index] // spec.MIN_SLASHING_PENALTY_QUOTIENT
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

    state.current_justified_epoch += 1
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    # set attestion1 to surround attestation 2
    attester_slashing.attestation_1.data.source_epoch = attester_slashing.attestation_2.data.source_epoch - 1
    attester_slashing.attestation_1.data.target_epoch = attester_slashing.attestation_2.data.target_epoch + 1

    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

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

    attester_slashing.attestation_1.data.target_epoch += 1
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
def test_custody_bit_0_and_1(spec, state):
    attester_slashing = get_valid_attester_slashing(spec, state, signed_1=False, signed_2=True)

    attester_slashing.attestation_1.custody_bit_1_indices = (
        attester_slashing.attestation_1.custody_bit_0_indices
    )
    sign_indexed_attestation(spec, state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(spec, state, attester_slashing, False)
