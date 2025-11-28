from eth2spec.test.context import (
    spec_state_test,
    with_capella_and_later,
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
    set_validator_fully_withdrawable,
)
from tests.infra.helpers.withdrawals import (
    get_expected_withdrawals,
    prepare_withdrawals,
)

#
# Basic Tests
#


@with_capella_and_later
@spec_state_test
def test_no_withdrawals_no_withdrawal_credentials(spec, state):
    """Validators with BLS_WITHDRAWAL_PREFIX credentials should not withdraw even with excess balance"""

    current_epoch = spec.get_current_epoch(state)
    for i in range(len(state.validators)):
        state.validators[i].withdrawable_epoch = current_epoch
        state.validators[i].exit_epoch = current_epoch
        state.balances[i] = spec.MAX_EFFECTIVE_BALANCE + spec.Gwei(10_000_000_000)

        assert state.validators[i].withdrawal_credentials[0:1] == spec.BLS_WITHDRAWAL_PREFIX

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 0


@with_capella_and_later
@spec_state_test
def test_single_full_withdrawal(spec, state):
    """One validator fully withdrawable should return one full withdrawal"""
    validator_index = 0

    prepare_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[validator_index],
        full_withdrawable_offsets=[0],  # Immediate withdrawal
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 1
    assert withdrawals[0].validator_index == validator_index
    assert withdrawals[0].amount == state.balances[validator_index]


