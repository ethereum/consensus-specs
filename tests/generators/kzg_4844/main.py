"""
KZG 4844 test vectors generator
"""

from hashlib import sha256
from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import (
    encode_hex,
    int_to_big_endian,
)
import milagro_bls_binding as milagro_bls

from eth2spec.utils import bls
from eth2spec.test.helpers.constants import PHASE0, ALTAIR, DENEB
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.deneb import spec




def expect_exception(func, *args):
    try:
        func(*args)
    except Exception:
        pass
    else:
        raise Exception("should have raised exception")

def field_element_bytes(x):
    return int.to_bytes(x % spec.BLS_MODULUS, 32, "little")

BLOB_ALL_ZEROS = spec.Blob()
BLOB_RANDOM_VALID = spec.Blob(b''.join([field_element_bytes((2^128 - 1) * n) for n in range(4096)]))
BLOB_INVALID = spec.Blob(b'\xFF' * 4096 * 32)

VALID_BLOBS = [BLOB_ALL_ZEROS, BLOB_RANDOM_VALID]
INVALID_BLOBS = [BLOB_INVALID]
VALID_ZS = [x.to_bytes(32, spec.ENDIANNESS) for x in [0, 1, 15, 2**150 - 1, spec.BLS_MODULUS - 1]]
INVALID_ZS = [x.to_bytes(32, spec.ENDIANNESS) for x in [spec.BLS_MODULUS, 2**256 - 1]]

def hash(x):
    return sha256(x).digest()

def int_to_hex(n: int, byte_length: int = None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b'\x00')
    return encode_hex(byte_value)

def case01_compute_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        for z in VALID_ZS:
            proof = spec.compute_kzg_proof(blob, z)
            identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}'
            yield f'compute_kzg_proof_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'blob': encode_hex(blob),
                    'z': encode_hex(z),
                },
                'output': encode_hex(proof)
            }
    # Edge case: Invalid blob
    expect_exception(spec.compute_kzg_proof, BLOB_INVALID, 0)
    yield 'compute_kzg_proof_case_invalid_blob', {
        'input': {
            'blob': encode_hex(BLOB_INVALID),
            'z': encode_hex(VALID_ZS[0]),
        },
        'output': None
    }
    # Edge case: Invalid z
    expect_exception(spec.compute_kzg_proof, BLOB_ALL_ZEROS, INVALID_ZS[0])
    yield 'compute_kzg_proof_case_invalid_z', {
        'input': {
            'blob': encode_hex(BLOB_ALL_ZEROS),
            'z': encode_hex(INVALID_ZS[0]),
        },
        'output': None
    }

def create_provider(fork_name: SpecForkName,
                    handler_name: str,
                    test_case_fn: Callable[[], Iterable[Tuple[str, Dict[str, Any]]]]) -> gen_typing.TestProvider:

    def prepare_fn() -> None:
        # Nothing to load / change in spec. Maybe in future forks.
        # Put the tests into the general config category, to not require any particular configuration.
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for data in test_case_fn():
            (case_name, case_content) = data
            yield gen_typing.TestCase(
                fork_name=fork_name,
                preset_name='general',
                runner_name='bls',
                handler_name=handler_name,
                suite_name='small',
                case_name=case_name,
                case_fn=lambda: [('data', 'data', case_content)]
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)

if __name__ == "__main__":
    bls.use_arkworks()  
    gen_runner.run_generator("bls", [
        # PHASE0
        create_provider(PHASE0, 'compute_kzg_proof', case01_compute_kzg_proof),
    ])