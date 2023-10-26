from py_ecc.bls import G2ProofOfPossession as py_ecc_bls
from py_ecc.bls.g2_primatives import signature_to_G2 as _signature_to_G2
from py_ecc.optimized_bls12_381 import (  # noqa: F401
    G1 as py_ecc_G1,
    G2 as py_ecc_G2,
    Z1 as py_ecc_Z1,
    add as py_ecc_add,
    multiply as py_ecc_mul,
    neg as py_ecc_neg,
    pairing as py_ecc_pairing,
    final_exponentiate as py_ecc_final_exponentiate,
    FQ12 as py_ecc_GT,
)
from py_ecc.bls.g2_primitives import (  # noqa: F401
    curve_order as BLS_MODULUS,
    G1_to_pubkey as py_ecc_G1_to_bytes48,
    pubkey_to_G1 as py_ecc_bytes48_to_G1,
    G2_to_signature as py_ecc_G2_to_bytes96,
    signature_to_G2 as py_ecc_bytes96_to_G2,
)
from py_arkworks_bls12381 import (
    G1Point as arkworks_G1,
    G2Point as arkworks_G2,
    Scalar as arkworks_Scalar,
    GT as arkworks_GT,
)


import milagro_bls_binding as milagro_bls  # noqa: F401 for BLS switching option

import py_arkworks_bls12381 as arkworks_bls  # noqa: F401 for BLS switching option


class fastest_bls:
    G1 = arkworks_G1
    G2 = arkworks_G2
    Scalar = arkworks_Scalar
    GT = arkworks_GT
    _AggregatePKs = milagro_bls._AggregatePKs
    Sign = milagro_bls.Sign
    Verify = milagro_bls.Verify
    Aggregate = milagro_bls.Aggregate
    AggregateVerify = milagro_bls.AggregateVerify
    FastAggregateVerify = milagro_bls.FastAggregateVerify
    SkToPk = milagro_bls.SkToPk


# Flag to make BLS active or not. Used for testing, do not ignore BLS in production unless you know what you are doing.
bls_active = True

# Default to fastest_bls
bls = fastest_bls

STUB_SIGNATURE = b'\x11' * 96
STUB_PUBKEY = b'\x22' * 48
G2_POINT_AT_INFINITY = b'\xc0' + b'\x00' * 95
STUB_COORDINATES = _signature_to_G2(G2_POINT_AT_INFINITY)


def use_milagro():
    """
    Shortcut to use Milagro as BLS library
    """
    global bls
    bls = milagro_bls


def use_arkworks():
    """
    Shortcut to use Arkworks as BLS library
    """
    global bls
    bls = arkworks_bls


def use_py_ecc():
    """
    Shortcut to use Py-ecc as BLS library
    """
    global bls
    bls = py_ecc_bls


def use_fastest():
    """
    Shortcut to use Milagro for signatures and Arkworks for other BLS operations
    """
    global bls
    bls = fastest_bls


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
    try:
        if bls == arkworks_bls:  # no signature API in arkworks
            result = py_ecc_bls.Verify(PK, message, signature)
        else:
            result = bls.Verify(PK, message, signature)
    except Exception:
        result = False
    finally:
        return result


@only_with_bls(alt_return=True)
def AggregateVerify(pubkeys, messages, signature):
    try:
        if bls == arkworks_bls:  # no signature API in arkworks
            result = py_ecc_bls.AggregateVerify(list(pubkeys), list(messages), signature)
        else:
            result = bls.AggregateVerify(list(pubkeys), list(messages), signature)
    except Exception:
        result = False
    finally:
        return result


@only_with_bls(alt_return=True)
def FastAggregateVerify(pubkeys, message, signature):
    try:
        if bls == arkworks_bls:  # no signature API in arkworks
            result = py_ecc_bls.FastAggregateVerify(list(pubkeys), message, signature)
        else:
            result = bls.FastAggregateVerify(list(pubkeys), message, signature)
    except Exception:
        result = False
    finally:
        return result


@only_with_bls(alt_return=STUB_SIGNATURE)
def Aggregate(signatures):
    if bls == arkworks_bls:  # no signature API in arkworks
        return py_ecc_bls.Aggregate(signatures)
    return bls.Aggregate(signatures)


