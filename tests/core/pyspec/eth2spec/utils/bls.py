import milagro_bls_binding as milagro_bls  # noqa: F401 for BLS switching option
import py_arkworks_bls12381 as arkworks_bls  # noqa: F401 for BLS switching option
from py_arkworks_bls12381 import (
    G1Point as arkworks_G1,
    G2Point as arkworks_G2,
    GT as arkworks_GT,
    Scalar as arkworks_Scalar,
)
from py_ecc.bls import G2ProofOfPossession as py_ecc_bls
from py_ecc.bls.g2_primitives import (  # noqa: F401
    curve_order as BLS_MODULUS,
    G1_to_pubkey as py_ecc_G1_to_bytes48,
    G2_to_signature as py_ecc_G2_to_bytes96,
    pubkey_to_G1 as py_ecc_bytes48_to_G1,
    signature_to_G2 as _signature_to_G2,
    signature_to_G2 as py_ecc_bytes96_to_G2,
)
from py_ecc.optimized_bls12_381 import (  # noqa: F401
    add as py_ecc_add,
    final_exponentiate as py_ecc_final_exponentiate,
    FQ,
    FQ2,
    FQ12 as py_ecc_GT,
    G1 as py_ecc_G1,
    G2 as py_ecc_G2,
    multiply as py_ecc_mul,
    neg as py_ecc_neg,
    pairing as py_ecc_pairing,
    Z1 as py_ecc_Z1,
    Z2 as py_ecc_Z2,
)
from py_ecc.utils import prime_field_inv as py_ecc_prime_field_inv


class py_ecc_Scalar(FQ):
    field_modulus = BLS_MODULUS

    def __init__(self, value):
        """
        Force underlying value to be a native integer.
        """
        super().__init__(int(value))

    def pow(self, exp):
        """
        Raises the self to the power of the given exponent.
        """
        return self ** int(exp)

    def inverse(self):
        """
        Computes the modular inverse of self.
        """
        return py_ecc_Scalar(py_ecc_prime_field_inv(self.n, self.field_modulus))


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
Scalar = fastest_bls.Scalar

STUB_SIGNATURE = b"\x11" * 96
STUB_PUBKEY = b"\x22" * 48
G2_POINT_AT_INFINITY = b"\xc0" + b"\x00" * 95
STUB_COORDINATES = _signature_to_G2(G2_POINT_AT_INFINITY)


def use_milagro():
    """
    Shortcut to use Milagro as BLS library
    """
    global bls
    bls = milagro_bls
    global Scalar
    Scalar = py_ecc_Scalar


def use_arkworks():
    """
    Shortcut to use Arkworks as BLS library
    """
    global bls
    bls = arkworks_bls
    global Scalar
    Scalar = arkworks_Scalar


def use_py_ecc():
    """
    Shortcut to use Py-ecc as BLS library
    """
    global bls
    bls = py_ecc_bls
    global Scalar
    Scalar = py_ecc_Scalar


def use_fastest():
    """
    Shortcut to use Milagro for signatures and Arkworks for other BLS operations
    """
    global bls
    bls = fastest_bls
    global Scalar
    Scalar = fastest_bls.Scalar


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
        return bls.Sign(SK.to_bytes(32, "big"), message)


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
        return bls.SkToPk(SK.to_bytes(32, "big"))


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
        if not isinstance(scalar, arkworks_Scalar):
            return point * arkworks_Scalar(int(scalar))
        return point * scalar
    return py_ecc_mul(point, int(scalar))


def multi_exp(points, scalars):
    """
    Performs a multi-scalar multiplication between
    `points` and `scalars`.
    `points` can either be in G1 or G2.
    """
    # Since this method accepts either G1 or G2, we need to know
    # the type of the point to return. Hence, we need at least one point.
    if not points or not scalars:
        raise Exception("Cannot call multi_exp with zero points or zero scalars")

    if bls == arkworks_bls or bls == fastest_bls:
        # If using py_ecc Scalars, convert to arkworks Scalars.
        if not isinstance(scalars[0], arkworks_Scalar):
            scalars = [arkworks_Scalar(int(s)) for s in scalars]

        # Check if we need to perform a G1 or G2 multiexp
        if isinstance(points[0], arkworks_G1):
            return arkworks_G1.multiexp_unchecked(points, scalars)
        elif isinstance(points[0], arkworks_G2):
            return arkworks_G2.multiexp_unchecked(points, scalars)
        else:
            raise Exception("Invalid point type")

    result = None
    if isinstance(points[0][0], FQ):
        result = Z1()
    elif isinstance(points[0][0], FQ2):
        result = Z2()
    else:
        raise Exception("Invalid point type")

    for point, scalar in zip(points, scalars):
        result = add(result, multiply(point, scalar))
    return result


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


def Z2():
    """
    Returns the identity point in G2
    """
    if bls == arkworks_bls or bls == fastest_bls:
        return arkworks_G2.identity()
    return py_ecc_Z2


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
