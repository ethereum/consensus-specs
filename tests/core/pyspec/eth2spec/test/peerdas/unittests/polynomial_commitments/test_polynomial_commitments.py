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
    roots_of_unity = spec.ROOTS_OF_UNITY
    result = spec.fft_field(vals, roots_of_unity)
    assert len(result) == len(vals)
    # TODO: add more assertions?


@with_peerdas_and_later
@spec_test
@single_phase
def test_compute_and_verify_cells_and_proofs(spec):
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_proofs(blob)
    cell_id = 0
    assert spec.verify_cell_proof(commitment, cell_id, cells[cell_id], proofs[cell_id])