@only_with_bls(alt_return=STUB_SIGNATURE)
def Sign(SK, message):
    if bls == arkworks_bls:  # no signature API in arkworks
        return py_ecc_bls.Sign(SK, message)
    elif bls == py_ecc_bls:
        return bls.Sign(SK, message)
    else:
        return bls.Sign(SK.to_bytes(32, 'big'), message)


@only_with_bls(alt_return=STUB_COORDINATES)
def signature_to_G2(signature):
    return _signature_to_G2(signature)


@only_with_bls(alt_return=STUB_PUBKEY)
def AggregatePKs(pubkeys):
    if bls == py_ecc_bls:
        assert all(bls.KeyValidate(pubkey) for pubkey in pubkeys)
    elif bls == milagro_bls:
        # milagro_bls._AggregatePKs checks KeyValidate internally
        pass

    if bls == arkworks_bls:  # no signature API in arkworks
        return py_ecc_bls._AggregatePKs(list(pubkeys))

    return bls._AggregatePKs(list(pubkeys))


@only_with_bls(alt_return=STUB_SIGNATURE)
def SkToPk(SK):
    if bls == py_ecc_bls or bls == arkworks_bls:  # no signature API in arkworks
        return py_ecc_bls.SkToPk(SK)
    else:
        return bls.SkToPk(SK.to_bytes(32, 'big'))


def pairing_check(values):
    if bls == arkworks_bls or bls == fastest_bls:
        p_q_1, p_q_2 = values
        g1s = [p_q_1[0], p_q_2[0]]
        g2s = [p_q_1[1], p_q_2[1]]
        return arkworks_GT.multi_pairing(g1s, g2s) == arkworks_GT.one()
    else:
        p_q_1, p_q_2 = values
        final_exponentiation = py_ecc_final_exponentiate(
            py_ecc_pairing(p_q_1[1], p_q_1[0], final_exponentiate=False)
            * py_ecc_pairing(p_q_2[1], p_q_2[0], final_exponentiate=False)
        )
        return final_exponentiation == py_ecc_GT.one()


def add(lhs, rhs):
    """
    Performs point addition of `lhs` and `rhs`.
    The points can either be in G1 or G2.
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return lhs + rhs
    return py_ecc_add(lhs, rhs)


def multiply(point, scalar):
    """
    Performs Scalar multiplication between
    `point` and `scalar`.
    `point` can either be in G1 or G2
    """
    if bls == arkworks_bls or bls == fastest_bls:
        int_as_bytes = scalar.to_bytes(32, 'little')
        scalar = arkworks_Scalar.from_le_bytes(int_as_bytes)
        return point * scalar
    return py_ecc_mul(point, scalar)


def neg(point):
    """
    Returns the point negation of `point`
    `point` can either be in G1 or G2
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return -point
    return py_ecc_neg(point)


def Z1():
    """
    Returns the identity point in G1
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return arkworks_G1.identity()
    return py_ecc_Z1


def G1():
    """
    Returns the chosen generator point in G1
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return arkworks_G1()
    return py_ecc_G1


def G2():
    """
    Returns the chosen generator point in G2
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return arkworks_G2()
    return py_ecc_G2


def G1_to_bytes48(point):
    """
    Serializes a point in G1.
    Returns a bytearray of size 48 as
    we use the compressed format
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return bytes(point.to_compressed_bytes())
    return py_ecc_G1_to_bytes48(point)


def G2_to_bytes96(point):
    """
    Serializes a point in G2.
    Returns a bytearray of size 96 as
    we use the compressed format
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return bytes(point.to_compressed_bytes())
    return py_ecc_G2_to_bytes96(point)


def bytes48_to_G1(bytes48):
    """
    Deserializes a purported compressed serialized
    point in G1.
        - No subgroup checks are performed
        - If the bytearray is not a valid serialization
        of a point in G1, then this method will raise
        an exception
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return arkworks_G1.from_compressed_bytes_unchecked(bytes48)
    return py_ecc_bytes48_to_G1(bytes48)


def bytes96_to_G2(bytes96):
    """
    Deserializes a purported compressed serialized
    point in G2.
        - No subgroup checks are performed
        - If the bytearray is not a valid serialization
        of a point in G2, then this method will raise
        an exception
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return arkworks_G2.from_compressed_bytes_unchecked(bytes96)
    return py_ecc_bytes96_to_G2(bytes96)


@only_with_bls(alt_return=True)
def KeyValidate(pubkey):
    return py_ecc_bls.KeyValidate(pubkey)
