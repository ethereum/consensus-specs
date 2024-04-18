"""
KZG PeerDAS test vectors generator
"""

from hashlib import sha256
from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import encode_hex

from eth2spec.utils import bls
from eth2spec.test.helpers.constants import EIP7594
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.eip7594 import spec


###############################################################################
# Helper functions
###############################################################################

def expect_exception(func, *args):
    try:
        func(*args)
    except Exception:
        pass
    else:
        raise Exception("should have raised exception")


def bls_add_one(x):
    """
    Adds "one" (actually bls.G1()) to a compressed group element.
    Useful to compute definitely incorrect proofs.
    """
    return bls.G1_to_bytes48(
        bls.add(bls.bytes48_to_G1(x), bls.G1())
    )


def hash(x):
    return sha256(x).digest()


def make_id(*args):
    values_str = "_".join(str(arg) for arg in args)
    return hash(bytes(values_str, "utf-8"))[:8].hex()


def field_element_bytes(x):
    return int.to_bytes(x % spec.BLS_MODULUS, 32, spec.KZG_ENDIANNESS)


def field_element_bytes_unchecked(x):
    return int.to_bytes(x, 32, spec.KZG_ENDIANNESS)


def encode_hex_list(a):
    return [encode_hex(x) for x in a]


def cell_to_cell_bytes(cell):
    result = []
    for field in cell:
        byte_value = field_element_bytes_unchecked(field)
        result.append(byte_value)
    return result


def cells_to_cells_bytes(cells):
    result = []
    for cell in cells:
        result.append(cell_to_cell_bytes(cell))
    return result


def encode_hex_cell_bytes(cell_bytes):
    result = []
    for field_bytes in cell_bytes:
        result.append(field_bytes)
    return "0x" + b"".join(result).hex()


def encode_hex_cells_bytes(cells_bytes):
    result = []
    for cell_bytes in cells_bytes:
        result.append(encode_hex_cell_bytes(cell_bytes))
    return result


def encode_hex_bls_field_list(fields):
    result = []
    for field in fields:
        result.append(encode_hex(field_element_bytes_unchecked(field)))
    return result


###############################################################################
# Global variables
###############################################################################

BLS_MODULUS_BYTES = spec.BLS_MODULUS.to_bytes(32, spec.KZG_ENDIANNESS)

# Blobs

BLOB_ALL_ZEROS = spec.Blob()
BLOB_ALL_TWOS = spec.Blob(b''.join([field_element_bytes(2) for n in range(4096)]))
BLOB_RANDOM_VALID1 = spec.Blob(b''.join([field_element_bytes(pow(2, n + 256, spec.BLS_MODULUS)) for n in range(4096)]))
BLOB_RANDOM_VALID2 = spec.Blob(b''.join([field_element_bytes(pow(3, n + 256, spec.BLS_MODULUS)) for n in range(4096)]))
BLOB_RANDOM_VALID3 = spec.Blob(b''.join([field_element_bytes(pow(5, n + 256, spec.BLS_MODULUS)) for n in range(4096)]))
BLOB_ALL_MODULUS_MINUS_ONE = spec.Blob(b''.join([field_element_bytes(spec.BLS_MODULUS - 1) for n in range(4096)]))
BLOB_ALMOST_ZERO = spec.Blob(b''.join([field_element_bytes(1 if n == 3211 else 0) for n in range(4096)]))

BLOB_INVALID = spec.Blob(b'\xFF' * 4096 * 32)
BLOB_INVALID_CLOSE = spec.Blob(b''.join(
    [BLS_MODULUS_BYTES if n == 2111 else field_element_bytes(0) for n in range(4096)]
))
BLOB_INVALID_LENGTH_PLUS_ONE = BLOB_RANDOM_VALID1 + b"\x00"
BLOB_INVALID_LENGTH_MINUS_ONE = BLOB_RANDOM_VALID1[:-1]

VALID_BLOBS = [BLOB_ALL_ZEROS, BLOB_ALL_TWOS, BLOB_RANDOM_VALID1, BLOB_RANDOM_VALID2,
               BLOB_RANDOM_VALID3, BLOB_ALL_MODULUS_MINUS_ONE, BLOB_ALMOST_ZERO]
INVALID_BLOBS = [BLOB_INVALID, BLOB_INVALID_CLOSE, BLOB_INVALID_LENGTH_PLUS_ONE, BLOB_INVALID_LENGTH_MINUS_ONE]

