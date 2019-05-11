from py_ecc import bls


def bls_verify(pubkey, message_hash, signature, domain):
    return bls.verify(message_hash=message_hash, pubkey=pubkey, signature=signature, domain=domain)


def bls_verify_multiple(pubkeys, message_hashes, signature, domain):
    return bls.verify_multiple(pubkeys, message_hashes, signature, domain)


def bls_aggregate_pubkeys(pubkeys):
    return bls.aggregate_pubkeys(pubkeys)
