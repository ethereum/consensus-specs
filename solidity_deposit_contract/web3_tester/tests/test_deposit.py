from random import randint
import pytest
import eth_utils

from eth_consensus_specs.phase0.mainnet import DepositData
from eth_consensus_specs.utils.ssz.ssz_typing import List
from eth_consensus_specs.utils.ssz.ssz_impl import hash_tree_root

from tests.conftest import (
    FULL_DEPOSIT_AMOUNT,
    MIN_DEPOSIT_AMOUNT,
)


SAMPLE_PUBKEY = b'\x11' * 48
SAMPLE_WITHDRAWAL_CREDENTIALS = b'\x22' * 32
SAMPLE_VALID_SIGNATURE = b'\x33' * 96


@pytest.fixture
def deposit_input(amount):
    """
    pubkey: bytes[48]
    withdrawal_credentials: bytes[32]
    signature: bytes[96]
    deposit_data_root: bytes[32]
    """
    return (
        SAMPLE_PUBKEY,
        SAMPLE_WITHDRAWAL_CREDENTIALS,
        SAMPLE_VALID_SIGNATURE,
        hash_tree_root(
            DepositData(
                pubkey=SAMPLE_PUBKEY,
                withdrawal_credentials=SAMPLE_WITHDRAWAL_CREDENTIALS,
                amount=amount,
                signature=SAMPLE_VALID_SIGNATURE,
            ),
        )
    )


@pytest.mark.parametrize(
    ('success', 'amount'),
    [
        (True, FULL_DEPOSIT_AMOUNT),
        (True, MIN_DEPOSIT_AMOUNT),
        (False, MIN_DEPOSIT_AMOUNT - 1),
        (True, FULL_DEPOSIT_AMOUNT + 1)
    ]
)
def test_deposit_amount(registration_contract,
                        w3,
                        success,
                        amount,
                        assert_tx_failed,
                        deposit_input):
    call = registration_contract.functions.deposit(*deposit_input)
    if success:
        assert call.transact({"value": amount * eth_utils.denoms.gwei})
    else:
        assert_tx_failed(
            lambda: call.transact({"value": amount * eth_utils.denoms.gwei})
        )


@pytest.mark.parametrize(
    'amount',
    [
        (FULL_DEPOSIT_AMOUNT)
    ]
)
@pytest.mark.parametrize(
    'invalid_pubkey,invalid_withdrawal_credentials,invalid_signature,success',
    [
        (False, False, False, True),
        (True, False, False, False),
        (False, True, False, False),
        (False, False, True, False),
    ]
)
def test_deposit_inputs(registration_contract,
                        w3,
                        assert_tx_failed,
                        amount,
                        invalid_pubkey,
                        invalid_withdrawal_credentials,
                        invalid_signature,
                        success):
    pubkey = SAMPLE_PUBKEY[2:] if invalid_pubkey else SAMPLE_PUBKEY
    withdrawal_credentials = (
        SAMPLE_WITHDRAWAL_CREDENTIALS[2:] if invalid_withdrawal_credentials
        else SAMPLE_WITHDRAWAL_CREDENTIALS
    )
    signature = SAMPLE_VALID_SIGNATURE[2:] if invalid_signature else SAMPLE_VALID_SIGNATURE

    call = registration_contract.functions.deposit(
        pubkey,
        withdrawal_credentials,
        signature,
        hash_tree_root(
            DepositData(
                pubkey=SAMPLE_PUBKEY if invalid_pubkey else pubkey,
                withdrawal_credentials=(
                    SAMPLE_WITHDRAWAL_CREDENTIALS if invalid_withdrawal_credentials
                    else withdrawal_credentials
                ),
                amount=amount,
                signature=SAMPLE_VALID_SIGNATURE if invalid_signature else signature,
            ),
        )
    )
    if success:
        assert call.transact({"value": amount * eth_utils.denoms.gwei})
    else:
        assert_tx_failed(
            lambda: call.transact({"value": amount * eth_utils.denoms.gwei})
        )


def test_deposit_event_log(registration_contract, a0, w3):
    log_filter = registration_contract.events.DepositEvent.create_filter(
        fromBlock='latest',
    )
    deposit_amount_list = [randint(MIN_DEPOSIT_AMOUNT, FULL_DEPOSIT_AMOUNT * 2) for _ in range(3)]

    for i in range(3):
        deposit_input = (
            SAMPLE_PUBKEY,
            SAMPLE_WITHDRAWAL_CREDENTIALS,
            SAMPLE_VALID_SIGNATURE,
            hash_tree_root(
                DepositData(
                    pubkey=SAMPLE_PUBKEY,
                    withdrawal_credentials=SAMPLE_WITHDRAWAL_CREDENTIALS,
                    amount=deposit_amount_list[i],
                    signature=SAMPLE_VALID_SIGNATURE,
                ),
            )
        )
        registration_contract.functions.deposit(
            *deposit_input,
        ).transact({"value": deposit_amount_list[i] * eth_utils.denoms.gwei})

        logs = log_filter.get_new_entries()
        assert len(logs) == 1
        log = logs[0]['args']

        assert log['pubkey'] == deposit_input[0]
        assert log['withdrawal_credentials'] == deposit_input[1]
        assert log['amount'] == deposit_amount_list[i].to_bytes(8, 'little')
        assert log['signature'] == deposit_input[2]
        assert log['index'] == i.to_bytes(8, 'little')


def test_deposit_tree(registration_contract, w3, assert_tx_failed):
    log_filter = registration_contract.events.DepositEvent.create_filter(
        fromBlock='latest',
    )

    deposit_amount_list = [randint(MIN_DEPOSIT_AMOUNT, FULL_DEPOSIT_AMOUNT * 2) for _ in range(10)]
    deposit_data_list = []
    for i in range(0, 10):
        deposit_data = DepositData(
            pubkey=SAMPLE_PUBKEY,
            withdrawal_credentials=SAMPLE_WITHDRAWAL_CREDENTIALS,
            amount=deposit_amount_list[i],
            signature=SAMPLE_VALID_SIGNATURE,
        )
        deposit_input = (
            SAMPLE_PUBKEY,
            SAMPLE_WITHDRAWAL_CREDENTIALS,
            SAMPLE_VALID_SIGNATURE,
            hash_tree_root(deposit_data),
        )
        deposit_data_list.append(deposit_data)

        tx_hash = registration_contract.functions.deposit(
            *deposit_input,
        ).transact({"value": deposit_amount_list[i] * eth_utils.denoms.gwei})
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        print("deposit transaction consumes %d gas" % receipt['gasUsed'])

        logs = log_filter.get_new_entries()
        assert len(logs) == 1
        log = logs[0]['args']

        assert log["index"] == i.to_bytes(8, 'little')

        # Check deposit count and root
        count = len(deposit_data_list).to_bytes(8, 'little')
        assert count == registration_contract.functions.get_deposit_count().call()
        root = hash_tree_root(List[DepositData, 2**32](*deposit_data_list))
        assert root == registration_contract.functions.get_deposit_root().call()
