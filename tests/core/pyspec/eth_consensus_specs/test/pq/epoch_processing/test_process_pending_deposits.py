from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.keys import pubkeys, xmss_pubkeys


def prepare_pending_deposit(spec, pubkey, amount, signature=bytes(96)):
    """
    A finalized pending deposit naming ``pubkey``, which is 48 bytes.
    """
    return spec.PendingDeposit(
        pubkey=spec.Bytes48(pubkey),
        withdrawal_credentials=spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x66" * 20,
        amount=amount,
        signature=spec.Bytes96(signature),
        slot=spec.GENESIS_SLOT,
    )


def run_process_pending_deposits(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")


@with_phases([PQ])
@spec_state_test
def test_new_validator_deposit(spec, state):
    index = len(state.validators)
    pubkey = xmss_pubkeys[index]
    vrf_root = b"\x88" * 32
    amount = spec.MIN_ACTIVATION_BALANCE
    deposit = prepare_pending_deposit(
        spec, spec.XMSS_DEPOSIT_PREFIX + pubkey, amount, vrf_root + bytes(64)
    )
    state.pending_deposits.append(deposit)
    state.deposit_balance_to_consume = amount

    yield from run_process_pending_deposits(spec, state)

    assert len(state.validators) == index + 1
    validator = state.validators[index]
    assert validator.pubkey == pubkey
    assert validator.vrf_root == vrf_root
    assert validator.withdrawal_credentials == deposit.withdrawal_credentials
    assert validator.exit_epoch == spec.FAR_FUTURE_EPOCH
    assert state.balances[index] == amount
    assert len(state.pending_deposits) == 0


@with_phases([PQ])
@spec_state_test
def test_top_up_deposit(spec, state):
    validator_index = 0
    pre_validator_count = len(state.validators)
    pre_balance = state.balances[validator_index]
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    pubkey = spec.XMSS_DEPOSIT_PREFIX + state.validators[validator_index].pubkey
    state.pending_deposits.append(prepare_pending_deposit(spec, pubkey, amount))
    state.deposit_balance_to_consume = amount

    yield from run_process_pending_deposits(spec, state)

    assert len(state.validators) == pre_validator_count
    assert state.balances[validator_index] == pre_balance + amount
    assert len(state.pending_deposits) == 0


@with_phases([PQ])
@spec_state_test
def test_legacy_deposit_is_exited(spec, state):
    index = len(state.validators)
    bls_pubkey = pubkeys[index]
    amount = spec.MIN_ACTIVATION_BALANCE
    deposit = prepare_pending_deposit(spec, bls_pubkey, amount, signature=b"\x99" * 96)
    assert spec.is_legacy_pubkey(deposit.pubkey)
    state.pending_deposits.append(deposit)
    state.deposit_balance_to_consume = 0

    yield from run_process_pending_deposits(spec, state)

    assert len(state.validators) == index + 1
    validator = state.validators[index]
    assert validator.pubkey == spec.sha256(bls_pubkey + spec.LEGACY_XMSS_PUBKEY_DOMAIN)
    assert validator.vrf_root == spec.sha256(bls_pubkey + spec.LEGACY_VRF_ROOT_DOMAIN)
    assert validator.exit_epoch == spec.get_current_epoch(state)
    expected_withdrawable = (
        spec.get_current_epoch(state) + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    assert validator.withdrawable_epoch == expected_withdrawable
    assert state.balances[index] == amount
    assert len(state.pending_deposits) == 0
    assert state.deposit_balance_to_consume == 0
