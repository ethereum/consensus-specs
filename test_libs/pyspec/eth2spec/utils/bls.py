from py_ecc import bls

# Flag to make BLS active or not. Used for testing, do not ignore BLS in production unless you know what you are doing.
bls_active = True

STUB_SIGNATURE = b'\x11' * 96
STUB_PUBKEY = b'\x22' * 48
STUB_COORDINATES = bls.api.signature_to_G2(bls.sign(b"", 0, b"\0" * 8))


def only_with_bls(alt_return=None):
    """
    Decorator factory to make a function only run when BLS is active. Otherwise return the default.
    """
    def runner(fn):
        def entry(*args, **kw):
            if bls_active:
                return fn(*args, **kw)
            else:
                return alt_return
        return entry
    return runner


@only_with_bls(alt_return=True)
def bls_verify(pubkey, message_hash, signature, domain):
    return bls.verify(message_hash=message_hash, pubkey=pubkey,
                      signature=signature, domain=domain)


@only_with_bls(alt_return=True)
def bls_verify_multiple(pubkeys, message_hashes, signature, domain):
    return bls.verify_multiple(pubkeys=pubkeys, message_hashes=message_hashes,
                               signature=signature, domain=domain)


@only_with_bls(alt_return=STUB_PUBKEY)
def bls_aggregate_pubkeys(pubkeys):
    return bls.aggregate_pubkeys(pubkeys)


@only_with_bls(alt_return=STUB_SIGNATURE)
def bls_aggregate_signatures(signatures):
    return bls.aggregate_signatures(signatures)


@only_with_bls(alt_return=STUB_SIGNATURE)
def bls_sign(message_hash, privkey, domain):
    return bls.sign(message_hash=message_hash, privkey=privkey,
                    domain=domain)


@only_with_bls(alt_return=STUB_COORDINATES)
def bls_signature_to_G2(signature):
    return bls.api.signature_to_G2(signature)
