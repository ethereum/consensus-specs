import random
from eth2spec.test.context import (
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
def test_recover_matrix(spec):
    rng = random.Random(5566)

    # Number of samples we will be recovering from
    N_SAMPLES = spec.CELLS_PER_BLOB // 2

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
            cell_id = rng.randint(0, spec.CELLS_PER_BLOB - 1)
            while cell_id in cell_ids:
                cell_id = rng.randint(0, spec.CELLS_PER_BLOB - 1)
            cell_ids.append(cell_id)
            cell = cells[cell_id]
            cells_dict[(blob_index, cell_id)] = cell
        assert len(cell_ids) == N_SAMPLES

    # Recover the matrix
    recovered_matrix = spec.recover_matrix(cells_dict, blob_count)
    flatten_original_cells = [cell for cells in original_cells for cell in cells]
    assert recovered_matrix == flatten_original_cells
