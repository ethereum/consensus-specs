import json
import os

DIR = os.path.dirname(__file__)


def get_deposit_contract_code():
    file_path = os.path.join(DIR, './validator_registration.v.py')
    deposit_contract_code = open(file_path).read()
    return deposit_contract_code


def get_deposit_contract_json():
    file_path = os.path.join(DIR, './validator_registration.json')
    deposit_contract_json = open(file_path).read()
    return json.loads(deposit_contract_json)
