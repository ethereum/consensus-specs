# Ref: https://github.com/ethereum/research/blob/8f084630528ba33d92b2bc05edf5338dd193c6f1/trusted_setup/trusted_setup.py

from py_ecc.optimized_bls12_381 import (  # noqa: F401
    G1,
    G2,
    Z1,
    Z2,
    curve_order,
    field_modulus as FIELD_MODULUS,
    add,
    multiply,
    neg,
)


PRIMITIVE_ROOT_OF_UNITY = 7


def generate_setup(generator, secret, length):
    """
    Generate trusted setup of ``generator`` in ``length``.
    """
    result = [generator]
    for _ in range(1, length):
        result.append(multiply(result[-1], secret))
    return tuple(result)


def fft(vals, modulus, domain):
    if len(vals) == 1:
        return vals
    L = fft(vals[::2], modulus, domain[::2])
    R = fft(vals[1::2], modulus, domain[::2])
    o = [0] * len(vals)
    for i, (x, y) in enumerate(zip(L, R)):
        y_times_root = multiply(y, domain[i])
        o[i] = add(x, y_times_root)
        o[i + len(L)] = add(x, neg(y_times_root))
    return o


def generate_root_of_unity(length) -> int:
    """
    Generate a w such that ``w**length = 1``.
    """
    assert (curve_order - 1) % length == 0
    return pow(PRIMITIVE_ROOT_OF_UNITY, (curve_order - 1) // length, curve_order)


def get_lagrange(setup):
    """
    Convert a G1 or G2 portion of a setup into the Lagrange basis.
    """
    root_of_unity = generate_root_of_unity(len(setup))
    assert pow(root_of_unity, len(setup), curve_order) == 1
    domain = [pow(root_of_unity, i, curve_order) for i in range(len(setup))]
    fft_output = fft(setup, curve_order, domain)
    inv_length = pow(len(setup), curve_order - 2, curve_order)
    return [multiply(fft_output[-i], inv_length) for i in range(len(fft_output))]
