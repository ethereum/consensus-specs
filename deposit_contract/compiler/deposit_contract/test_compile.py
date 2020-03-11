from vyper import compiler

import json
import os

DIR = os.path.dirname(__file__)


def get_deposit_contract_code():
    file_path = os.path.join(DIR, '../../contracts/validator_registration.vy')
    deposit_contract_code = open(file_path).read()
    return deposit_contract_code


def get_deposit_contract_json():
    file_path = os.path.join(DIR, '../../contracts/validator_registration.json')
    deposit_contract_json = open(file_path).read()
    return json.loads(deposit_contract_json)


def test_compile_deposit_contract():
    compiled_deposit_contract_json = get_deposit_contract_json()

    deposit_contract_code = get_deposit_contract_code()
    abi = compiler.mk_full_signature(deposit_contract_code)
    bytecode = compiler.compile_code(deposit_contract_code)['bytecode']

    assert abi == compiled_deposit_contract_json["abi"]
    assert bytecode == compiled_deposit_contract_json["bytecode"]
