# EIP-4844 -- Polynomial Commitments

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Preset](#preset)
  - [Blob](#blob)
  - [Crypto](#crypto)
  - [Trusted setup](#trusted-setup)
- [Helper functions](#helper-functions)
  - [Bit-reversal permutation](#bit-reversal-permutation)
    - [`is_power_of_two`](#is_power_of_two)
    - [`reverse_bits`](#reverse_bits)
    - [`bit_reversal_permutation`](#bit_reversal_permutation)
  - [BLS12-381 helpers](#bls12-381-helpers)
    - [`hash_to_bls_field`](#hash_to_bls_field)
    - [`bytes_to_bls_field`](#bytes_to_bls_field)
    - [`validate_kzg_g1`](#validate_kzg_g1)
    - [`bytes_to_kzg_commitment`](#bytes_to_kzg_commitment)
    - [`bytes_to_kzg_proof`](#bytes_to_kzg_proof)
    - [`blob_to_polynomial`](#blob_to_polynomial)
    - [`compute_challenges`](#compute_challenges)
    - [`bls_modular_inverse`](#bls_modular_inverse)
    - [`div`](#div)
    - [`g1_lincomb`](#g1_lincomb)
    - [`poly_lincomb`](#poly_lincomb)
    - [`compute_powers`](#compute_powers)
  - [Polynomials](#polynomials)
    - [`evaluate_polynomial_in_evaluation_form`](#evaluate_polynomial_in_evaluation_form)
  - [KZG](#kzg)
    - [`blob_to_kzg_commitment`](#blob_to_kzg_commitment)
    - [`verify_kzg_proof`](#verify_kzg_proof)
    - [`verify_kzg_proof_impl`](#verify_kzg_proof_impl)
    - [`compute_kzg_proof`](#compute_kzg_proof)
    - [`compute_kzg_proof_impl`](#compute_kzg_proof_impl)
    - [`compute_aggregated_poly_and_commitment`](#compute_aggregated_poly_and_commitment)
    - [`compute_aggregate_kzg_proof`](#compute_aggregate_kzg_proof)
    - [`verify_aggregate_kzg_proof`](#verify_aggregate_kzg_proof)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document specifies basic polynomial operations and KZG polynomial commitment operations as they are needed for the EIP-4844 specification. The implementations are not optimized for performance, but readability. All practical implementations should optimize the polynomial operations.

Functions flagged as "Public method" MUST be provided by the underlying KZG library as public functions. All other functions are private functions used internally by the KZG library.

Public functions MUST accept raw bytes as input and perform the required cryptographic normalization before invoking any internal functions.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `G1Point` | `Bytes48` | |
| `G2Point` | `Bytes96` | |
| `BLSFieldElement` | `uint256` | Validation: `x < BLS_MODULUS` |
| `KZGCommitment` | `Bytes48` | Validation: Perform [BLS standard's](https://datatracker.ietf.org/doc/html/draft-irtf-cfrg-bls-signature-04#section-2.5) "KeyValidate" check but do allow the identity point |
| `KZGProof` | `Bytes48` | Same as for `KZGCommitment` |
| `Polynomial` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_BLOB]` | A polynomial in evaluation form |
| `Blob` | `ByteVector[BYTES_PER_FIELD_ELEMENT * FIELD_ELEMENTS_PER_BLOB]` | A basic blob data |

## Constants

| Name | Value | Notes |
| - | - | - |
| `BLS_MODULUS` | `52435875175126190479447740508185965837690552500527637822603658699938581184513` | Scalar field modulus of BLS12-381 |
| `BYTES_PER_FIELD_ELEMENT` | `uint64(32)` | Bytes used to encode a BLS scalar field element |
| `G1_POINT_AT_INFINITY` | `Bytes48(b'\xc0' + b'\x00' * 47)` | Serialized form of the point at infinity on the G1 group |


## Preset

### Blob

| Name | Value |
| - | - |
| `FIELD_ELEMENTS_PER_BLOB` | `uint64(4096)` |
| `FIAT_SHAMIR_PROTOCOL_DOMAIN` | `b'FSBLOBVERIFY_V1_'` |

### Crypto

| Name | Value | Notes |
| - | - | - |
| `ROOTS_OF_UNITY` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_BLOB]` | Roots of unity of order FIELD_ELEMENTS_PER_BLOB over the BLS12-381 field |

### Trusted setup

The trusted setup is part of the preset: during testing a `minimal` insecure variant may be used,
but reusing the `mainnet` settings in public networks is a critical security requirement.

| Name | Value |
| - | - |
| `KZG_SETUP_G2_LENGTH` | `65` |
| `KZG_SETUP_G1` | `Vector[G1Point, FIELD_ELEMENTS_PER_BLOB]`, contents TBD |
| `KZG_SETUP_G2` | `Vector[G2Point, KZG_SETUP_G2_LENGTH]`, contents TBD |
| `KZG_SETUP_LAGRANGE` | `Vector[KZGCommitment, FIELD_ELEMENTS_PER_BLOB]`, contents TBD |

## Helper functions

### Bit-reversal permutation

All polynomials (which are always given in Lagrange form) should be interpreted as being in
bit-reversal permutation. In practice, clients can implement this by storing the lists
`KZG_SETUP_LAGRANGE` and `ROOTS_OF_UNITY` in bit-reversal permutation, so these functions only
have to be called once at startup.

#### `is_power_of_two`

```python
def is_power_of_two(value: int) -> bool:
    """
    Check if ``value`` is a power of two integer.
    """
    return (value > 0) and (value & (value - 1) == 0)
```

#### `reverse_bits`

```python
def reverse_bits(n: int, order: int) -> int:
    """
    Reverse the bit order of an integer ``n``.
    """
    assert is_power_of_two(order)
    # Convert n to binary with the same number of bits as "order" - 1, then reverse its bit order
    return int(('{:0' + str(order.bit_length() - 1) + 'b}').format(n)[::-1], 2)
```

#### `bit_reversal_permutation`

```python
def bit_reversal_permutation(sequence: Sequence[T]) -> Sequence[T]:
    """
    Return a copy with bit-reversed permutation. The permutation is an involution (inverts itself).

    The input and output are a sequence of generic type ``T`` objects.
    """
    return [sequence[reverse_bits(i, len(sequence))] for i in range(len(sequence))]
```

### BLS12-381 helpers

#### `hash_to_bls_field`

```python
def hash_to_bls_field(data: bytes) -> BLSFieldElement:
    """
    Hash ``data`` and convert the output to a BLS scalar field element.
    The output is not uniform over the BLS field.
    """
    hashed_data = hash(data)
    return BLSFieldElement(int.from_bytes(hashed_data, ENDIANNESS) % BLS_MODULUS)
```

#### `bytes_to_bls_field`

```python
def bytes_to_bls_field(b: Bytes32) -> BLSFieldElement:
    """
    Convert untrusted bytes to a trusted and validated BLS scalar field element.
    This function does not accept inputs greater than the BLS modulus.
    """
    field_element = int.from_bytes(b, ENDIANNESS)
    assert field_element < BLS_MODULUS
    return BLSFieldElement(field_element)
```


#### `validate_kzg_g1`

```python
def validate_kzg_g1(b: Bytes48) -> None:
    """
    Perform BLS validation required by the types `KZGProof` and `KZGCommitment`.
    """
    if b == G1_POINT_AT_INFINITY:
        return

    assert bls.KeyValidate(b)
```

#### `bytes_to_kzg_commitment`

```python
def bytes_to_kzg_commitment(b: Bytes48) -> KZGCommitment:
    """
    Convert untrusted bytes into a trusted and validated KZGCommitment.
    """
    validate_kzg_g1(b)
    return KZGCommitment(b)
```

#### `bytes_to_kzg_proof`

```python
def bytes_to_kzg_proof(b: Bytes48) -> KZGProof:
    """
    Convert untrusted bytes into a trusted and validated KZGProof.
    """
    validate_kzg_g1(b)
    return KZGProof(b)
```

#### `blob_to_polynomial`

```python
def blob_to_polynomial(blob: Blob) -> Polynomial:
    """
    Convert a blob to list of BLS field scalars.
    """
    polynomial = Polynomial()
    for i in range(FIELD_ELEMENTS_PER_BLOB):
        value = bytes_to_bls_field(blob[i * BYTES_PER_FIELD_ELEMENT: (i + 1) * BYTES_PER_FIELD_ELEMENT])
        polynomial[i] = value
    return polynomial
```

#### `compute_challenges`

```python
def compute_challenges(polynomials: Sequence[Polynomial],
                       commitments: Sequence[KZGCommitment]) -> Tuple[Sequence[BLSFieldElement], BLSFieldElement]:
    """
    Return the Fiat-Shamir challenges required by the rest of the protocol.
    The Fiat-Shamir logic works as per the following pseudocode:

       hashed_data = hash(DOMAIN_SEPARATOR, polynomials, commitments)
       r = hash(hashed_data, 0)
       r_powers = [1, r, r**2, r**3, ...]
       eval_challenge = hash(hashed_data, 1)

    Then return `r_powers` and `eval_challenge` after converting them to BLS field elements.
    The resulting field elements are not uniform over the BLS field.
    """
    # Append the number of polynomials and the degree of each polynomial as a domain separator
    num_polynomials = int.to_bytes(len(polynomials), 8, ENDIANNESS)
    degree_poly = int.to_bytes(FIELD_ELEMENTS_PER_BLOB, 8, ENDIANNESS)
    data = FIAT_SHAMIR_PROTOCOL_DOMAIN + degree_poly + num_polynomials

    # Append each polynomial which is composed by field elements
    for poly in polynomials:
        for field_element in poly:
            data += int.to_bytes(field_element, BYTES_PER_FIELD_ELEMENT, ENDIANNESS)

    # Append serialized G1 points
    for commitment in commitments:
        data += commitment

    # Transcript has been prepared: time to create the challenges
    hashed_data = hash(data)
    r = hash_to_bls_field(hashed_data + b'\x00')
    r_powers = compute_powers(r, len(commitments))
    eval_challenge = hash_to_bls_field(hashed_data + b'\x01')

    return r_powers, eval_challenge
```

#### `bls_modular_inverse`

```python
def bls_modular_inverse(x: BLSFieldElement) -> BLSFieldElement:
    """
    Compute the modular inverse of x
    i.e. return y such that x * y % BLS_MODULUS == 1 and return 0 for x == 0
    """
    return BLSFieldElement(pow(x, -1, BLS_MODULUS)) if x != 0 else BLSFieldElement(0)
```

#### `div`

```python
def div(x: BLSFieldElement, y: BLSFieldElement) -> BLSFieldElement:
    """
    Divide two field elements: ``x`` by `y``.
    """
    return BLSFieldElement((int(x) * int(bls_modular_inverse(y))) % BLS_MODULUS)
```

#### `g1_lincomb`

```python
def g1_lincomb(points: Sequence[KZGCommitment], scalars: Sequence[BLSFieldElement]) -> KZGCommitment:
    """
    BLS multiscalar multiplication. This function can be optimized using Pippenger's algorithm and variants.
    """
    assert len(points) == len(scalars)
    result = bls.Z1
    for x, a in zip(points, scalars):
        result = bls.add(result, bls.multiply(bls.bytes48_to_G1(x), a))
    return KZGCommitment(bls.G1_to_bytes48(result))
```

#### `poly_lincomb`

```python
def poly_lincomb(polys: Sequence[Polynomial],
                 scalars: Sequence[BLSFieldElement]) -> Polynomial:
    """
    Given a list of ``polynomials``, interpret it as a 2D matrix and compute the linear combination
    of each column with `scalars`: return the resulting polynomials.
    """
    assert len(polys) == len(scalars)
    result = [0] * FIELD_ELEMENTS_PER_BLOB
    for v, s in zip(polys, scalars):
        for i, x in enumerate(v):
            result[i] = (result[i] + int(s) * int(x)) % BLS_MODULUS
    return Polynomial([BLSFieldElement(x) for x in result])
```

#### `compute_powers`

```python
def compute_powers(x: BLSFieldElement, n: uint64) -> Sequence[BLSFieldElement]:
    """
    Return ``x`` to power of [0, n-1], if n > 0. When n==0, an empty array is returned.
    """
    current_power = 1
    powers = []
    for _ in range(n):
        powers.append(BLSFieldElement(current_power))
        current_power = current_power * int(x) % BLS_MODULUS
    return powers
```


### Polynomials

#### `evaluate_polynomial_in_evaluation_form`

```python
def evaluate_polynomial_in_evaluation_form(polynomial: Polynomial,
                                           z: BLSFieldElement) -> BLSFieldElement:
    """
    Evaluate a polynomial (in evaluation form) at an arbitrary point ``z`` that is not in the domain.
    Uses the barycentric formula:
       f(z) = (z**WIDTH - 1) / WIDTH  *  sum_(i=0)^WIDTH  (f(DOMAIN[i]) * DOMAIN[i]) / (z - DOMAIN[i])
    """
    width = len(polynomial)
    assert width == FIELD_ELEMENTS_PER_BLOB
    inverse_width = bls_modular_inverse(BLSFieldElement(width))

    roots_of_unity_brp = bit_reversal_permutation(ROOTS_OF_UNITY)

    # If we are asked to evaluate within the domain, we already know the answer
    if z in roots_of_unity_brp:
        eval_index = roots_of_unity_brp.index(z)
        return BLSFieldElement(polynomial[eval_index])

    result = 0
    for i in range(width):
        a = BLSFieldElement(int(polynomial[i]) * int(roots_of_unity_brp[i]) % BLS_MODULUS)
        b = BLSFieldElement((int(BLS_MODULUS) + int(z) - int(roots_of_unity_brp[i])) % BLS_MODULUS)
        result += int(div(a, b) % BLS_MODULUS)
    result = result * int(pow(z, width, BLS_MODULUS) - 1) * int(inverse_width)
    return BLSFieldElement(result % BLS_MODULUS)
```

### KZG

KZG core functions. These are also defined in EIP-4844 execution specs.

#### `blob_to_kzg_commitment`

```python
def blob_to_kzg_commitment(blob: Blob) -> KZGCommitment:
    """
    Public method.
    """
    return g1_lincomb(bit_reversal_permutation(KZG_SETUP_LAGRANGE), blob_to_polynomial(blob))
```

#### `verify_kzg_proof`

```python
def verify_kzg_proof(commitment_bytes: Bytes48,
                     z: Bytes32,
                     y: Bytes32,
                     proof_bytes: Bytes48) -> bool:
    """
    Verify KZG proof that ``p(z) == y`` where ``p(z)`` is the polynomial represented by ``polynomial_kzg``.
    Receives inputs as bytes.
    Public method.
    """
    return verify_kzg_proof_impl(bytes_to_kzg_commitment(commitment_bytes),
                                 bytes_to_bls_field(z),
                                 bytes_to_bls_field(y),
                                 bytes_to_kzg_proof(proof_bytes))
```


#### `verify_kzg_proof_impl`

```python
def verify_kzg_proof_impl(commitment: KZGCommitment,
                          z: BLSFieldElement,
                          y: BLSFieldElement,
                          proof: KZGProof) -> bool:
    """
    Verify KZG proof that ``p(z) == y`` where ``p(z)`` is the polynomial represented by ``polynomial_kzg``.
    """
    # Verify: P - y = Q * (X - z)
    X_minus_z = bls.add(bls.bytes96_to_G2(KZG_SETUP_G2[1]), bls.multiply(bls.G2, BLS_MODULUS - z))
    P_minus_y = bls.add(bls.bytes48_to_G1(commitment), bls.multiply(bls.G1, BLS_MODULUS - y))
    return bls.pairing_check([
        [P_minus_y, bls.neg(bls.G2)],
        [bls.bytes48_to_G1(proof), X_minus_z]
    ])
```

#### `compute_kzg_proof`

```python
def compute_kzg_proof(blob: Blob, z: Bytes32) -> KZGProof:
    """
    Compute KZG proof at point `z` for the polynomial represented by `blob`.
    Do this by computing the quotient polynomial in evaluation form: q(x) = (p(x) - p(z)) / (x - z).
    Public method.
    """
    polynomial = blob_to_polynomial(blob)
    return compute_kzg_proof_impl(polynomial, bytes_to_bls_field(z))
```

#### `compute_kzg_proof_impl`

```python
def compute_kzg_proof_impl(polynomial: Polynomial, z: BLSFieldElement) -> KZGProof:
    """
    Helper function for compute_kzg_proof() and compute_aggregate_kzg_proof().
    """
    y = evaluate_polynomial_in_evaluation_form(polynomial, z)
    polynomial_shifted = [BLSFieldElement((int(p) - int(y)) % BLS_MODULUS) for p in polynomial]

    # Make sure we won't divide by zero during division
    assert z not in ROOTS_OF_UNITY
    denominator_poly = [BLSFieldElement((int(x) - int(z)) % BLS_MODULUS)
                        for x in bit_reversal_permutation(ROOTS_OF_UNITY)]

    # Calculate quotient polynomial by doing point-by-point division
    quotient_polynomial = [div(a, b) for a, b in zip(polynomial_shifted, denominator_poly)]
    return KZGProof(g1_lincomb(bit_reversal_permutation(KZG_SETUP_LAGRANGE), quotient_polynomial))
```

#### `compute_aggregated_poly_and_commitment`

```python
def compute_aggregated_poly_and_commitment(
        blobs: Sequence[Blob],
        kzg_commitments: Sequence[KZGCommitment]) -> Tuple[Polynomial, KZGCommitment, BLSFieldElement]:
    """
    Return (1) the aggregated polynomial, (2) the aggregated KZG commitment,
    and (3) the polynomial evaluation random challenge.
    This function should also work with blobs == [] and kzg_commitments == []
    """
    assert len(blobs) == len(kzg_commitments)

    # Convert blobs to polynomials
    polynomials = [blob_to_polynomial(blob) for blob in blobs]

    # Generate random linear combination and evaluation challenges
    r_powers, evaluation_challenge = compute_challenges(polynomials, kzg_commitments)

    # Create aggregated polynomial in evaluation form
    aggregated_poly = poly_lincomb(polynomials, r_powers)

    # Compute commitment to aggregated polynomial
    aggregated_poly_commitment = KZGCommitment(g1_lincomb(kzg_commitments, r_powers))

    return aggregated_poly, aggregated_poly_commitment, evaluation_challenge
```

#### `compute_aggregate_kzg_proof`

```python
def compute_aggregate_kzg_proof(blobs: Sequence[Blob]) -> KZGProof:
    """
    Given a list of blobs, return the aggregated KZG proof that is used to verify them against their commitments.
    Public method.
    """
    commitments = [blob_to_kzg_commitment(blob) for blob in blobs]
    aggregated_poly, aggregated_poly_commitment, evaluation_challenge = compute_aggregated_poly_and_commitment(
        blobs,
        commitments
    )
    return compute_kzg_proof_impl(aggregated_poly, evaluation_challenge)
```

#### `verify_aggregate_kzg_proof`

```python
def verify_aggregate_kzg_proof(blobs: Sequence[Blob],
                               commitments_bytes: Sequence[Bytes48],
                               aggregated_proof_bytes: Bytes48) -> bool:
    """
    Given a list of blobs and an aggregated KZG proof, verify that they correspond to the provided commitments.

    Public method.
    """
    commitments = [bytes_to_kzg_commitment(c) for c in commitments_bytes]

    aggregated_poly, aggregated_poly_commitment, evaluation_challenge = compute_aggregated_poly_and_commitment(
        blobs,
        commitments
    )

    # Evaluate aggregated polynomial at `evaluation_challenge` (evaluation function checks for div-by-zero)
    y = evaluate_polynomial_in_evaluation_form(aggregated_poly, evaluation_challenge)

    # Verify aggregated proof
    aggregated_proof = bytes_to_kzg_proof(aggregated_proof_bytes)
    return verify_kzg_proof_impl(aggregated_poly_commitment, evaluation_challenge, y, aggregated_proof)
```
