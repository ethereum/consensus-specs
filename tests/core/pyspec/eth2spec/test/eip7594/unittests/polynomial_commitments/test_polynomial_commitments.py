import random
from eth2spec.test.context import (
    spec_test,
    single_phase,
    expect_assertion_error,
    with_eip7594_and_later,
)
from eth2spec.test.helpers.sharding import (
    get_sample_blob,
)
from eth2spec.utils.bls import BLS_MODULUS


@with_eip7594_and_later
@spec_test
@single_phase
def test_fft(spec):
    rng = random.Random(5566)

    roots_of_unity = spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)

    poly_coeff = [rng.randint(0, BLS_MODULUS - 1) for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)]

    poly_eval = spec.fft_field(poly_coeff, roots_of_unity)
    poly_coeff_inversed = spec.fft_field(poly_eval, roots_of_unity, inv=True)

    assert len(poly_eval) == len(poly_coeff) == len(poly_coeff_inversed)
    assert poly_coeff_inversed == poly_coeff


@with_eip7594_and_later
@spec_test
@single_phase
def test_coset_fft(spec):
    rng = random.Random(5566)

    roots_of_unity = spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)

    poly_coeff = [rng.randint(0, BLS_MODULUS - 1) for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)]

    poly_eval = spec.coset_fft_field(poly_coeff, roots_of_unity)
    poly_coeff_inversed = spec.coset_fft_field(poly_eval, roots_of_unity, inv=True)

    assert len(poly_eval) == len(poly_coeff) == len(poly_coeff_inversed)
    assert poly_coeff_inversed == poly_coeff


@with_eip7594_and_later
@spec_test
@single_phase
def test_construct_vanishing_polynomial(spec):
    rng = random.Random(5566)

    num_missing_cells = rng.randint(0, spec.CELLS_PER_EXT_BLOB - 1)
    # Get a unique list of `num_missing_cells` cell indices
    unique_missing_cell_indices = rng.sample(range(spec.CELLS_PER_EXT_BLOB), num_missing_cells)

    zero_poly_coeff = spec.construct_vanishing_polynomial(unique_missing_cell_indices)
    roots_of_unity = spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_EXT_BLOB)
    zero_poly_eval = spec.fft_field(zero_poly_coeff, roots_of_unity)
    zero_poly_eval_brp = spec.bit_reversal_permutation(zero_poly_eval)

    for cell_index in range(spec.CELLS_PER_EXT_BLOB):
        start = cell_index * spec.FIELD_ELEMENTS_PER_CELL
        end = (cell_index + 1) * spec.FIELD_ELEMENTS_PER_CELL
        if cell_index in unique_missing_cell_indices:
            assert all(a == 0 for a in zero_poly_eval_brp[start:end])
        else:  # cell_index in cell_indices
            assert all(a != 0 for a in zero_poly_eval_brp[start:end])


@with_eip7594_and_later
@spec_test
@single_phase
def test_verify_cell_kzg_proof(spec):
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)

    cell_index = 0
    assert spec.verify_cell_kzg_proof(commitment, cell_index, cells[cell_index], proofs[cell_index])
    cell_index = 1
    assert spec.verify_cell_kzg_proof(commitment, cell_index, cells[cell_index], proofs[cell_index])


@with_eip7594_and_later
@spec_test
@single_phase
def test_verify_cell_kzg_proof_batch(spec):
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)

    assert len(cells) == len(proofs)

    assert spec.verify_cell_kzg_proof_batch(
        row_commitments_bytes=[commitment],
        row_indices=[0, 0],
        column_indices=[0, 4],
        cells=[cells[0], cells[4]],
        proofs_bytes=[proofs[0], proofs[4]],
    )


@with_eip7594_and_later
@spec_test
@single_phase
def test_recover_cells_and_kzg_proofs(spec):
    rng = random.Random(5566)

    # Number of samples we will be recovering from
    N_SAMPLES = spec.CELLS_PER_EXT_BLOB // 2

    # Get the data we will be working with
    blob = get_sample_blob(spec)

    # Extend data with Reed-Solomon and split the extended data in cells
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)

    # Compute the cells we will be recovering from
    cell_indices = []
    # First figure out just the indices of the cells
    for i in range(N_SAMPLES):
        j = rng.randint(0, spec.CELLS_PER_EXT_BLOB - 1)
        while j in cell_indices:
            j = rng.randint(0, spec.CELLS_PER_EXT_BLOB - 1)
        cell_indices.append(j)
    # Now the cells/proofs themselves
    known_cells = [cells[cell_index] for cell_index in cell_indices]
    known_proofs = [proofs[cell_index] for cell_index in cell_indices]

    # Recover the missing cells and proofs
    recovered_cells, recovered_proofs = spec.recover_cells_and_kzg_proofs(cell_indices, known_cells, known_proofs)
    recovered_data = [x for xs in recovered_cells for x in xs]

    # Check that the original data match the non-extended portion of the recovered data
    blob_byte_array = [b for b in blob]
    assert blob_byte_array == recovered_data[:len(recovered_data) // 2]

    # Check that the recovered cells/proofs match the original cells/proofs
    assert cells == recovered_cells
    assert proofs == recovered_proofs


@with_eip7594_and_later
@spec_test
@single_phase
def test_multiply_polynomial_degree_overflow(spec):
    rng = random.Random(5566)

    # Perform a legitimate-but-maxed-out polynomial multiplication
    poly1_coeff = [rng.randint(0, BLS_MODULUS - 1) for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)]
    poly2_coeff = [rng.randint(0, BLS_MODULUS - 1) for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)]
    _ = spec.multiply_polynomialcoeff(poly1_coeff, poly2_coeff)

    # Now overflow the degree by pumping the degree of one of the inputs by one
    poly2_coeff = [rng.randint(0, BLS_MODULUS - 1) for _ in range(spec.FIELD_ELEMENTS_PER_BLOB + 1)]
    expect_assertion_error(lambda: spec.multiply_polynomialcoeff(poly1_coeff, poly2_coeff))