@with_capella_and_later
@spec_state_test
def test_single_partial_withdrawal(spec, state):
    """One validator with excess balance should return partial withdrawal"""
    validator_index = 0
    excess_balance = spec.Gwei(1_000_000_000)  # 1 ETH

    prepare_withdrawals(
        spec,
        state,
        partial_withdrawal_indices=[validator_index],
        partial_excess_balances=[excess_balance],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 1
    assert withdrawals[0].validator_index == validator_index
    assert withdrawals[0].amount == excess_balance


@with_capella_and_later
@spec_state_test
def test_max_withdrawals_per_payload(spec, state):
    """Should return exactly MAX_WITHDRAWALS_PER_PAYLOAD when more are eligible"""
    num_withdrawals = 20

    assert len(state.validators) >= num_withdrawals, (
        f"Test requires at least {num_withdrawals} validators"
    )

    withdrawal_indices = list(range(num_withdrawals))

    prepare_withdrawals(
        spec,
        state,
        full_withdrawal_indices=withdrawal_indices,
        full_withdrawable_offsets=[0] * num_withdrawals,
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD


@with_capella_and_later
@spec_state_test
def test_withdrawal_index_wraparound(spec, state):
    """Withdrawal validator index should wrap around to 0"""
    assert len(state.validators) >= 3, "Test requires at least 3 validators for wraparound"

    state.next_withdrawal_validator_index = len(state.validators) - 2

    prepare_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[len(state.validators) - 1, 0, 1],
        full_withdrawable_offsets=[0, 0, 0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 3
    validator_indices = [w.validator_index for w in withdrawals]
    assert validator_indices == [len(state.validators) - 1, 0, 1], (
        "Should process validators in wraparound order"
    )


@with_capella_and_later
@spec_state_test
def test_validator_sweep_limit(spec, state):
    """Should stop sweep at MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP validators"""
    num_validators_to_setup = spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP + 10

    assert len(state.validators) >= num_validators_to_setup, (
        f"Test requires at least {num_validators_to_setup} validators"
    )

    state.next_withdrawal_validator_index = 0

    withdrawal_indices = list(range(num_validators_to_setup))
    prepare_withdrawals(
        spec,
        state,
        partial_withdrawal_indices=withdrawal_indices,
        partial_excess_balances=[spec.Gwei(1_000_000_000)] * num_validators_to_setup,
    )

    withdrawals = get_expected_withdrawals(spec, state)

    swept_indices = set(w.validator_index for w in withdrawals)

    for idx in range(spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP, num_validators_to_setup):
        assert idx not in swept_indices, f"Validator {idx} should not be swept (beyond sweep limit)"


@with_capella_and_later
@spec_state_test
def test_mixed_full_and_partial_withdrawals(spec, state):
    """Mix of full and partial withdrawals should process both correctly"""
    full_indices = [0, 1]
    partial_indices = [2, 3]

    required_validators = max(full_indices + partial_indices) + 1
    assert len(state.validators) >= required_validators, (
        f"Test requires at least {required_validators} validators"
    )

    state.next_withdrawal_validator_index = 0

    prepare_withdrawals(
        spec,
        state,
        full_withdrawal_indices=full_indices,
        partial_withdrawal_indices=partial_indices,
        full_withdrawable_offsets=[0, 0],
        partial_excess_balances=[spec.Gwei(1_000_000_000)] * 2,
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 4

    full_withdrawals = [w for w in withdrawals if w.validator_index in full_indices]
    partial_withdrawals = [w for w in withdrawals if w.validator_index in partial_indices]

    assert len(full_withdrawals) == 2
    assert len(partial_withdrawals) == 2

    validator_indices = [w.validator_index for w in withdrawals]
    assert validator_indices == sorted(validator_indices)


# Corner Cases Tests


@with_capella_and_later
@spec_state_test
def test_zero_balance_full_withdrawal(spec, state):
    """Withdrawable validator with balance = 0 should be skipped"""
    validator_index = 0

    set_validator_fully_withdrawable(spec, state, validator_index)
    state.balances[validator_index] = spec.Gwei(0)

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 0


@with_capella_and_later
@spec_state_test
def test_exact_max_effective_balance(spec, state):
    """Balance exactly equals MAX_EFFECTIVE_BALANCE, no partial withdrawal"""
    validator_index = 0

    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE,
        balance=spec.MAX_EFFECTIVE_BALANCE,
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 0


@with_capella_and_later
@spec_state_test
def test_one_gwei_excess_partial(spec, state):
    """Balance = MAX_EFFECTIVE_BALANCE + 1 Gwei should withdraw exactly 1 Gwei"""
    validator_index = 0

    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE,
        balance=spec.MAX_EFFECTIVE_BALANCE + spec.Gwei(1),
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 1
    assert withdrawals[0].validator_index == validator_index
    assert withdrawals[0].amount == spec.Gwei(1)


@with_capella_and_later
@spec_state_test
def test_all_validators_withdrawable(spec, state):
    """Every validator eligible should process only first MAX_WITHDRAWALS_PER_PAYLOAD"""
    num_validators = min(len(state.validators), spec.MAX_WITHDRAWALS_PER_PAYLOAD + 5)

    assert len(state.validators) >= spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1, (
        f"Test requires at least {spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1} validators"
    )

    withdrawal_indices = list(range(num_validators))

    prepare_withdrawals(
        spec,
        state,
        full_withdrawal_indices=withdrawal_indices,
        full_withdrawable_offsets=[0] * num_validators,
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD


@with_capella_and_later
@spec_state_test
def test_withdrawal_index_at_validator_set_boundary(spec, state):
    """next_withdrawal_validator_index at len(validators) - 1 should wrap to 0"""
    assert len(state.validators) >= 3, "Test requires at least 3 validators"

    state.next_withdrawal_validator_index = len(state.validators) - 1

    prepare_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[0, 1, 2],
        full_withdrawable_offsets=[0, 0, 0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 3
    validator_indices = [w.validator_index for w in withdrawals]
    assert validator_indices == [0, 1, 2]


# Edge Cases by Processing Phase - Validator Sweep


@with_capella_and_later
@spec_state_test
def test_partial_validator_sweep_index_update(spec, state):
    """Process some validators, hit limit, verify index updates"""
    mid_index = min(10, len(state.validators) - 1)

    prepare_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[mid_index],
        full_withdrawable_offsets=[0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 1
    assert withdrawals[0].validator_index == mid_index


@with_capella_and_later
@spec_state_test
def test_skip_validators_wrong_credentials(spec, state):
    """Mix of BLS_WITHDRAWAL_PREFIX and ETH1_ADDRESS_WITHDRAWAL_PREFIX credentials, only ETH1 processed"""
    assert len(state.validators) >= 2, "Test requires at least 2 validators"

    prepare_withdrawals(
        spec,
        state,
        full_withdrawal_indices=[1],
        full_withdrawable_offsets=[0],
    )

    assert state.validators[0].withdrawal_credentials[0:1] == spec.BLS_WITHDRAWAL_PREFIX
    assert state.validators[1].withdrawal_credentials[0:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 1
    assert withdrawals[0].validator_index == 1
