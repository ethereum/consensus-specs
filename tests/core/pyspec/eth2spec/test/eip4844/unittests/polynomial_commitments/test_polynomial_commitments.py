from eth2spec.test.context import (
    spec_state_test,
    with_eip4844_and_later,
)
from eth2spec.test.helpers.sharding import (
    get_sample_blob,
)


@with_eip4844_and_later
@spec_state_test
def test_verify_kzg_proof(spec, state):
    x = 3
    blob = get_sample_blob(spec)
    commitment = spec.blob_to_kzg_commitment(blob)
    polynomial = spec.blob_to_polynomial(blob)
    proof = spec.compute_kzg_proof(polynomial, x)

    y = spec.evaluate_polynomial_in_evaluation_form(polynomial, x)
    assert spec.verify_kzg_proof(commitment, x, y, proof)
