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
def test_reverse_bits_limited(spec):
    rng = random.Random(5566)
    for exp in range(64):
        length = 2**exp
        value = rng.randrange(0, length)
        assert value == spec.reverse_bits_limited(length, spec.reverse_bits_limited(length, value))


@with_eip7594_and_later
@spec_test
@single_phase
def test_verify_cell_proof(spec):
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_proofs(blob)
    cells_bytes = [[field_element_bytes(element) for element in cell] for cell in cells]
    for cell_id in range(spec.CELLS_PER_BLOB):
        assert spec.verify_cell_proof(commitment, cell_id, cells_bytes[cell_id], proofs[cell_id])


@with_eip7594_and_later
@spec_test
@single_phase
def test_verify_cell_proof_batch(spec):
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    cells, proofs = spec.compute_cells_and_proofs(blob)
    cells_bytes = [[spec.bls_field_to_bytes(element) for element in cell] for cell in cells]

    assert len(cells) == len(proofs)

    assert spec.verify_cell_proof_batch(
        row_commitments_bytes=[commitment],
        row_indices=[0, 0],
        column_indices=[0, 4],
        cells_bytes=[cells_bytes[0], cells_bytes[4]],
        proofs_bytes=[proofs[0], proofs[4]],
    )


@with_eip7594_and_later
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
    cells_bytes = [[spec.bls_field_to_bytes(element) for element in cell] for cell in cells]

    # Compute the cells we will be recovering from
    cell_ids = []
    # First figure out just the indices of the cells
    for i in range(N_SAMPLES):
        j = rng.randint(0, spec.CELLS_PER_BLOB - 1)
        while j in cell_ids:
            j = rng.randint(0, spec.CELLS_PER_BLOB - 1)
        cell_ids.append(j)
    # Now the cells themselves
    known_cells_bytes = [cells_bytes[cell_id] for cell_id in cell_ids]

    # Recover the data
    recovered_data = spec.recover_polynomial(cell_ids, known_cells_bytes)

    # Check that the original data match the non-extended portion of the recovered data
    assert original_polynomial == recovered_data[:len(recovered_data) // 2]

    # Now flatten the cells and check that they match the entirety of the recovered data
    flattened_cells = [x for xs in cells for x in xs]
    assert flattened_cells == recovered_data


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
