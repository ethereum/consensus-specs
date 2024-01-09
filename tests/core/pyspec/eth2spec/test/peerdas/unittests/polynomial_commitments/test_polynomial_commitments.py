import random
from eth2spec.test.context import (
    spec_test,
    single_phase,
    with_peerdas_and_later,
)
from eth2spec.test.helpers.sharding import (
    get_sample_blob,
)


@with_peerdas_and_later
@spec_test
@single_phase
def test_fft(spec):
    vals = [int.from_bytes(x, spec.KZG_ENDIANNESS) for x in spec.KZG_SETUP_G1_MONOMIAL]
    roots_of_unity = spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)
    result = spec.fft_field(vals, roots_of_unity)
    assert len(result) == len(vals)
    # TODO: add more assertions?
    # One possible test would be to use polynomial_eval_to_coeff()


@with_peerdas_and_later
@spec_test
@single_phase
def test_verify_cell_proof(spec):
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_proofs(blob)
    cell_id = 0
    assert spec.verify_cell_proof(commitment, cell_id, cells[cell_id], proofs[cell_id])
    cell_id = 1
    assert spec.verify_cell_proof(commitment, cell_id, cells[cell_id], proofs[cell_id])


@with_peerdas_and_later
@spec_test
@single_phase
def test_verify_cell_proof_batch(spec):
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_proofs(blob)

    assert spec.verify_cell_proof_batch(
        row_commitments=[commitment],
        row_ids=[0],
        column_ids=[0, 1],
        cells=cells[0:1],
        proofs=proofs,
    )


@with_peerdas_and_later
@spec_test
@single_phase
def test_recover_polynomial(spec):
    rng = random.Random(5566)

    # Number of samples we will be recovering from
    N_SAMPLES = spec.CELLS_PER_BLOB // 2

    # Get the data we will be working with
    blob = get_sample_blob(spec)
    # Get the data in evaluation form
    original_polynomial = spec.blob_to_polynomial(blob)

    # Extend data with Reed-Solomon and split the extended data in cells
    cells = spec.compute_cells(blob)

    # Compute the cells we will be recovering from
    cell_ids = []
    known_cells = []
    # First figure out just the indices of the cells
    for i in range(N_SAMPLES):
        j = rng.randint(0, spec.CELLS_PER_BLOB)
        while j in cell_ids:
            j = rng.randint(0, spec.CELLS_PER_BLOB)
        cell_ids.append(j)
    # Now the cells themselves
    known_cells = [cells[cell_id] for cell_id in cell_ids]

    # Recover the data
    recovered_data = spec.recover_polynomial(cell_ids, known_cells)

    # Check that the original data match the non-extended portion of the recovered data
    assert original_polynomial == recovered_data[:len(recovered_data) // 2]

    # Now flatten the cells and check that they match the entirety of the recovered data
    flattened_cells = [x for xs in cells for x in xs]
    assert flattened_cells == recovered_data
