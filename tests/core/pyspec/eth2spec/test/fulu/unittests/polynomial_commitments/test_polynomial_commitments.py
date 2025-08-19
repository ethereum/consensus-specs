import random

from eth2spec.test.context import (
    expect_assertion_error,
    single_phase,
    spec_test,
    with_fulu_and_later,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob,
)
from eth2spec.utils.bls import BLS_MODULUS


@with_fulu_and_later
@spec_test
@single_phase
def test_fft(spec):
    # in this test we sample a random polynomial in coefficient form
    # then we apply an FFT to get evaluations over the roots of unity
    # we then apply an inverse FFT to the evaluations to get coefficients

    # we check two things:
    # 1) the original coefficients and the resulting coefficients match
    # 2) the evaluations that we got are the same as if we would have evaluated individually

    rng = random.Random(5566)

    roots_of_unity = spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)

    # sample a random polynomial
    poly_coeff = [
        spec.BLSFieldElement(rng.randint(0, BLS_MODULUS - 1))
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]

    # do an FFT and then an inverse FFT
    poly_eval = spec.fft_field(poly_coeff, roots_of_unity)
    poly_coeff_inversed = spec.fft_field(poly_eval, roots_of_unity, inv=True)

    # first check: inverse FFT after FFT results in original coefficients
    assert len(poly_eval) == len(poly_coeff) == len(poly_coeff_inversed)
    assert poly_coeff_inversed == poly_coeff

    # second check: result of FFT are really the evaluations
    for i, w in enumerate(roots_of_unity):
        individual_evaluation = spec.evaluate_polynomialcoeff(poly_coeff, w)
        assert individual_evaluation == poly_eval[i]


@with_fulu_and_later
@spec_test
@single_phase
def test_coset_fft(spec):
    # in this test we sample a random polynomial in coefficient form
    # then we apply a Coset FFT to get evaluations over the coset of the roots of unity
    # we then apply an inverse Coset FFT to the evaluations to get coefficients

    # we check two things:
    # 1) the original coefficients and the resulting coefficients match
    # 2) the evaluations that we got are the same as if we would have evaluated individually

    rng = random.Random(5566)

    roots_of_unity = spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)

    # this is the shift that generates the coset
    coset_shift = spec.BLSFieldElement(spec.PRIMITIVE_ROOT_OF_UNITY)

    # sample a random polynomial
    poly_coeff = [
        spec.BLSFieldElement(rng.randint(0, BLS_MODULUS - 1))
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]

    # do a coset FFT and then an inverse coset FFT
    poly_eval = spec.coset_fft_field(poly_coeff, roots_of_unity)
    poly_coeff_inversed = spec.coset_fft_field(poly_eval, roots_of_unity, inv=True)

    # first check: inverse coset FFT after coset FFT results in original coefficients
    assert len(poly_eval) == len(poly_coeff) == len(poly_coeff_inversed)
    assert poly_coeff_inversed == poly_coeff

    # second check: result of FFT are really the evaluations over the coset
    for i, w in enumerate(roots_of_unity):
        # the element of the coset is coset_shift * w
        shifted_w = coset_shift * w
        individual_evaluation = spec.evaluate_polynomialcoeff(poly_coeff, shifted_w)
        assert individual_evaluation == poly_eval[i]


@with_fulu_and_later
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
            assert all(a == spec.BLSFieldElement(0) for a in zero_poly_eval_brp[start:end])
        else:  # cell_index in cell_indices
            assert all(a != spec.BLSFieldElement(0) for a in zero_poly_eval_brp[start:end])


@with_fulu_and_later
@spec_test
@single_phase
def test_verify_cell_kzg_proof_batch_zero_cells(spec):
    # Verify with zero cells should return true
    assert spec.verify_cell_kzg_proof_batch(
        commitments_bytes=[],
        cell_indices=[],
        cells=[],
        proofs_bytes=[],
    )


