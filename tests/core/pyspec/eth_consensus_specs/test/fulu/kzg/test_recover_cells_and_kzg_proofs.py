import random

from eth_consensus_specs.test.context import (
    expect_assertion_error,
    only_generator,
    single_phase,
    spec_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import FULU
from eth_consensus_specs.test.utils.kzg_tests import (
    CELL_RANDOM_VALID1,
    encode_hex_list,
    INVALID_INDIVIDUAL_CELL_BYTES,
    VALID_BLOBS,
)
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test


def _run_recover_cells_and_kzg_proofs_test(
    spec,
    cell_indices,
    cells,
    expected_recovered_cells=None,
    expected_recovered_proofs=None,
    valid: bool = True,
):
    if valid:
        recovered_cells, recovered_proofs = spec.recover_cells_and_kzg_proofs(cell_indices, cells)
        if expected_recovered_cells is not None:
            assert recovered_cells == expected_recovered_cells
        if expected_recovered_proofs is not None:
            assert recovered_proofs == expected_recovered_proofs
    else:
        expect_assertion_error(lambda: spec.recover_cells_and_kzg_proofs(cell_indices, cells))
        recovered_cells, recovered_proofs = None, None

    yield (
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


###############################################################################
# Valid cases
###############################################################################


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_valid_no_missing(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[0])
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB))

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        cells,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_valid_half_missing_every_other_cell(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[1])
    cell_indices = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
    partial_cells = [cells[cell_index] for cell_index in cell_indices]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_valid_half_missing_first_half(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[2])
    cell_indices = list(range(0, spec.CELLS_PER_EXT_BLOB // 2))
    partial_cells = [cells[cell_index] for cell_index in cell_indices]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_valid_half_missing_second_half(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[3])
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2, spec.CELLS_PER_EXT_BLOB))
    partial_cells = [cells[cell_index] for cell_index in cell_indices]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
    )


###############################################################################
# Invalid cases
###############################################################################


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_all_cells_are_missing(spec):
    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        [],
        [],
        valid=False,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_more_than_half_missing(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[4])
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2 - 1))
    partial_cells = [cells[cell_index] for cell_index in cell_indices]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
        valid=False,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_more_cells_than_cells_per_ext_blob(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[5])
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB)) + [0]
    partial_cells = [cells[cell_index] for cell_index in cell_indices]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
        valid=False,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_cell_index(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[6])
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2))
    partial_cells = [cells[cell_index] for cell_index in cell_indices]
    # Replace first cell_index with an invalid value
    cell_indices[0] = int(spec.CELLS_PER_EXT_BLOB)

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
        valid=False,
    )


@template_test
def _recover_cells_and_kzg_proofs_case_invalid_cell(index):
    cell = INVALID_INDIVIDUAL_CELL_BYTES[index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([FULU])
    @spec_test
    @single_phase
    def the_test(spec):
        cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[6])
        cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2))
        partial_cells = [cells[cell_index] for cell_index in cell_indices]
        # Replace first cell with an invalid value
        partial_cells[0] = cell

        yield from _run_recover_cells_and_kzg_proofs_test(
            spec,
            cell_indices,
            partial_cells,
            valid=False,
        )

    return (the_test, f"test_recover_cells_and_kzg_proofs_case_invalid_cell_{index}")


for index in range(len(INVALID_INDIVIDUAL_CELL_BYTES)):
    _recover_cells_and_kzg_proofs_case_invalid_cell(index)


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_more_cell_indices_than_cells(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[0])
    cell_indices = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
    partial_cells = [cells[cell_index] for cell_index in cell_indices]
    # Add another cell_index
    cell_indices.append(int(spec.CELLS_PER_EXT_BLOB - 1))

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
        valid=False,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_more_cells_than_cell_indices(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[1])
    cell_indices = list(range(0, spec.CELLS_PER_EXT_BLOB, 2))
    partial_cells = [cells[cell_index] for cell_index in cell_indices]
    # Add another cell
    partial_cells.append(CELL_RANDOM_VALID1)

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
        valid=False,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_duplicate_cell_index(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[2])
    # There will be 65 cells, where 64 are unique and 1 is a duplicate.
    # Depending on the implementation, 63 & 1 might not fail for the right
    # reason. For example, if the implementation assigns cells in an array
    # via index, this would result in 63 cells and the test would fail due
    # to insufficient cell count, not because of a duplicate cell.
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2 + 1))
    partial_cells = [cells[cell_index] for cell_index in cell_indices]
    # Replace first cell_index with the second cell_index
    cell_indices[0] = cell_indices[1]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
        valid=False,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_shuffled_no_missing(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[4])
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB))
    random.seed(42)  # Use fixed seed for reproducibility
    random.shuffle(cell_indices)
    all_cells = [cells[cell_index] for cell_index in cell_indices]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        all_cells,
        valid=False,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_shuffled_one_missing(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[5])
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB - 1))
    random.seed(42)  # Use fixed seed for reproducibility
    random.shuffle(cell_indices)
    partial_cells = [cells[cell_index] for cell_index in cell_indices]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
        valid=False,
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([FULU])
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs_case_invalid_shuffled_half_missing(spec):
    cells, _ = spec.compute_cells_and_kzg_proofs(VALID_BLOBS[5])
    cell_indices = list(range(spec.CELLS_PER_EXT_BLOB // 2))
    random.seed(42)  # Use fixed seed for reproducibility
    random.shuffle(cell_indices)
    partial_cells = [cells[cell_index] for cell_index in cell_indices]

    yield from _run_recover_cells_and_kzg_proofs_test(
        spec,
        cell_indices,
        partial_cells,
        valid=False,
    )
