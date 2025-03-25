import random

from eth2spec.test.context import (
    spec_test,
    single_phase,
    with_deneb_and_later,
    expect_assertion_error,
    always_bls,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob,
    get_poly_in_both_forms,
    eval_poly_in_coeff_form,
)
from eth2spec.utils import bls
from eth2spec.utils.bls import BLS_MODULUS

G1 = bls.G1_to_bytes48(bls.G1())
P1_NOT_IN_G1 = bytes.fromhex(
    "8123456789abcdef0123456789abcdef0123456789abcdef"
    + "0123456789abcdef0123456789abcdef0123456789abcdef"
)
P1_NOT_ON_CURVE = bytes.fromhex(
    "8123456789abcdef0123456789abcdef0123456789abcdef"
    + "0123456789abcdef0123456789abcdef0123456789abcde0"
)


def bls_add_one(x):
    """
    Adds "one" (actually bls.G1()) to a compressed group element.
    Useful to compute definitely incorrect proofs.
    """
    return bls.G1_to_bytes48(bls.add(bls.bytes48_to_G1(x), bls.G1()))


@with_deneb_and_later
@spec_test
@single_phase
def test_verify_kzg_proof(spec):
    """
    Test the wrapper functions (taking bytes arguments) for computing and verifying KZG proofs.
    """
    x = spec.bls_field_to_bytes(spec.BLSFieldElement(3))
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    proof, y = spec.compute_kzg_proof(blob, x)

    assert spec.verify_kzg_proof(commitment, x, y, proof)


@with_deneb_and_later
@spec_test
@single_phase
def test_verify_kzg_proof_incorrect_proof(spec):
    """
    Test the wrapper function `verify_kzg_proof` fails on an incorrect proof.
    """
    x = spec.bls_field_to_bytes(spec.BLSFieldElement(3465))
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    proof, y = spec.compute_kzg_proof(blob, x)
    proof = bls_add_one(proof)

    assert not spec.verify_kzg_proof(commitment, x, y, proof)


@with_deneb_and_later
@spec_test
@single_phase
def test_verify_kzg_proof_impl(spec):
    """
    Test the implementation functions (taking field element arguments) for computing and verifying KZG proofs.
    """
    x = spec.BLSFieldElement(BLS_MODULUS - 1)
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    polynomial = spec.blob_to_polynomial(blob)
    proof, y = spec.compute_kzg_proof_impl(polynomial, x)

    assert spec.verify_kzg_proof_impl(commitment, x, y, proof)


@with_deneb_and_later
@spec_test
@single_phase
def test_verify_kzg_proof_impl_incorrect_proof(spec):
    """
    Test the implementation function `verify_kzg_proof` fails on an incorrect proof.
    """
    x = spec.BLSFieldElement(324561)
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    polynomial = spec.blob_to_polynomial(blob)
    proof, y = spec.compute_kzg_proof_impl(polynomial, x)
    proof = bls_add_one(proof)

    assert not spec.verify_kzg_proof_impl(commitment, x, y, proof)


@with_deneb_and_later
@spec_test
@single_phase
def test_barycentric_outside_domain(spec):
    """
    Test barycentric formula correctness by using it to evaluate a polynomial at a bunch of points outside its domain
    (the roots of unity).

    Then make sure that we would get the same result if we evaluated it from coefficient form without using the
    barycentric formula
    """
    rng = random.Random(5566)
    poly_coeff, poly_eval = get_poly_in_both_forms(spec)
    roots_of_unity_brp = spec.bit_reversal_permutation(
        spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)
    )

    assert len(poly_coeff) == len(poly_eval) == len(roots_of_unity_brp)
    n_samples = 12

    for _ in range(n_samples):
        # Get a random evaluation point and make sure it's not a root of unity
        z = spec.BLSFieldElement(rng.randint(0, BLS_MODULUS - 1))
        while z in roots_of_unity_brp:
            z = spec.BLSFieldElement(rng.randint(0, BLS_MODULUS - 1))

        # Get p(z) by evaluating poly in coefficient form
        p_z_coeff = eval_poly_in_coeff_form(spec, poly_coeff, z)

        # Get p(z) by evaluating poly in evaluation form
        p_z_eval = spec.evaluate_polynomial_in_evaluation_form(poly_eval, z)

        # Both evaluations should agree
        assert p_z_coeff == p_z_eval