# Individual Cells

CELL_RANDOM_VALID1 = [field_element_bytes(pow(2, n + 256, spec.BLS_MODULUS))
                      for n in range(spec.FIELD_ELEMENTS_PER_CELL)]
CELL_RANDOM_VALID2 = [field_element_bytes(pow(3, n + 256, spec.BLS_MODULUS))
                      for n in range(spec.FIELD_ELEMENTS_PER_CELL)]
CELL_RANDOM_VALID3 = [field_element_bytes(pow(5, n + 256, spec.BLS_MODULUS))
                      for n in range(spec.FIELD_ELEMENTS_PER_CELL)]

CELL_ALL_MAX_VALUE = [field_element_bytes_unchecked(2 ** 256 - 1) for n in range(spec.FIELD_ELEMENTS_PER_CELL)]
CELL_ONE_INVALID_FIELD = [field_element_bytes_unchecked(spec.BLS_MODULUS) if n == 7 else field_element_bytes(0) for n in
                          range(spec.FIELD_ELEMENTS_PER_CELL)]

VALID_INDIVIDUAL_RANDOM_CELL_BYTES = [CELL_RANDOM_VALID1, CELL_RANDOM_VALID2, CELL_RANDOM_VALID3]
INVALID_INDIVIDUAL_CELL_BYTES = [CELL_ALL_MAX_VALUE, CELL_ONE_INVALID_FIELD]

# Cells & Proofs

VALID_CELLS_AND_PROOFS = []  # Saved in case02_compute_cells_and_proofs
VALID_COMMITMENTS = [spec.blob_to_kzg_commitment(blob) for blob in VALID_BLOBS]

# Points

G1 = bls.G1_to_bytes48(bls.G1())
G1_INVALID_TOO_FEW_BYTES = G1[:-1]
G1_INVALID_TOO_MANY_BYTES = G1 + b"\x00"
G1_INVALID_P1_NOT_IN_G1 = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                        "0123456789abcdef0123456789abcdef0123456789abcdef")
G1_INVALID_P1_NOT_ON_CURVE = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                           "0123456789abcdef0123456789abcdef0123456789abcde0")
INVALID_G1_POINTS = [G1_INVALID_TOO_FEW_BYTES, G1_INVALID_TOO_MANY_BYTES,
                     G1_INVALID_P1_NOT_IN_G1, G1_INVALID_P1_NOT_ON_CURVE]


###############################################################################
# Test cases for compute_cells
###############################################################################

def case01_compute_cells():
    # Valid cases
    for blob in VALID_BLOBS:
        cells = spec.compute_cells(blob)
        identifier = make_id(blob)
        yield f'compute_cells_case_valid_{identifier}', {
            'input': {
                'blob': encode_hex(blob),
            },
            'output': encode_hex_cells_bytes(cells_to_cells_bytes(cells))
        }

    # Edge case: Invalid blobs
    for blob in INVALID_BLOBS:
        expect_exception(spec.compute_cells, blob)
        identifier = make_id(blob)
        yield f'compute_cells_case_invalid_blob_{identifier}', {
            'input': {
                'blob': encode_hex(blob)
            },
            'output': None
        }


###############################################################################
# Test cases for compute_cells_and_proofs
###############################################################################

def case02_compute_cells_and_proofs():
    # Valid cases
    for blob in VALID_BLOBS:
        cells, proofs = spec.compute_cells_and_proofs(blob)
        # Save cells & proofs here to save on time.
        VALID_CELLS_AND_PROOFS.append((cells, proofs))
        identifier = make_id(blob)
        yield f'compute_cells_and_proofs_case_valid_{identifier}', {
            'input': {
                'blob': encode_hex(blob),
            },
            'output': (encode_hex_cells_bytes(cells_to_cells_bytes(cells)), encode_hex_list(proofs))
        }

    # Edge case: Invalid blobs
    for blob in INVALID_BLOBS:
        expect_exception(spec.compute_cells_and_proofs, blob)
        identifier = make_id(blob)
        yield f'compute_cells_and_proofs_case_invalid_blob_{identifier}', {
            'input': {
                'blob': encode_hex(blob)
            },
            'output': None
        }


###############################################################################
# Test cases for verify_cell_proof
###############################################################################

