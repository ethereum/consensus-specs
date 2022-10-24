from eth2spec.utils import bls
from eth2spec.test.helpers.keys import pubkeys, privkeys, pubkey_to_privkey


def get_signed_address_change(spec, state, validator_index=None, withdrawal_pubkey=None):
    if validator_index is None:
        validator_index = 0

    if withdrawal_pubkey is None:
        key_index = -1 - validator_index
        withdrawal_pubkey = pubkeys[key_index]
        withdrawal_privkey = privkeys[key_index]
    else:
        withdrawal_privkey = pubkey_to_privkey[withdrawal_pubkey]

    domain = spec.get_domain(state, spec.DOMAIN_BLS_TO_EXECUTION_CHANGE)
    address_change = spec.BLSToExecutionChange(
        validator_index=validator_index,
        from_bls_withdrawal_pubkey=withdrawal_pubkey,
        to_execution_address=b'\x42' * 20,
    )

    signing_root = spec.compute_signing_root(address_change, domain)
    return spec.SignedBLSToExecutionChange(
        message=address_change,
        signature=bls.Sign(withdrawal_privkey, signing_root),
    )
