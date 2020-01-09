from py_ecc.bls import G2ProofOfPossession as bls
from py_ecc.bls.g2_primatives import signature_to_G2 as _signature_to_G2

# Flag to make BLS active or not. Used for testing, do not ignore BLS in production unless you know what you are doing.
bls_active = True

STUB_SIGNATURE = b'\x11' * 96
STUB_PUBKEY = b'\x22' * 48
STUB_COORDINATES = _signature_to_G2(bls.Sign(0, b""))


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
def Verify(PK, message, signature):
    return bls.Verify(PK, message, signature)


@only_with_bls(alt_return=True)
def AggregateVerify(pairs, signature):
    return bls.AggregateVerify(pairs, signature)


@only_with_bls(alt_return=True)
def FastAggregateVerify(PKs, message, signature):
    return bls.FastAggregateVerify(PKs, message, signature)


@only_with_bls(alt_return=STUB_SIGNATURE)
def Aggregate(signatures):
    return bls.Aggregate(signatures)


@only_with_bls(alt_return=STUB_SIGNATURE)
def Sign(SK, message):
    return bls.Sign(SK, message)


@only_with_bls(alt_return=STUB_COORDINATES)
def signature_to_G2(signature):
    return _signature_to_G2(signature)