def case03_verify_cell_proof():
    # Valid cases
    for i in range(len(VALID_BLOBS)):
        commitment = VALID_COMMITMENTS[i]
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        cell_id = (2 ** i - 1) % spec.CELLS_PER_BLOB
        cell_bytes = cell_to_cell_bytes(cells[cell_id])
        proof = proofs[cell_id]
        assert spec.verify_cell_proof(commitment, cell_id, cell_bytes, proof)
        identifier = make_id(commitment, cell_id, cell_bytes, proof)
        yield f'verify_cell_proof_case_valid_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex_cell_bytes(cell_bytes),
                'proof': encode_hex(proof),
            },
            'output': True
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        cell_id = 81 % spec.CELLS_PER_BLOB
        cells, proofs = VALID_CELLS_AND_PROOFS[0]
        cell_bytes = cell_to_cell_bytes(cells[cell_id])
        proof = proofs[cell_id]
        expect_exception(spec.verify_cell_proof, commitment, cell_id, cell_bytes, proof)
        identifier = make_id(commitment, cell_id, cell_bytes, proof)
        yield f'verify_cell_proof_case_invalid_commitment_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex_cell_bytes(cell_bytes),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid cell_id
    for cell_id in [spec.CELLS_PER_BLOB, spec.CELLS_PER_BLOB + 1]:
        commitment = VALID_COMMITMENTS[1]
        cells, proofs = VALID_CELLS_AND_PROOFS[1]
        cell_bytes = cell_to_cell_bytes(cells[0])
        proof = proofs[0]
        expect_exception(spec.verify_cell_proof, commitment, cell_id, cell_bytes, proof)
        identifier = make_id(commitment, cell_id, cell_bytes, proof)
        yield f'verify_cell_proof_case_invalid_cell_id_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex_cell_bytes(cell_bytes),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid cell_bytes
    for cell_bytes in INVALID_INDIVIDUAL_CELL_BYTES:
        cell_id = 32 % spec.CELLS_PER_BLOB
        commitment = VALID_COMMITMENTS[2]
        cells, proofs = VALID_CELLS_AND_PROOFS[2]
        proof = proofs[cell_id]
        expect_exception(spec.verify_cell_proof, commitment, cell_id, cell_bytes, proof)
        identifier = make_id(commitment, cell_id, cell_bytes, proof)
        yield f'verify_cell_proof_case_invalid_cell_bytes_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex_cell_bytes(cell_bytes),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid proof
    for proof in INVALID_G1_POINTS:
        cell_id = 36 % spec.CELLS_PER_BLOB
        commitment = VALID_COMMITMENTS[3]
        cells, _ = VALID_CELLS_AND_PROOFS[3]
        cell_bytes = cell_to_cell_bytes(cells[cell_id])
        expect_exception(spec.verify_cell_proof, commitment, cell_id, cell_bytes, proof)
        identifier = make_id(commitment, cell_id, cell_bytes, proof)
        yield f'verify_cell_proof_case_invalid_proof_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex_cell_bytes(cell_bytes),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Incorrect commitment
    for i in range(len(VALID_BLOBS)):
        cell_id = 99 % spec.CELLS_PER_BLOB
        commitment = bls_add_one(VALID_COMMITMENTS[i])
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        cell_bytes = cell_to_cell_bytes(cells[cell_id])
        proof = proofs[cell_id]
        assert not spec.verify_cell_proof(commitment, cell_id, cell_bytes, proof)
        identifier = make_id(commitment, cell_id, cell_bytes, proof)
        yield f'verify_cell_proof_case_incorrect_commitment_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex_cell_bytes(cell_bytes),
                'proof': encode_hex(proof),
            },
            'output': False
        }

    # Incorrect cell_bytes
    for i in range(len(VALID_INDIVIDUAL_RANDOM_CELL_BYTES)):
        cell_id = 16 % spec.CELLS_PER_BLOB
        commitment = VALID_COMMITMENTS[i]
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        cell_bytes = VALID_INDIVIDUAL_RANDOM_CELL_BYTES[i]
        proof = proofs[cell_id]
        assert not spec.verify_cell_proof(commitment, cell_id, cell_bytes, proof)
        identifier = make_id(commitment, cell_id, cell_bytes, proof)
        yield f'verify_cell_proof_case_incorrect_cell_bytes_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex_cell_bytes(cell_bytes),
                'proof': encode_hex(proof),
            },
            'output': False
        }

    # Incorrect proof
    for i in range(len(VALID_BLOBS)):
        cell_id = 91 % spec.CELLS_PER_BLOB
        commitment = VALID_COMMITMENTS[i]
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        cell_bytes = cell_to_cell_bytes(cells[cell_id])
        proof = bls_add_one(proofs[cell_id])
        assert not spec.verify_cell_proof(commitment, cell_id, cell_bytes, proof)
        identifier = make_id(commitment, cell_id, cell_bytes, proof)
        yield f'verify_cell_proof_case_incorrect_proof_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex_cell_bytes(cell_bytes),
                'proof': encode_hex(proof),
            },
            'output': False
        }


