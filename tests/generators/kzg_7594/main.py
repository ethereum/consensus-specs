"""
KZG test vectors generator for EIP-7594
"""

from functools import lru_cache
from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import encode_hex

from eth2spec.fulu import spec
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.test.helpers.constants import FULU
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.test.utils.kzg_tests import (
    CELL_RANDOM_VALID1,
    CELL_RANDOM_VALID2,
    INVALID_BLOBS,
    INVALID_G1_POINTS,
    INVALID_INDIVIDUAL_CELL_BYTES,
    VALID_BLOBS,
    bls_add_one,
    encode_hex_list,
)
from eth2spec.utils import bls


###############################################################################
# Test helpers
###############################################################################


@lru_cache(maxsize=None)
def cached_blob_to_kzg_commitment(blob):
    return spec.blob_to_kzg_commitment(blob)


@lru_cache(maxsize=None)
def cached_compute_cells_and_kzg_proofs(blob):
    return spec.compute_cells_and_kzg_proofs(blob)


###############################################################################
# Test cases for compute_cells
###############################################################################


def case_compute_cells():
    def run_test_case(blob):
        def _runner():
            try:
                cells = None
                cells = spec.compute_cells(blob)
            except:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {"blob": encode_hex(blob)},
                        "output": encode_hex_list(cells) if cells is not None else None,
                    },
                )
            ]

        return _runner

    # Valid cases
    for index, blob in enumerate(VALID_BLOBS):
        yield f"compute_cells_case_valid_{index}", lambda: run_test_case(blob)

    # Edge case: Invalid blobs
    for index, blob in enumerate(INVALID_BLOBS):
        yield f"compute_cells_invalid_blob_{index}", lambda: run_test_case(blob)


###############################################################################
# Test cases for compute_cells_and_kzg_proofs
###############################################################################


def case_compute_cells_and_kzg_proofs():
    def run_test_case(blob):
        def _runner():
            try:
                cells, proofs = None, None
                cells, proofs = cached_compute_cells_and_kzg_proofs(blob)
            except:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {"blob": encode_hex(blob)},
                        "output": (
                            (encode_hex_list(cells), encode_hex_list(proofs))
                            if cells is not None
                            else None
                        ),
                    },
                )
            ]

        return _runner

    # Valid cases
    for index, blob in enumerate(VALID_BLOBS):
        yield f"compute_cells_and_kzg_proofs_case_valid_{index}", lambda: run_test_case(blob)

    # Edge case: Invalid blobs
    for index, blob in enumerate(INVALID_BLOBS):
        yield f"compute_cells_and_kzg_proofs_case_invalid_blob_{index}", lambda: run_test_case(blob)


###############################################################################
# Test cases for verify_cell_kzg_proof_batch
###############################################################################


