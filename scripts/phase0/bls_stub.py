

def bls_verify(pubkey, message_hash, signature, domain):
    return True


def bls_verify_multiple(pubkeys, message_hashes, signature, domain):
    return True


def bls_aggregate_pubkeys(pubkeys):
    return b'\x42'*96
