from eth2spec.utils import bls
from eth2spec.test.helpers.keys import pubkeys, privkeys, pubkey_to_privkey


def get_signed_pubkey_change(spec, state, validator_index=None, withdrawal_pubkey=None):
    if validator_index is None:
        validator_index = 0

    if withdrawal_pubkey is None:
        key_index = -1 - validator_index
        withdrawal_pubkey = pubkeys[key_index]
        withdrawal_privkey = privkeys[key_index]
    else:
        withdrawal_privkey = pubkey_to_privkey[withdrawal_pubkey]

    pubkey_change_epoch = spec.get_current_epoch(state) + spec.Epoch(1)

    # HACK: Get this from somewhere properly
    new_pubkey = pubkeys[50]

    domain = spec.get_domain(state, spec.DOMAIN_PUBKEY_CHANGE)
    pubkey_change = spec.PubKeyChange(
        validator_index=validator_index,
        from_bls_pubkey=withdrawal_pubkey,
        new_pubkey=new_pubkey,
        epoch=pubkey_change_epoch
    )

    signing_root = spec.compute_signing_root(pubkey_change, domain)
    return spec.SignedPubKeyChange(
        message=pubkey_change,
        signature=bls.Sign(withdrawal_privkey, signing_root),
    )
