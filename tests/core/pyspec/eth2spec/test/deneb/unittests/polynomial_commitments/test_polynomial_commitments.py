import random

from eth2spec.test.context import (
    spec_state_test,
    with_deneb_and_later,
)
from eth2spec.test.helpers.sharding import (
    get_sample_blob,
    get_poly_in_both_forms,
    eval_poly_in_coeff_form,
)


@with_deneb_and_later
@spec_state_test
def test_verify_kzg_proof(spec, state):
    x = 3
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    polynomial = spec.blob_to_polynomial(blob)
    proof = spec.compute_kzg_proof_impl(polynomial, x)

    y = spec.evaluate_polynomial_in_evaluation_form(polynomial, x)
    assert spec.verify_kzg_proof_impl(commitment, x, y, proof)


@with_deneb_and_later
@spec_state_test
def test_barycentric_outside_domain(spec, state):
    """
    Test barycentric formula correctness by using it to evaluate a polynomial at a bunch of points outside its domain
    (the roots of unity).

    Then make sure that we would get the same result if we evaluated it from coefficient form without using the
    barycentric formula
    """
    rng = random.Random(5566)
    poly_coeff, poly_eval = get_poly_in_both_forms(spec)
    roots_of_unity_brp = spec.bit_reversal_permutation(spec.ROOTS_OF_UNITY)

    assert len(poly_coeff) == len(poly_eval) == len(roots_of_unity_brp)
    n_samples = 12

    for _ in range(n_samples):
        # Get a random evaluation point and make sure it's not a root of unity
        z = rng.randint(0, spec.BLS_MODULUS - 1)
        while z in roots_of_unity_brp:
            z = rng.randint(0, spec.BLS_MODULUS - 1)

        # Get p(z) by evaluating poly in coefficient form
        p_z_coeff = eval_poly_in_coeff_form(spec, poly_coeff, z)

        # Get p(z) by evaluating poly in evaluation form
        p_z_eval = spec.evaluate_polynomial_in_evaluation_form(poly_eval, z)

        # Both evaluations should agree
        assert p_z_coeff == p_z_eval


@with_deneb_and_later
@spec_state_test
def test_barycentric_within_domain(spec, state):
    """
    Test barycentric formula correctness by using it to evaluate a polynomial at all the points of its domain
    (the roots of unity).

    Then make sure that we would get the same result if we evaluated it from coefficient form without using the
    barycentric formula
    """
    poly_coeff, poly_eval = get_poly_in_both_forms(spec)
    roots_of_unity_brp = spec.bit_reversal_permutation(spec.ROOTS_OF_UNITY)

    assert len(poly_coeff) == len(poly_eval) == len(roots_of_unity_brp)
    n = len(poly_coeff)

    # Iterate over the entire domain
    for i in range(n):
        # Grab a root of unity and use it as the evaluation point
        z = int(roots_of_unity_brp[i])

        # Get p(z) by evaluating poly in coefficient form
        p_z_coeff = eval_poly_in_coeff_form(spec, poly_coeff, z)

        # Get p(z) by evaluating poly in evaluation form
        p_z_eval = spec.evaluate_polynomial_in_evaluation_form(poly_eval, z)

        # The two evaluations should be agree and p(z) should also be the i-th "coefficient" of the polynomial in
        # evaluation form
        assert p_z_coeff == p_z_eval == poly_eval[i]


@with_deneb_and_later
@spec_state_test
def test_compute_kzg_proof_within_domain(spec, state):
    """
    Create and verify KZG proof that p(z) == y
    where z is in the domain of our KZG scheme (i.e. a relevant root of unity).
    """
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    polynomial = spec.blob_to_polynomial(blob)

    roots_of_unity_brp = spec.bit_reversal_permutation(spec.ROOTS_OF_UNITY)

    for i, z in enumerate(roots_of_unity_brp):
        proof = spec.compute_kzg_proof_impl(polynomial, z)

        y = spec.evaluate_polynomial_in_evaluation_form(polynomial, z)
        assert spec.verify_kzg_proof_impl(commitment, z, y, proof)
