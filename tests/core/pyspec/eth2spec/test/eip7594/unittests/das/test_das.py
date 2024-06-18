import random
from eth2spec.test.context import (
    expect_assertion_error,
    spec_test,
    single_phase,
    with_eip7594_and_later,
)
from eth2spec.test.helpers.sharding import (
    get_sample_blob,
)


@with_eip7594_and_later
@spec_test
@single_phase
def test_compute_extended_matrix(spec):
    rng = random.Random(5566)

    blob_count = 2
    input_blobs = [get_sample_blob(spec, rng=rng) for _ in range(blob_count)]
    extended_matrix = spec.compute_extended_matrix(input_blobs)
    assert len(extended_matrix) == spec.CELLS_PER_EXT_BLOB * blob_count

    rows = [extended_matrix[i:(i + spec.CELLS_PER_EXT_BLOB)]
            for i in range(0, len(extended_matrix), spec.CELLS_PER_EXT_BLOB)]
    assert len(rows) == blob_count
    assert len(rows[0]) == spec.CELLS_PER_EXT_BLOB

    for blob_index, row in enumerate(rows):
        extended_blob = []
        for cell in row:
            extended_blob.extend(spec.cell_to_coset_evals(cell))
        blob_part = extended_blob[0:len(extended_blob) // 2]
        blob = b''.join([spec.bls_field_to_bytes(x) for x in blob_part])
        assert blob == input_blobs[blob_index]


@with_eip7594_and_later
@spec_test
@single_phase
def test_recover_matrix(spec):
    rng = random.Random(5566)

    # Number of samples we will be recovering from
    N_SAMPLES = spec.CELLS_PER_EXT_BLOB // 2

    blob_count = 2
    cells_dict = {}
    original_cells = []
    for blob_index in range(blob_count):
        # Get the data we will be working with
        blob = get_sample_blob(spec, rng=rng)
        # Extend data with Reed-Solomon and split the extended data in cells
        cells = spec.compute_cells(blob)
        original_cells.append(cells)
        cell_ids = []
        # First figure out just the indices of the cells
        for _ in range(N_SAMPLES):
            cell_id = rng.randint(0, spec.CELLS_PER_EXT_BLOB - 1)
            while cell_id in cell_ids:
                cell_id = rng.randint(0, spec.CELLS_PER_EXT_BLOB - 1)
            cell_ids.append(cell_id)
            cell = cells[cell_id]
            cells_dict[(blob_index, cell_id)] = cell
        assert len(cell_ids) == N_SAMPLES

    # Recover the matrix
    recovered_matrix = spec.recover_matrix(cells_dict, blob_count)
    flatten_original_cells = [cell for cells in original_cells for cell in cells]
    assert recovered_matrix == flatten_original_cells


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__1(spec):
    rng = random.Random(1111)
    allowed_failures = rng.randint(0, spec.config.NUMBER_OF_COLUMNS // 2)
    spec.get_extended_sample_count(allowed_failures)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__2(spec):
    rng = random.Random(2222)
    allowed_failures = rng.randint(0, spec.config.NUMBER_OF_COLUMNS // 2)
    spec.get_extended_sample_count(allowed_failures)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__3(spec):
    rng = random.Random(3333)
    allowed_failures = rng.randint(0, spec.config.NUMBER_OF_COLUMNS // 2)
    spec.get_extended_sample_count(allowed_failures)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__lower_bound(spec):
    allowed_failures = 0
    spec.get_extended_sample_count(allowed_failures)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__upper_bound(spec):
    allowed_failures = spec.config.NUMBER_OF_COLUMNS // 2
    spec.get_extended_sample_count(allowed_failures)


@with_eip7594_and_later
@spec_test
@single_phase
def test_get_extended_sample_count__upper_bound_exceed(spec):
    allowed_failures = spec.config.NUMBER_OF_COLUMNS // 2 + 1
    expect_assertion_error(lambda: spec.get_extended_sample_count(allowed_failures))