def case_verify_cell_kzg_proof_batch():
    def run_test_case(input_getter):
        def _runner():
            commitments, cell_indices, cells, proofs = input_getter()
            try:
                ok = None
                ok = spec.verify_cell_kzg_proof_batch(commitments, cell_indices, cells, proofs)
            except:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "commitments": encode_hex_list(commitments),
                            "cell_indices": cell_indices,
                            "cells": encode_hex_list(cells),
                            "proofs": encode_hex_list(proofs),
                        },
                        "output": ok if ok is not None else None,
                    },
                )
            ]

        return _runner

    # Valid cases
    for index, blob in enumerate(VALID_BLOBS):

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(blob)
            commitments = [cached_blob_to_kzg_commitment(blob) for _ in cells]
            cell_indices = list(range(spec.CELLS_PER_EXT_BLOB))
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_valid_{index}", run_test_case(get_inputs)

    # Valid: zero cells
    if True:

        def get_inputs():
            return [], [], [], []

        yield f"verify_cell_kzg_proof_batch_case_valid_zero_cells", run_test_case(get_inputs)

    # Valid: Verify cells from multiple blobs
    if True:

        def get_inputs():
            cells0, proofs0 = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[0])
            cells1, proofs1 = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[1])
            commitments = [
                cached_blob_to_kzg_commitment(VALID_BLOBS[0]),
                cached_blob_to_kzg_commitment(VALID_BLOBS[1]),
            ]
            cell_indices = [0, 0]
            cells = [cells0[0], cells1[0]]
            proofs = [proofs0[0], proofs1[0]]
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_valid_multiple_blobs", run_test_case(get_inputs)

    # Valid: Same cell multiple times
    if True:

        def get_inputs():
            num_duplicates = 3
            commitments = [cached_blob_to_kzg_commitment(VALID_BLOBS[3])] * num_duplicates
            cell_indices = [0] * num_duplicates
            cells = [cached_compute_cells_and_kzg_proofs(VALID_BLOBS[3])[0][0]] * num_duplicates
            proofs = [cached_compute_cells_and_kzg_proofs(VALID_BLOBS[3])[1][0]] * num_duplicates
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_valid_same_cell_multiple_times", run_test_case(
            get_inputs
        )

    # Incorrect commitment
    if True:

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[5])
            cells, proofs = cells[:1], proofs[:1]
            # Use the wrong commitment
            commitments = [bls_add_one(cached_blob_to_kzg_commitment(VALID_BLOBS[5]))]
            cell_indices = list(range(len(cells)))
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_incorrect_commitment", run_test_case(get_inputs)

    # Incorrect cell
    if True:

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[6])
            cells, proofs = cells[:1], proofs[:1]
            commitments = [cached_blob_to_kzg_commitment(VALID_BLOBS[6])]
            cell_indices = list(range(len(cells)))
            # Change last cell so it's wrong
            cells[-1] = CELL_RANDOM_VALID2
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_incorrect_cell", run_test_case(get_inputs)

    # Incorrect proof
    if True:

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[0])
            cells, proofs = cells[:1], proofs[:1]
            commitments = [cached_blob_to_kzg_commitment(VALID_BLOBS[0])]
            cell_indices = list(range(len(cells)))
            # Change last proof so it's wrong
            proofs[-1] = bls_add_one(proofs[-1])
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_incorrect_proof", run_test_case(get_inputs)

    # Edge case: Invalid commitment
    for index, commitment in enumerate(INVALID_G1_POINTS):

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(
                VALID_BLOBS[index % len(INVALID_G1_POINTS)]
            )
            cells, proofs = cells[:1], proofs[:1]
            # Set commitments to the invalid commitment
            commitments = [commitment]
            cell_indices = list(range(len(cells)))
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_invalid_commitment_{index}", run_test_case(
            get_inputs
        )

    # Edge case: Invalid cell_index
    if True:

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[1])
            cells, proofs = cells[:1], proofs[:1]
            commitments = [cached_blob_to_kzg_commitment(VALID_BLOBS[1])]
            cell_indices = list(range(len(cells)))
            # Set first cell index to an invalid value
            cell_indices[0] = int(spec.CELLS_PER_EXT_BLOB)
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_invalid_cell_index", run_test_case(get_inputs)

    # Edge case: Invalid cell
    for index, cell in enumerate(INVALID_INDIVIDUAL_CELL_BYTES):

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(
                VALID_BLOBS[index % len(INVALID_INDIVIDUAL_CELL_BYTES)]
            )
            cells, proofs = cells[:1], proofs[:1]
            commitments = [
                cached_blob_to_kzg_commitment(
                    VALID_BLOBS[index % len(INVALID_INDIVIDUAL_CELL_BYTES)]
                )
            ]
            cell_indices = list(range(len(cells)))
            # Set first cell to the invalid cell
            cells[0] = cell
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_invalid_cell_{index}", run_test_case(get_inputs)

    # Edge case: Invalid proof
    for index, proof in enumerate(INVALID_G1_POINTS):

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(
                VALID_BLOBS[index % len(INVALID_G1_POINTS)]
            )
            cells, proofs = cells[:1], proofs[:1]
            commitments = [
                cached_blob_to_kzg_commitment(VALID_BLOBS[index % len(INVALID_G1_POINTS)])
            ]
            cell_indices = list(range(len(cells)))
            # Set first proof to the invalid proof
            proofs[0] = proof
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_invalid_proof_{index}", run_test_case(get_inputs)

    # Edge case: Missing a commitment
    if True:

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[0])
            cells, proofs = cells[:2], proofs[:2]
            # Do not include the second commitment
            commitments = [cached_blob_to_kzg_commitment(VALID_BLOBS[0])]
            cell_indices = list(range(len(cells)))
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_invalid_missing_commitment", run_test_case(
            get_inputs
        )

    # Edge case: Missing a cell index
    if True:

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[2])
            cells, proofs = cells[:2], proofs[:2]
            commitments = [
                cached_blob_to_kzg_commitment(VALID_BLOBS[2]),
                cached_blob_to_kzg_commitment(VALID_BLOBS[2]),
            ]
            # Leave off one of the cell indices
            cell_indices = list(range(len(cells) - 1))
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_invalid_missing_cell_index", run_test_case(
            get_inputs
        )

    # Edge case: Missing a cell
    if True:

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[3])
            cells, proofs = cells[:2], proofs[:2]
            commitments = [
                cached_blob_to_kzg_commitment(VALID_BLOBS[3]),
                cached_blob_to_kzg_commitment(VALID_BLOBS[3]),
            ]
            cell_indices = list(range(len(cells)))
            # Remove the last proof
            cells = cells[:-1]
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_invalid_missing_cell", run_test_case(get_inputs)

    # Edge case: Missing a proof
    if True:

        def get_inputs():
            cells, proofs = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[4])
            cells, proofs = cells[:2], proofs[:2]
            commitments = [
                cached_blob_to_kzg_commitment(VALID_BLOBS[4]),
                cached_blob_to_kzg_commitment(VALID_BLOBS[4]),
            ]
            cell_indices = list(range(len(cells)))
            # Remove the last proof
            proofs = proofs[:-1]
            return commitments, cell_indices, cells, proofs

        yield f"verify_cell_kzg_proof_batch_case_invalid_missing_proof", run_test_case(get_inputs)


