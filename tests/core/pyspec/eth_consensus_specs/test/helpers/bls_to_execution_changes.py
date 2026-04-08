from eth_consensus_specs.test.helpers.keys import privkeys, pubkey_to_privkey, pubkeys
from eth_consensus_specs.utils import bls


def get_signed_address_change(
    spec,
    state,
    validator_index=None,
    withdrawal_pubkey=None,
    to_execution_address=None,
    fork_version=None,
    genesis_validators_root=None,
):
    if validator_index is None:
        validator_index = 0

    if withdrawal_pubkey is None:
        key_index = -1 - validator_index
        withdrawal_pubkey = pubkeys[key_index]
        withdrawal_privkey = privkeys[key_index]
    else:
        withdrawal_privkey = pubkey_to_privkey[withdrawal_pubkey]

    if to_execution_address is None:
        to_execution_address = b"\x42" * 20

    if genesis_validators_root is None:
        genesis_validators_root = state.genesis_validators_root

    domain = spec.compute_domain(
        spec.DOMAIN_BLS_TO_EXECUTION_CHANGE,
        fork_version=fork_version,
        genesis_validators_root=genesis_validators_root,
    )

    address_change = spec.BLSToExecutionChange(
        validator_index=validator_index,
        from_bls_pubkey=withdrawal_pubkey,
        to_execution_address=to_execution_address,
    )

    signing_root = spec.compute_signing_root(address_change, domain)
    return spec.SignedBLSToExecutionChange(
        message=address_change,
        signature=bls.Sign(withdrawal_privkey, signing_root),
    )
