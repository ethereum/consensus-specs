"""
KZG test vectors generator for EIP-7594
"""

from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import encode_hex

from eth2spec.eip7594 import spec
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.test.helpers.constants import EIP7594
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.test.utils.kzg_tests import *
from eth2spec.utils import bls


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
            'output': encode_hex_list(cells)
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
            'output': (encode_hex_list(cells), encode_hex_list(proofs))
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
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        commitment = VALID_COMMITMENTS[i]
        cell_id = (2 ** i - 1) % spec.CELLS_PER_EXT_BLOB
        cell = cells[cell_id]
        proof = proofs[cell_id]
        assert spec.verify_cell_proof(commitment, cell_id, cell, proof)
        identifier = make_id(commitment, cell_id, cell, proof)
        yield f'verify_cell_proof_case_valid_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex(cell),
                'proof': encode_hex(proof),
            },
            'output': True
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        cells, proofs = VALID_CELLS_AND_PROOFS[0]
        cell_id = 81 % spec.CELLS_PER_EXT_BLOB
        cell = cells[cell_id]
        proof = proofs[cell_id]
        expect_exception(spec.verify_cell_proof, commitment, cell_id, cell, proof)
        identifier = make_id(commitment, cell_id, cell, proof)
        yield f'verify_cell_proof_case_invalid_commitment_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex(cell),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid cell_id
    for cell_id in [spec.CELLS_PER_EXT_BLOB, spec.CELLS_PER_EXT_BLOB + 1]:
        cells, proofs = VALID_CELLS_AND_PROOFS[1]
        commitment = VALID_COMMITMENTS[1]
        cell = cells[0]
        proof = proofs[0]
        expect_exception(spec.verify_cell_proof, commitment, cell_id, cell, proof)
        identifier = make_id(commitment, cell_id, cell, proof)
        yield f'verify_cell_proof_case_invalid_cell_id_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex(cell),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid cell
    for cell in INVALID_INDIVIDUAL_CELL_BYTES:
        cell_id = 32 % spec.CELLS_PER_EXT_BLOB
        commitment = VALID_COMMITMENTS[2]
        cells, proofs = VALID_CELLS_AND_PROOFS[2]
        proof = proofs[cell_id]
        expect_exception(spec.verify_cell_proof, commitment, cell_id, cell, proof)
        identifier = make_id(commitment, cell_id, cell, proof)
        yield f'verify_cell_proof_case_invalid_cell_bytes_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex(cell),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid proof
    for proof in INVALID_G1_POINTS:
        cells, _ = VALID_CELLS_AND_PROOFS[3]
        commitment = VALID_COMMITMENTS[3]
        cell_id = 36 % spec.CELLS_PER_EXT_BLOB
        cell = cells[cell_id]
        expect_exception(spec.verify_cell_proof, commitment, cell_id, cell, proof)
        identifier = make_id(commitment, cell_id, cell, proof)
        yield f'verify_cell_proof_case_invalid_proof_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex(cell),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Incorrect commitment
    for i in range(len(VALID_BLOBS)):
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        commitment = bls_add_one(VALID_COMMITMENTS[i])
        cell_id = 99 % spec.CELLS_PER_EXT_BLOB
        cell = cells[cell_id]
        proof = proofs[cell_id]
        assert not spec.verify_cell_proof(commitment, cell_id, cell, proof)
        identifier = make_id(commitment, cell_id, cell, proof)
        yield f'verify_cell_proof_case_incorrect_commitment_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex(cell),
                'proof': encode_hex(proof),
            },
            'output': False
        }

    # Incorrect cell
    for i in range(len(VALID_INDIVIDUAL_RANDOM_CELL_BYTES)):
        cell_id = 16 % spec.CELLS_PER_EXT_BLOB
        commitment = VALID_COMMITMENTS[i]
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        cell = VALID_INDIVIDUAL_RANDOM_CELL_BYTES[i]
        proof = proofs[cell_id]
        assert not spec.verify_cell_proof(commitment, cell_id, cell, proof)
        identifier = make_id(commitment, cell_id, cell, proof)
        yield f'verify_cell_proof_case_incorrect_cell_bytes_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex(cell),
                'proof': encode_hex(proof),
            },
            'output': False
        }

    # Incorrect proof
    for i in range(len(VALID_BLOBS)):
        cell_id = 91 % spec.CELLS_PER_EXT_BLOB
        commitment = VALID_COMMITMENTS[i]
        cells, proofs = VALID_CELLS_AND_PROOFS[i]
        cell = cells[cell_id]
        proof = bls_add_one(proofs[cell_id])
        assert not spec.verify_cell_proof(commitment, cell_id, cell, proof)
        identifier = make_id(commitment, cell_id, cell, proof)
        yield f'verify_cell_proof_case_incorrect_proof_{identifier}', {
            'input': {
                'commitment': encode_hex(commitment),
                'cell_id': cell_id,
                'cell': encode_hex(cell),
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
        row_indices = [0] * spec.CELLS_PER_EXT_BLOB
        column_indices = list(range(spec.CELLS_PER_EXT_BLOB))
        assert spec.verify_cell_proof_batch(row_commitments, row_indices, column_indices, cells, proofs)
        identifier = make_id(row_commitments, row_indices, column_indices, cells, proofs)
        yield f'verify_cell_proof_batch_case_valid_{identifier}', {
            'input': {
                'row_commitments': encode_hex_list(row_commitments),
                'row_indices': row_indices,
                'column_indices': column_indices,
                'cells': encode_hex_list(cells),
                'proofs': encode_hex_list(proofs),
            },
            'output': True
        }


###############################################################################
# Test cases for recover_all_cells
###############################################################################

def case05_recover_all_cells():
    # Valid: No missing cells
    blob = BLOB_RANDOM_VALID1
    cells = spec.compute_cells(blob)
    cell_ids = list(range(spec.CELLS_PER_EXT_BLOB))
    recovered_cells = spec.recover_all_cells(cell_ids, cells)
    assert recovered_cells == cells
    identifier = make_id(cell_ids, cells)
    yield f'recover_all_cells_case_valid_no_missing_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_list(cells),
        },
        'output': encode_hex_list(recovered_cells)
    }

    # Valid: Half missing cells
    blob = BLOB_RANDOM_VALID2
    cells = spec.compute_cells(blob)
    cell_ids = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
    partial_cells = [cells[cell_id] for cell_id in cell_ids]
    recovered_cells = spec.recover_all_cells(cell_ids, partial_cells)
    assert recovered_cells == cells
    identifier = make_id(cell_ids, partial_cells)
    yield f'recover_all_cells_case_valid_half_missing_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_list(partial_cells),
        },
        'output': encode_hex_list(recovered_cells)
    }

    # Edge case: More than half missing
    blob = BLOB_RANDOM_VALID3
    cells = spec.compute_cells(blob)
    cell_ids = list(range(spec.CELLS_PER_EXT_BLOB // 2 - 1))
    partial_cells = [cells[cell_id] for cell_id in cell_ids]
    expect_exception(spec.recover_all_cells, cell_ids, partial_cells)
    identifier = make_id(cell_ids, partial_cells)
    yield f'recover_all_cells_case_invalid_more_than_half_missing_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_list(partial_cells),
        },
        'output': None
    }

    # Edge case: Invalid cell_id
    blob = BLOB_RANDOM_VALID1
    cells = spec.compute_cells(blob)
    cell_ids = list(range(spec.CELLS_PER_EXT_BLOB // 2))
    partial_cells = [cells[cell_id] for cell_id in cell_ids]
    # Replace first cell_id with an invalid value
    cell_ids[0] = spec.CELLS_PER_EXT_BLOB
    expect_exception(spec.recover_all_cells, cell_ids, partial_cells)
    identifier = make_id(cell_ids, partial_cells)
    yield f'recover_all_cells_case_invalid_cell_id_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_list(partial_cells),
        },
        'output': None
    }

    # Edge case: Invalid cell
    blob = BLOB_RANDOM_VALID2
    cells = spec.compute_cells(blob)
    cell_ids = list(range(spec.CELLS_PER_EXT_BLOB // 2))
    partial_cells = [cells[cell_id] for cell_id in cell_ids]
    # Replace first cell with an invalid value
    partial_cells[0] = CELL_ONE_INVALID_FIELD
    expect_exception(spec.recover_all_cells, cell_ids, partial_cells)
    identifier = make_id(cell_ids, partial_cells)
    yield f'recover_all_cells_case_invalid_cell_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_list(partial_cells),
        },
        'output': None
    }

    # Edge case: More cell_ids than cells
    blob = BLOB_RANDOM_VALID3
    cells = spec.compute_cells(blob)
    cell_ids = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
    partial_cells = [cells[cell_id] for cell_id in cell_ids]
    # Add another cell_id
    cell_ids.append(spec.CELLS_PER_EXT_BLOB - 1)
    expect_exception(spec.recover_all_cells, cell_ids, partial_cells)
    identifier = make_id(cell_ids, partial_cells)
    yield f'recover_all_cells_case_invalid_more_cell_ids_than_cells_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_list(partial_cells),
        },
        'output': None
    }

    # Edge case: More cells than cell_ids
    blob = BLOB_RANDOM_VALID1
    cells = spec.compute_cells(blob)
    cell_ids = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
    partial_cells = [cells[cell_id] for cell_id in cell_ids]
    # Add another cell
    partial_cells.append(CELL_RANDOM_VALID1)
    expect_exception(spec.recover_all_cells, cell_ids, partial_cells)
    identifier = make_id(cell_ids, partial_cells)
    yield f'recover_all_cells_case_invalid_more_cells_than_cell_ids_{identifier}', {
        'input': {
            'cell_ids': cell_ids,
            'cells': encode_hex_list(partial_cells),
        },
        'output': None
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
                runner_name='kzg_7594',
                handler_name=handler_name,
                suite_name='kzg_7594',
                case_name=case_name,
                case_fn=lambda: [('data', 'data', case_content)]
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    bls.use_arkworks()
    gen_runner.run_generator("kzg_7594", [
        # EIP-7594
        create_provider(EIP7594, 'compute_cells', case01_compute_cells),
        create_provider(EIP7594, 'compute_cells_and_proofs', case02_compute_cells_and_proofs),
        create_provider(EIP7594, 'verify_cell_proof', case03_verify_cell_proof),
        create_provider(EIP7594, 'verify_cell_proof_batch', case04_verify_cell_proof_batch),
        create_provider(EIP7594, 'recover_all_cells', case05_recover_all_cells),
    ])
