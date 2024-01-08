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
    blob = get_sample_blob(spec)
    original_polynomial = spec.blob_to_polynomial(blob)
    cells = spec.compute_cells(blob)
    cell_ids = list(range(spec.CELLS_PER_BLOB // 2))
    known_cells = [cells[cell_id] for cell_id in cell_ids]
    result = spec.recover_polynomial(cell_ids, known_cells)

    assert original_polynomial == result[0:len(result) // 2]
