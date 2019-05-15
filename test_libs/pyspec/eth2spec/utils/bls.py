from py_ecc import bls

# Flag to make BLS active or not. Used for testing, do not ignore BLS in production unless you know what you are doing.
bls_active = True


def bls_verify(pubkey, message_hash, signature, domain):
    if bls_active:
        return bls.verify(message_hash=message_hash, pubkey=pubkey, signature=signature, domain=domain)
    else:
        return True


def bls_verify_multiple(pubkeys, message_hashes, signature, domain):
    if bls_active:
        return bls.verify_multiple(pubkeys, message_hashes, signature, domain)
    else:
        return True


def bls_aggregate_pubkeys(pubkeys):
    if bls_active:
        return bls.aggregate_pubkeys(pubkeys)
    else:
        return b'\xaa' * 48


def bls_aggregate_signatures(signatures):
    if bls_active:
        return bls.aggregate_signatures(signatures)
    else:
        return b'\x22' * 96


def bls_sign(message_hash, privkey, domain):
    if bls_active:
        return bls.sign(message_hash=message_hash, privkey=privkey, domain=domain)
    else:
        return b'\x11' * 96