###############################################################################
# Test cases for verify_cell_proof_batch
###############################################################################

def case04_verify_cell_proof_batch():
    # Valid cases
    for i in range(len(VALID_BLOBS)):
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        row_commitments = [VALID_COMMITMENTS[i]]
        row_indices = [0] * spec.CELLS_PER_BLOB
        column_indices = list(range(spec.CELLS_PER_BLOB))
        cells_bytes = cells_to_cells_bytes(cells)
        assert spec.verify_cell_proof_batch(row_commitments, row_indices, column_indices, cells_bytes, proofs)
        identifier = make_id(row_commitments, row_indices, column_indices, cells_bytes, proofs)
        yield f'verify_cell_proof_batch_case_valid_{identifier}', {
            'input': {
                'row_commitments': encode_hex_list(row_commitments),
                'row_indices': row_indices,
                'column_indices': column_indices,
                'cells': encode_hex_cells_bytes(cells_bytes),
                'proofs': encode_hex_list(proofs),
            },
            'output': True
        }


###############################################################################
# Test cases for recover_polynomial
###############################################################################

def case05_recover_polynomial():
    # Valid, no missing cells
    blob = BLOB_RANDOM_VALID1
    cells = spec.compute_cells(blob)
    cell_ids = list(range(spec.CELLS_PER_BLOB))
    cells_bytes = cells_to_cells_bytes(cells)
    recovered_cells = spec.recover_polynomial(cell_ids, cells_bytes)
    for i in range(spec.FIELD_ELEMENTS_PER_EXT_BLOB):
        j, k = int(i / int(spec.FIELD_ELEMENTS_PER_CELL)), i % int(spec.FIELD_ELEMENTS_PER_CELL)
        assert recovered_cells[i] == cells[j][k]
    identifier = make_id(cell_ids, cells_bytes)
    yield f'recover_polynomial_case_valid_no_missing_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_cells_bytes(cells_bytes),
        },
        'output': encode_hex_bls_field_list(recovered_cells)
    }

    # Valid, half missing cells
    blob = BLOB_RANDOM_VALID2
    cells = spec.compute_cells(blob)
    cell_ids = []
    cells_bytes = []
    for cell_id, cell in enumerate(cells):
        if cell_id % 2 == 0:
            continue
        cell_ids.append(cell_id)
        cells_bytes.append(cell_to_cell_bytes(cell))
    recovered_cells = spec.recover_polynomial(cell_ids, cells_bytes)
    for i in range(spec.FIELD_ELEMENTS_PER_EXT_BLOB):
        j, k = int(i / int(spec.FIELD_ELEMENTS_PER_CELL)), i % int(spec.FIELD_ELEMENTS_PER_CELL)
        assert recovered_cells[i] == cells[j][k]
    identifier = make_id(cell_ids, cells_bytes)
    yield f'recover_polynomial_case_valid_half_missing_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_cells_bytes(cells_bytes),
        },
        'output': encode_hex_bls_field_list(recovered_cells)
    }


###############################################################################
# Main logic
###############################################################################

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
                runner_name='kzg_peerdas',
                handler_name=handler_name,
                suite_name='kzg_peerdas',
                case_name=case_name,
                case_fn=lambda: [('data', 'data', case_content)]
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    bls.use_arkworks()
    gen_runner.run_generator("kzg_peerdas", [
        # EIP-7594
        create_provider(EIP7594, 'compute_cells', case01_compute_cells),
        create_provider(EIP7594, 'compute_cells_and_proofs', case02_compute_cells_and_proofs),
        create_provider(EIP7594, 'verify_cell_proof', case03_verify_cell_proof),
        create_provider(EIP7594, 'verify_cell_proof_batch', case04_verify_cell_proof_batch),
        create_provider(EIP7594, 'recover_polynomial', case05_recover_polynomial),
    ])
