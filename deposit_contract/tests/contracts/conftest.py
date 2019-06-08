from random import (
    randint,
)
import re

import pytest

import eth_tester
from eth_tester import (
    EthereumTester,
    PyEVMBackend,
)
from vyper import (
    compiler,
)
from web3 import Web3
from web3.providers.eth_tester import (
    EthereumTesterProvider,
)
from .utils import (
    get_deposit_contract_code,
    get_deposit_contract_json,
)


# Constants
MIN_DEPOSIT_AMOUNT = 1000000000  # Gwei
FULL_DEPOSIT_AMOUNT = 32000000000  # Gwei
DEPOSIT_CONTRACT_TREE_DEPTH = 32
TWO_TO_POWER_OF_TREE_DEPTH = 2**DEPOSIT_CONTRACT_TREE_DEPTH


@pytest.fixture
def tester():
    return EthereumTester(PyEVMBackend())


@pytest.fixture
def a0(tester):
    return tester.get_accounts()[0]


@pytest.fixture
def w3(tester):
    web3 = Web3(EthereumTesterProvider(tester))
    return web3


@pytest.fixture
def registration_contract(w3, tester):
    contract_bytecode = get_deposit_contract_json()['bytecode']
    contract_abi = get_deposit_contract_json()['abi']
    registration = w3.eth.contract(
        abi=contract_abi,
        bytecode=contract_bytecode)
    tx_hash = registration.constructor().transact()
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    registration_deployed = w3.eth.contract(
        address=tx_receipt.contractAddress,
        abi=contract_abi
    )
    return registration_deployed


@pytest.fixture(params=[0, 1, 2])
def modified_registration_contract(
        request,
        w3,
        tester):
    registration_code = get_deposit_contract_code()
    contract_bytecode = compiler.compile_code(registration_code)['bytecode']
    contract_abi = compiler.mk_full_signature(registration_code)
    registration = w3.eth.contract(
        abi=contract_abi,
        bytecode=contract_bytecode)
    tx_hash = registration.constructor().transact()
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    registration_deployed = w3.eth.contract(
        address=tx_receipt.contractAddress,
        abi=contract_abi
    )
    return registration_deployed


@pytest.fixture
def assert_tx_failed(tester):
    def assert_tx_failed(function_to_test, exception=eth_tester.exceptions.TransactionFailed):
        snapshot_id = tester.take_snapshot()
        with pytest.raises(exception):
            function_to_test()
        tester.revert_to_snapshot(snapshot_id)
    return assert_tx_failed