@with_fulu_and_later
@spec_test
@single_phase
def test_verify_cell_kzg_proof_batch(spec):
    # test with a single blob / commitment
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)

    assert len(cells) == len(proofs)

    assert spec.verify_cell_kzg_proof_batch(
        commitments_bytes=[commitment, commitment],
        cell_indices=[0, 4],
        cells=[cells[0], cells[4]],
        proofs_bytes=[proofs[0], proofs[4]],
    )

    # now test with three blobs / commitments
    all_blobs = []
    all_commitments = []
    all_cells = []
    all_proofs = []
    for _ in range(3):
        blob = get_sample_blob(spec)
        commitment = spec.blob_to_kzg_commitment(blob)
        cells, proofs = spec.compute_cells_and_kzg_proofs(blob)

        assert len(cells) == len(proofs)

        all_blobs.append(blob)
        all_commitments.append(commitment)
        all_cells.append(cells)
        all_proofs.append(proofs)

    # the cells of interest
    commitment_indices = [0, 0, 1, 2, 1]
    cell_indices = [0, 4, 0, 1, 2]
    cells = [all_cells[i][j] for (i, j) in zip(commitment_indices, cell_indices)]
    proofs = [all_proofs[i][j] for (i, j) in zip(commitment_indices, cell_indices)]
    commitments = [all_commitments[i] for i in commitment_indices]

    # do the check
    assert spec.verify_cell_kzg_proof_batch(
        commitments_bytes=commitments,
        cell_indices=cell_indices,
        cells=cells,
        proofs_bytes=proofs,
    )


@with_fulu_and_later
@spec_test
@single_phase
def test_verify_cell_kzg_proof_batch_invalid(spec):
    # test with a single blob / commitment
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_kzg_proofs(blob)
    
    assert len(cells) == len(proofs)

    assert not spec.verify_cell_kzg_proof_batch(
        commitments_bytes=[commitment, commitment],
        cell_indices=[0, 4],
        cells=[cells[0], cells[5]],  # Note: this is where it should go wrong
        proofs_bytes=[proofs[0], proofs[4]],
    )

    # now test with three blobs / commitments
    all_blobs = []
    all_commitments = []
    all_cells = []
    all_proofs = []
    for _ in range(3):
        blob = get_sample_blob(spec)
        commitment = spec.blob_to_kzg_commitment(blob)
        cells, proofs = spec.compute_cells_and_kzg_proofs(blob)

        assert len(cells) == len(proofs)

        all_blobs.append(blob)
        all_commitments.append(commitment)
        all_cells.append(cells)
        all_proofs.append(proofs)

    # the cells of interest
    commitment_indices = [0, 0, 1, 2, 1]
    cell_indices = [0, 4, 0, 1, 2]
    cells = [all_cells[i][j] for (i, j) in zip(commitment_indices, cell_indices)]
    proofs = [all_proofs[i][j] for (i, j) in zip(commitment_indices, cell_indices)]
    commitments = [all_commitments[i] for i in commitment_indices]

    # let's change one of the cells. Then it should not verify
    cells[1] = all_cells[1][3]

    # do the check
    assert not spec.verify_cell_kzg_proof_batch(
        commitments_bytes=commitments,
        cell_indices=cell_indices,
        cells=cells,
        proofs_bytes=proofs,
    )


@with_fulu_and_later
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
    # Now the cells themselves
    known_cells = [cells[cell_index] for cell_index in cell_indices]

    # Recover the missing cells and proofs
    recovered_cells, recovered_proofs = spec.recover_cells_and_kzg_proofs(cell_indices, known_cells)
    recovered_data = [x for xs in recovered_cells for x in xs]

    # Check that the original data match the non-extended portion of the recovered data
    blob_byte_array = [b for b in blob]
    assert blob_byte_array == recovered_data[: len(recovered_data) // 2]

    # Check that the recovered cells/proofs match the original cells/proofs
    assert cells == recovered_cells
    assert proofs == recovered_proofs


@with_fulu_and_later
@spec_test
@single_phase
def test_multiply_polynomial_degree_overflow(spec):
    rng = random.Random(5566)

    # Perform a legitimate-but-maxed-out polynomial multiplication
    poly1_coeff = [
        spec.BLSFieldElement(rng.randint(0, BLS_MODULUS - 1))
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]
    poly2_coeff = [
        spec.BLSFieldElement(rng.randint(0, BLS_MODULUS - 1))
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]
    _ = spec.multiply_polynomialcoeff(poly1_coeff, poly2_coeff)

    # Now overflow the degree by pumping the degree of one of the inputs by one
    poly2_coeff = [
        spec.BLSFieldElement(rng.randint(0, BLS_MODULUS - 1))
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB + 1)
    ]
    expect_assertion_error(lambda: spec.multiply_polynomialcoeff(poly1_coeff, poly2_coeff))
