import random

from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_fulu_and_later,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob,
)


def chunks(lst, n):
    """Helper that splits a list into N sized chunks."""
    return [lst[i : i + n] for i in range(0, len(lst), n)]


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_matrix(spec):
    rng = random.Random(5566)

    blob_count = 2
    input_blobs = [get_sample_blob(spec, rng=rng) for _ in range(blob_count)]
    matrix = spec.compute_matrix(input_blobs)
    assert len(matrix) == spec.CELLS_PER_EXT_BLOB * blob_count

    rows = chunks(matrix, spec.CELLS_PER_EXT_BLOB)
    assert len(rows) == blob_count
    for row in rows:
        assert len(row) == spec.CELLS_PER_EXT_BLOB

    for blob_index, row in enumerate(rows):
        extended_blob = []
        for entry in row:
            extended_blob.extend(spec.cell_to_coset_evals(entry.cell))
        blob_part = extended_blob[0 : len(extended_blob) // 2]
        blob = b"".join([spec.bls_field_to_bytes(x) for x in blob_part])
        assert blob == input_blobs[blob_index]


@with_fulu_and_later
@spec_test
@single_phase
def test_recover_matrix(spec):
    rng = random.Random(5566)

    # Number of samples we will be recovering from
    N_SAMPLES = spec.CELLS_PER_EXT_BLOB // 2

    # Compute an extended matrix with two blobs
    blob_count = 2
    blobs = [get_sample_blob(spec, rng=rng) for _ in range(blob_count)]
    matrix = spec.compute_matrix(blobs)

    # Construct a matrix with some entries missing
    partial_matrix = []
    for blob_entries in chunks(matrix, spec.CELLS_PER_EXT_BLOB):
        rng.shuffle(blob_entries)
        partial_matrix.extend(blob_entries[:N_SAMPLES])

    # Given the partial matrix, recover the missing entries
    recovered_matrix = spec.recover_matrix(partial_matrix, blob_count)

    # Ensure that the recovered matrix matches the original matrix
    assert recovered_matrix == matrix