@with_deneb_and_later
@spec_test
@single_phase
def test_barycentric_within_domain(spec):
    """
    Test barycentric formula correctness by using it to evaluate a polynomial at various points inside its domain
    (the roots of unity).

    Then make sure that we would get the same result if we evaluated it from coefficient form without using the
    barycentric formula
    """
    rng = random.Random(5566)
    poly_coeff, poly_eval = get_poly_in_both_forms(spec)
    roots_of_unity_brp = spec.bit_reversal_permutation(
        spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)
    )

    assert len(poly_coeff) == len(poly_eval) == len(roots_of_unity_brp)
    n = len(poly_coeff)

    # Iterate over some roots of unity
    for i in range(12):
        i = rng.randint(0, n - 1)
        # Grab a root of unity and use it as the evaluation point
        z = roots_of_unity_brp[i]

        # Get p(z) by evaluating poly in coefficient form
        p_z_coeff = eval_poly_in_coeff_form(spec, poly_coeff, z)

        # Get p(z) by evaluating poly in evaluation form
        p_z_eval = spec.evaluate_polynomial_in_evaluation_form(poly_eval, z)

        # The two evaluations should be agree and p(z) should also be the i-th "coefficient" of the polynomial in
        # evaluation form
        assert p_z_coeff == p_z_eval == poly_eval[i]


@with_deneb_and_later
@spec_test
@single_phase
def test_compute_kzg_proof_within_domain(spec):
    """
    Create and verify KZG proof that p(z) == y
    where z is in the domain of our KZG scheme (i.e. a relevant root of unity).
    """
    rng = random.Random(5566)
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    polynomial = spec.blob_to_polynomial(blob)

    roots_of_unity_brp = spec.bit_reversal_permutation(
        spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)
    )

    # Let's test some roots of unity
    for _ in range(6):
        z = rng.choice(roots_of_unity_brp)
        proof, y = spec.compute_kzg_proof_impl(polynomial, z)
        assert spec.verify_kzg_proof_impl(commitment, z, y, proof)


@with_deneb_and_later
@spec_test
@single_phase
def test_verify_blob_kzg_proof(spec):
    """
    Test the functions to compute and verify a blob KZG proof
    """
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.compute_blob_kzg_proof(blob, commitment)

    assert spec.verify_blob_kzg_proof(blob, commitment, proof)


@with_deneb_and_later
@spec_test
@single_phase
def test_verify_blob_kzg_proof_incorrect_proof(spec):
    """
    Check that `verify_blob_kzg_proof` fails on an incorrect proof
    """
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.compute_blob_kzg_proof(blob, commitment)
    proof = bls_add_one(proof)

    assert not spec.verify_blob_kzg_proof(blob, commitment, proof)


@with_deneb_and_later
@spec_test
@single_phase
def test_validate_kzg_g1_generator(spec):
    """
    Verify that `validate_kzg_g1` allows the generator G1
    """

    spec.validate_kzg_g1(bls.G1_to_bytes48(bls.G1()))


@with_deneb_and_later
@spec_test
@single_phase
def test_validate_kzg_g1_neutral_element(spec):
    """
    Verify that `validate_kzg_g1` allows the neutral element in G1
    """

    spec.validate_kzg_g1(bls.G1_to_bytes48(bls.Z1()))


@with_deneb_and_later
@spec_test
@single_phase
@always_bls
def test_validate_kzg_g1_not_in_g1(spec):
    """
    Verify that `validate_kzg_g1` fails on point not in G1
    """

    expect_assertion_error(lambda: spec.validate_kzg_g1(P1_NOT_IN_G1))


@with_deneb_and_later
@spec_test
@single_phase
@always_bls
def test_validate_kzg_g1_not_on_curve(spec):
    """
    Verify that `validate_kzg_g1` fails on point not in G1
    """

    expect_assertion_error(lambda: spec.validate_kzg_g1(P1_NOT_ON_CURVE))


@with_deneb_and_later
@spec_test
@single_phase
def test_bytes_to_bls_field_zero(spec):
    """
    Verify that `bytes_to_bls_field` handles zero
    """

    spec.bytes_to_bls_field(b"\0" * 32)


@with_deneb_and_later
@spec_test
@single_phase
def test_bytes_to_bls_field_modulus_minus_one(spec):
    """
    Verify that `bytes_to_bls_field` handles modulus minus one
    """

    spec.bytes_to_bls_field(
        (BLS_MODULUS - 1).to_bytes(spec.BYTES_PER_FIELD_ELEMENT, spec.KZG_ENDIANNESS)
    )


@with_deneb_and_later
@spec_test
@single_phase
def test_bytes_to_bls_field_modulus(spec):
    """
    Verify that `bytes_to_bls_field` fails on BLS modulus
    """

    expect_assertion_error(
        lambda: spec.bytes_to_bls_field(
            BLS_MODULUS.to_bytes(spec.BYTES_PER_FIELD_ELEMENT, spec.KZG_ENDIANNESS)
        )
    )


@with_deneb_and_later
@spec_test
@single_phase
def test_bytes_to_bls_field_max(spec):
    """
    Verify that `bytes_to_bls_field` fails on 2**256 - 1
    """

    expect_assertion_error(lambda: spec.bytes_to_bls_field(b"\xFF" * 32))
