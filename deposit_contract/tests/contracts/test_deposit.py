from random import (
    randint,
)

import pytest

import eth_utils
from tests.contracts.conftest import (
    DEPOSIT_CONTRACT_TREE_DEPTH,
    FULL_DEPOSIT_AMOUNT,
    MIN_DEPOSIT_AMOUNT,
)

from eth2spec.phase0.spec import (
    DepositData,
)
from eth2spec.utils.hash_function import hash
from eth2spec.utils.ssz.ssz_impl import (
    hash_tree_root,
)


def compute_merkle_root(leaf_nodes):
    assert len(leaf_nodes) >= 1
    empty_node = b'\x00' * 32
    child_nodes = leaf_nodes[:]
    for _ in range(DEPOSIT_CONTRACT_TREE_DEPTH):
        parent_nodes = []
        if len(child_nodes) % 2 == 1:
            child_nodes.append(empty_node)
        for j in range(0, len(child_nodes), 2):
            parent_nodes.append(hash(child_nodes[j] + child_nodes[j + 1]))
        child_nodes = parent_nodes
        empty_node = hash(empty_node + empty_node)
    return child_nodes[0]


@pytest.fixture
def deposit_input():
    """
    pubkey: bytes[48]
    withdrawal_credentials: bytes[32]
    signature: bytes[96]
    """
    return (
        b'\x11' * 48,
        b'\x22' * 32,
        b'\x33' * 96,
    )


@pytest.mark.parametrize(
    'value,success',
    [
        (0, True),
        (10, True),
        (55555, True),
        (2**64 - 1, True),
        (2**64, False),
    ]
)
def test_to_little_endian_64(registration_contract, value, success, assert_tx_failed):
    call = registration_contract.functions.to_little_endian_64(value)

    if success:
        little_endian_64 = call.call()
        assert little_endian_64 == (value).to_bytes(8, 'little')
    else:
        assert_tx_failed(
            lambda: call.call()
        )


@pytest.mark.parametrize(
    'success,deposit_amount',
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
                        deposit_amount,
                        assert_tx_failed,
                        deposit_input):
    call = registration_contract.functions.deposit(*deposit_input)
    if success:
        assert call.transact({"value": deposit_amount * eth_utils.denoms.gwei})
    else:
        assert_tx_failed(
            lambda: call.transact({"value": deposit_amount * eth_utils.denoms.gwei})
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
                        deposit_input,
                        invalid_pubkey,
                        invalid_withdrawal_credentials,
                        invalid_signature,
                        success):
    pubkey = deposit_input[0][2:] if invalid_pubkey else deposit_input[0]
    if invalid_withdrawal_credentials:  # this one is different to satisfy linter
        withdrawal_credentials = deposit_input[1][2:]
    else:
        withdrawal_credentials = deposit_input[1]
    signature = deposit_input[2][2:] if invalid_signature else deposit_input[2]

    call = registration_contract.functions.deposit(
        pubkey,
        withdrawal_credentials,
        signature,
    )
    if success:
        assert call.transact({"value": FULL_DEPOSIT_AMOUNT * eth_utils.denoms.gwei})
    else:
        assert_tx_failed(
            lambda: call.transact({"value": FULL_DEPOSIT_AMOUNT * eth_utils.denoms.gwei})
        )


def test_deposit_log(registration_contract, a0, w3, deposit_input):
    log_filter = registration_contract.events.Deposit.createFilter(
        fromBlock='latest',
    )

    deposit_amount_list = [randint(MIN_DEPOSIT_AMOUNT, FULL_DEPOSIT_AMOUNT * 2) for _ in range(3)]
    for i in range(3):
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
        assert log['merkle_tree_index'] == i.to_bytes(8, 'little')


def test_deposit_tree(registration_contract, w3, assert_tx_failed, deposit_input):
    log_filter = registration_contract.events.Deposit.createFilter(
        fromBlock='latest',
    )

    deposit_amount_list = [randint(MIN_DEPOSIT_AMOUNT, FULL_DEPOSIT_AMOUNT * 2) for _ in range(10)]
    leaf_nodes = []
    for i in range(0, 10):
        tx_hash = registration_contract.functions.deposit(
            *deposit_input,
        ).transact({"value": deposit_amount_list[i] * eth_utils.denoms.gwei})
        receipt = w3.eth.getTransactionReceipt(tx_hash)
        print("deposit transaction consumes %d gas" % receipt['gasUsed'])

        logs = log_filter.get_new_entries()
        assert len(logs) == 1
        log = logs[0]['args']

        assert log["merkle_tree_index"] == i.to_bytes(8, 'little')

        deposit_data = DepositData(
            pubkey=deposit_input[0],
            withdrawal_credentials=deposit_input[1],
            amount=deposit_amount_list[i],
            signature=deposit_input[2],
        )
        hash_tree_root_result = hash_tree_root(deposit_data)
        leaf_nodes.append(hash_tree_root_result)
        root = compute_merkle_root(leaf_nodes)
        assert root == registration_contract.functions.get_deposit_root().call()


def test_chain_start(modified_registration_contract, w3, assert_tx_failed, deposit_input):
    t = getattr(modified_registration_contract, 'chain_start_full_deposit_threshold')
    # CHAIN_START_FULL_DEPOSIT_THRESHOLD is set to t
    min_deposit_amount = MIN_DEPOSIT_AMOUNT * eth_utils.denoms.gwei  # in wei
    full_deposit_amount = FULL_DEPOSIT_AMOUNT * eth_utils.denoms.gwei
    log_filter = modified_registration_contract.events.Eth2Genesis.createFilter(
        fromBlock='latest',
    )

    index_not_full_deposit = randint(0, t - 1)
    for i in range(t):
        if i == index_not_full_deposit:
            # Deposit with value below FULL_DEPOSIT_AMOUNT
            modified_registration_contract.functions.deposit(
                *deposit_input,
            ).transact({"value": min_deposit_amount})
            logs = log_filter.get_new_entries()
            # Eth2Genesis event should not be triggered
            assert len(logs) == 0
        else:
            # Deposit with value FULL_DEPOSIT_AMOUNT
            modified_registration_contract.functions.deposit(
                *deposit_input,
            ).transact({"value": full_deposit_amount})
            logs = log_filter.get_new_entries()
            # Eth2Genesis event should not be triggered
            assert len(logs) == 0

    # Make 1 more deposit with value FULL_DEPOSIT_AMOUNT to trigger Eth2Genesis event
    modified_registration_contract.functions.deposit(
        *deposit_input,
    ).transact({"value": full_deposit_amount})
    logs = log_filter.get_new_entries()
    assert len(logs) == 1
    timestamp = int(w3.eth.getBlock(w3.eth.blockNumber)['timestamp'])
    timestamp_day_boundary = timestamp + (86400 - timestamp % 86400) + 86400
    log = logs[0]['args']
    assert log['deposit_root'] == modified_registration_contract.functions.get_deposit_root().call()
    assert int.from_bytes(log['time'], byteorder='little') == timestamp_day_boundary
    assert modified_registration_contract.functions.chainStarted().call() is True

    # Make 1 deposit with value FULL_DEPOSIT_AMOUNT and
    # check that Eth2Genesis event is not triggered
    modified_registration_contract.functions.deposit(
        *deposit_input,
    ).transact({"value": full_deposit_amount})
    logs = log_filter.get_new_entries()
    assert len(logs) == 0
