# Ref:
# - https://github.com/ethereum/research/blob/8f084630528ba33d92b2bc05edf5338dd193c6f1/trusted_setup/trusted_setup.py
# - https://github.com/asn-d6/kzgverify
import json
import os
from typing import (
    Tuple,
    Sequence,
)
from pathlib import Path

from eth_utils import encode_hex
from py_ecc.optimized_bls12_381 import (  # noqa: F401
    G1,
    G2,
    Z1,
    Z2,
    curve_order as BLS_MODULUS,
    add,
    multiply,
    neg,
)
from py_ecc.typing import (
    Optimized_Point3D,
)
from eth2spec.utils import bls


PRIMITIVE_ROOT_OF_UNITY = 7


def generate_setup(generator: Optimized_Point3D, secret: int, length: int) -> Tuple[Optimized_Point3D]:
    """
    Generate trusted setup of ``generator`` in ``length``.
    """
    result = [generator]
    for _ in range(1, length):
        result.append(multiply(result[-1], secret))
    return tuple(result)


def fft(vals: Sequence[Optimized_Point3D], modulus: int, domain: int) -> Sequence[Optimized_Point3D]:
    """
    FFT for group elements
    """
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


def compute_root_of_unity(length: int) -> int:
    """
    Generate a w such that ``w**length = 1``.
    """
    assert (BLS_MODULUS - 1) % length == 0
    return pow(PRIMITIVE_ROOT_OF_UNITY, (BLS_MODULUS - 1) // length, BLS_MODULUS)


def compute_roots_of_unity(field_elements_per_blob: int) -> Tuple[int]:
    """
    Compute a list of roots of unity for a given order.
    The order must divide the BLS multiplicative group order, i.e. BLS_MODULUS - 1
    """
    field_elements_per_blob = int(field_elements_per_blob)  # to non-SSZ int
    assert (BLS_MODULUS - 1) % field_elements_per_blob == 0
    root_of_unity = compute_root_of_unity(length=field_elements_per_blob)

    roots = []
    current_root_of_unity = 1
    for _ in range(field_elements_per_blob):
        roots.append(current_root_of_unity)
        current_root_of_unity = current_root_of_unity * root_of_unity % BLS_MODULUS
    return tuple(roots)


def get_lagrange(setup: Sequence[Optimized_Point3D]) -> Tuple[bytes]:
    """
    Convert a G1 or G2 portion of a setup into the Lagrange basis.
    """
    root_of_unity = compute_root_of_unity(len(setup))
    assert pow(root_of_unity, len(setup), BLS_MODULUS) == 1
    domain = [pow(root_of_unity, i, BLS_MODULUS) for i in range(len(setup))]
    # TODO: introduce an IFFT function for simplicity
    fft_output = fft(setup, BLS_MODULUS, domain)
    inv_length = pow(len(setup), BLS_MODULUS - 2, BLS_MODULUS)
    return tuple(bls.G1_to_bytes48(multiply(fft_output[-i], inv_length)) for i in range(len(fft_output)))


def dump_kzg_trusted_setup_files(secret: int, length: int, output_dir: str) -> None:
    setup_g1 = generate_setup(bls.G1, secret, length)
    setup_g2 = generate_setup(bls.G2, secret, length)
    setup_g1_lagrange = get_lagrange(setup_g1)
    roots_of_unity = compute_roots_of_unity(length)

    serailized_setup_g1 = [encode_hex(bls.G1_to_bytes48(p)) for p in setup_g1]
    serialized_setup_g2 = [encode_hex(bls.G2_to_bytes96(p)) for p in setup_g2]
    serialized_setup_g1_lagrange = [encode_hex(x) for x in setup_g1_lagrange]

    output_dir_path = Path(output_dir)

    if not os.path.exists(output_dir_path):
        os.makedirs(output_dir_path)
        print("Created directory: ", output_dir_path)

    file_path = output_dir_path / 'testing_trusted_setups.json'

    with open(file_path, 'w+') as f:
        json.dump(
            {
                "setup_G1": serailized_setup_g1,
                "setup_G2": serialized_setup_g2,
                "setup_G1_lagrange": serialized_setup_g1_lagrange,
                "roots_of_unity": roots_of_unity,
            }, f)

    print(f'Generated trusted setup file: {file_path}\n')
