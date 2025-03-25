from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
)


def prepare_switch_to_compounding_request(spec, state, validator_index, address=None):
    validator = state.validators[validator_index]
    if not spec.has_execution_withdrawal_credential(validator):
        set_eth1_withdrawal_credential_with_balance(
            spec, state, validator_index, address=address
        )

    return spec.ConsolidationRequest(
        source_address=state.validators[validator_index].withdrawal_credentials[12:],
        source_pubkey=state.validators[validator_index].pubkey,
        target_pubkey=state.validators[validator_index].pubkey,
    )
