from deposit_contract.contracts.utils import (
    get_deposit_contract_code,
    get_deposit_contract_json,
)
from vyper import (
    compiler,
)


def test_compile_deposit_contract():
    compiled_deposit_contract_json = get_deposit_contract_json()

    deposit_contract_code = get_deposit_contract_code()
    abi = compiler.mk_full_signature(deposit_contract_code)
    bytecode = compiler.compile_code(deposit_contract_code)['bytecode']

    assert abi == compiled_deposit_contract_json["abi"]
    assert bytecode == compiled_deposit_contract_json["bytecode"]