###############################################################################
# Test cases for recover_cells_and_kzg_proofs
###############################################################################


def case_recover_cells_and_kzg_proofs():
    def run_test_case(input_getter):
        def _runner():
            cell_indices, cells = input_getter()
            try:
                recovered_cells, recovered_proofs = None, None
                recovered_cells, recovered_proofs = spec.recover_cells_and_kzg_proofs(
                    cell_indices, cells
                )
            except:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "cell_indices": cell_indices,
                            "cells": encode_hex_list(cells),
                        },
                        "output": (
                            (encode_hex_list(recovered_cells), encode_hex_list(recovered_proofs))
                            if recovered_cells is not None
                            else None
                        ),
                    },
                )
            ]

        return _runner

    # Valid: No missing cells
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[0])
            cell_indices = list(range(spec.CELLS_PER_EXT_BLOB))
            return cell_indices, cells

        yield f"recover_cells_and_kzg_proofs_case_valid_no_missing", run_test_case(get_inputs)

    # Valid: Half missing cells (every other cell)
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[1])
            cell_indices = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_valid_half_missing_every_other_cell", run_test_case(
            get_inputs
        )

    # Valid: Half missing cells (first half)
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[2])
            cell_indices = list(range(0, spec.CELLS_PER_EXT_BLOB // 2))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_valid_half_missing_first_half", run_test_case(
            get_inputs
        )

    # Valid: Half missing cells (second half)
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[3])
            cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2, spec.CELLS_PER_EXT_BLOB))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_valid_half_missing_second_half", run_test_case(
            get_inputs
        )

    # Edge case: All cells are missing
    if True:

        def get_inputs():
            return [], []

        yield f"recover_cells_and_kzg_proofs_case_invalid_all_cells_are_missing", run_test_case(
            get_inputs
        )

    # Edge case: More than half missing
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[4])
            cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2 - 1))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_invalid_more_than_half_missing", run_test_case(
            get_inputs
        )

    # Edge case: More cells provided than CELLS_PER_EXT_BLOB
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[5])
            cell_indices = list(range(spec.CELLS_PER_EXT_BLOB)) + [0]
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_invalid_more_cells_than_cells_per_ext_blob", run_test_case(
            get_inputs
        )

    # Edge case: Invalid cell_index
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[6])
            cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            # Replace first cell_index with an invalid value
            cell_indices[0] = int(spec.CELLS_PER_EXT_BLOB)
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_invalid_cell_index", run_test_case(get_inputs)

    # Edge case: Invalid cell
    for index, cell in enumerate(INVALID_INDIVIDUAL_CELL_BYTES):

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[6])
            cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            # Replace first cell with an invalid value
            partial_cells[0] = cell
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_invalid_cell_{index}", run_test_case(get_inputs)

    # Edge case: More cell_indices than cells
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[0])
            cell_indices = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            # Add another cell_index
            cell_indices.append(int(spec.CELLS_PER_EXT_BLOB - 1))
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_invalid_more_cell_indices_than_cells", run_test_case(
            get_inputs
        )

    # Edge case: More cells than cell_indices
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[1])
            cell_indices = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            # Add another cell
            partial_cells.append(CELL_RANDOM_VALID1)
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_invalid_more_cells_than_cell_indices", run_test_case(
            get_inputs
        )

    # Edge case: Duplicate cell_index
    if True:

        def get_inputs():
            cells, _ = cached_compute_cells_and_kzg_proofs(VALID_BLOBS[2])
            # There will be 65 cells, where 64 are unique and 1 is a duplicate.
            # Depending on the implementation, 63 & 1 might not fail for the right
            # reason. For example, if the implementation assigns cells in an array
            # via index, this would result in 63 cells and the test would fail due
            # to insufficient cell count, not because of a duplicate cell.
            cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2 + 1))
            partial_cells = [cells[cell_index] for cell_index in cell_indices]
            # Replace first cell_index with the second cell_index
            cell_indices[0] = cell_indices[1]
            return cell_indices, partial_cells

        yield f"recover_cells_and_kzg_proofs_case_invalid_duplicate_cell_index", run_test_case(
            get_inputs
        )


###############################################################################
# Main logic
###############################################################################


def create_provider(
    fork_name: SpecForkName,
    handler_name: str,
    test_case_fn: Callable[[], Iterable[Tuple[str, Dict[str, Any]]]],
) -> gen_typing.TestProvider:
    def prepare_fn() -> None:
        # Nothing to load / change in spec. Maybe in future forks.
        # Put the tests into the general config category, to not require any particular configuration.
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for case_name, case_fn in test_case_fn():
            yield gen_typing.TestCase(
                fork_name=fork_name,
                preset_name="general",
                runner_name="kzg",
                handler_name=handler_name,
                suite_name="kzg-mainnet",
                case_name=case_name,
                case_fn=case_fn,
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    bls.use_arkworks()
    gen_runner.run_generator(
        "kzg_7594",
        [
            create_provider(FULU, "compute_cells", case_compute_cells),
            create_provider(
                FULU, "compute_cells_and_kzg_proofs", case_compute_cells_and_kzg_proofs
            ),
            create_provider(FULU, "verify_cell_kzg_proof_batch", case_verify_cell_kzg_proof_batch),
            create_provider(
                FULU, "recover_cells_and_kzg_proofs", case_recover_cells_and_kzg_proofs
            ),
        ],
    )
