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
    - [`bytes_to_bls_field`](#bytes_to_bls_field)
    - [`blob_to_polynomial`](#blob_to_polynomial)
    - [`hash_to_bls_field`](#hash_to_bls_field)
    - [`bls_modular_inverse`](#bls_modular_inverse)
    - [`div`](#div)
    - [`g1_lincomb`](#g1_lincomb)
    - [`poly_lincomb`](#poly_lincomb)
    - [`compute_powers`](#compute_powers)
    - [`compute_challenges`](#compute_challenges)
  - [Polynomials](#polynomials)
    - [`evaluate_polynomial_in_evaluation_form`](#evaluate_polynomial_in_evaluation_form)
  - [KZG](#kzg)
    - [`blob_to_kzg_commitment`](#blob_to_kzg_commitment)
    - [`verify_kzg_proof`](#verify_kzg_proof)
    - [`compute_kzg_proof`](#compute_kzg_proof)
    - [`compute_aggregated_poly_and_commitment`](#compute_aggregated_poly_and_commitment)
    - [`compute_aggregate_kzg_proof`](#compute_aggregate_kzg_proof)
    - [`verify_aggregate_kzg_proof`](#verify_aggregate_kzg_proof)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


## Introduction

This document specifies basic polynomial operations and KZG polynomial commitment operations as they are needed for the EIP-4844 specification. The implementations are not optimized for performance, but readability. All practical implementations should optimize the polynomial operations.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `G1Point` | `Bytes48` | |
| `G2Point` | `Bytes96` | |
| `BLSFieldElement` | `uint256` | `x < BLS_MODULUS` |
| `KZGCommitment` | `Bytes48` | Same as BLS standard "is valid pubkey" check but also allows `0x00..00` for point-at-infinity |
| `KZGProof` | `Bytes48` | Same as for `KZGCommitment` |
| `Polynomial` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_BLOB]` | a polynomial in evaluation form |
| `Blob` | `ByteVector[BYTES_PER_FIELD_ELEMENT * FIELD_ELEMENTS_PER_BLOB]` | a basic blob data |

## Constants

| Name | Value | Notes |
| - | - | - |
| `BLS_MODULUS` | `52435875175126190479447740508185965837690552500527637822603658699938581184513` | Scalar field modulus of BLS12-381 |
| `BYTES_PER_FIELD_ELEMENT` | `uint64(32)` | Bytes used to encode a BLS scalar field element |

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
| `KZG_SETUP_G1` | `Vector[G1Point, FIELD_ELEMENTS_PER_BLOB]`, contents TBD |
| `KZG_SETUP_G2` | `Vector[G2Point, FIELD_ELEMENTS_PER_BLOB]`, contents TBD |
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

#### `bytes_to_bls_field`

```python
def bytes_to_bls_field(b: Bytes32) -> BLSFieldElement:
    """
    Convert 32-byte value to a BLS field scalar. The output is not uniform over the BLS field.
    """
    return int.from_bytes(b, ENDIANNESS) % BLS_MODULUS
```

#### `blob_to_polynomial`

```python
def blob_to_polynomial(blob: Blob) -> Polynomial:
    """
    Convert a blob to list of BLS field scalars.
    """
    polynomial = Polynomial()
    for i in range(FIELD_ELEMENTS_PER_BLOB):
        value = int.from_bytes(blob[i * BYTES_PER_FIELD_ELEMENT: (i + 1) * BYTES_PER_FIELD_ELEMENT], ENDIANNESS)
        assert value < BLS_MODULUS
        polynomial[i] = value
    return polynomial
```

#### `hash_to_bls_field`

```python
def hash_to_bls_field(polys: Sequence[Polynomial],
                      comms: Sequence[KZGCommitment]) -> BLSFieldElement:
    """
    Compute 32-byte hash of serialized polynomials and commitments concatenated.
    This hash is then converted to a BLS field element, where the result is not uniform over the BLS field.
    Return the BLS field element.
    """
    # Append the number of polynomials and the degree of each polynomial as a domain separator
    num_polys = int.to_bytes(len(polys), 8, ENDIANNESS)
    degree_poly = int.to_bytes(FIELD_ELEMENTS_PER_BLOB, 8, ENDIANNESS)
    data = FIAT_SHAMIR_PROTOCOL_DOMAIN + degree_poly + num_polys

    # Append each polynomial which is composed by field elements
    for poly in polys:
        for field_element in poly:
            data += int.to_bytes(field_element, BYTES_PER_FIELD_ELEMENT, ENDIANNESS)

    # Append serialized G1 points
    for commitment in comms:
        data += commitment

    return bytes_to_bls_field(hash(data))
```

#### `bls_modular_inverse`

```python
def bls_modular_inverse(x: BLSFieldElement) -> BLSFieldElement:
    """
    Compute the modular inverse of x
    i.e. return y such that x * y % BLS_MODULUS == 1 and return 0 for x == 0
    """
    return pow(x, -1, BLS_MODULUS) if x != 0 else 0
```

#### `div`

```python
def div(x: BLSFieldElement, y: BLSFieldElement) -> BLSFieldElement:
    """
    Divide two field elements: ``x`` by `y``.
    """
    return (int(x) * int(bls_modular_inverse(y))) % BLS_MODULUS
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
    result = [0] * FIELD_ELEMENTS_PER_BLOB
    for v, s in zip(polys, scalars):
        for i, x in enumerate(v):
            result[i] = (result[i] + int(s) * int(x)) % BLS_MODULUS
    return [BLSFieldElement(x) for x in result]
```

#### `compute_powers`

```python
def compute_powers(x: BLSFieldElement, n: uint64) -> Sequence[BLSFieldElement]:
    """
    Return ``x`` to power of [0, n-1].
    """
    current_power = 1
    powers = []
    for _ in range(n):
        powers.append(BLSFieldElement(current_power))
        current_power = current_power * int(x) % BLS_MODULUS
    return powers
```
#### `compute_challenges`

```python
def compute_challenges(x: BLSFieldElement, n: uint64) -> Tuple[Sequence[BLSFieldElement], BLSFieldElement]:
    """
    Return the random linear combination challenges and the evaluation challenge
    """
    powers = compute_powers(x, n)
    evaluation_challenge = 0
    
    # When n == 0, this means that the blobs are empty
    # in that case, we define the evaluation challenge to be 0
    if len(powers) != 0:
        evaluation_challenge = int(powers[-1]) * x % BLS_MODULUS
    
    return powers, evaluation_challenge

```

### Polynomials

#### `evaluate_polynomial_in_evaluation_form`

```python
def evaluate_polynomial_in_evaluation_form(polynomial: Polynomial,
                                           z: BLSFieldElement) -> BLSFieldElement:
    """
    Evaluate a polynomial (in evaluation form) at an arbitrary point ``z``.
    Uses the barycentric formula:
       f(z) = (z**WIDTH - 1) / WIDTH  *  sum_(i=0)^WIDTH  (f(DOMAIN[i]) * DOMAIN[i]) / (z - DOMAIN[i])
    """
    width = len(polynomial)
    assert width == FIELD_ELEMENTS_PER_BLOB
    inverse_width = bls_modular_inverse(width)

    # Make sure we won't divide by zero during division
    assert z not in ROOTS_OF_UNITY

    roots_of_unity_brp = bit_reversal_permutation(ROOTS_OF_UNITY)

    result = 0
    for i in range(width):
        result += div(int(polynomial[i]) * int(roots_of_unity_brp[i]), (int(z) - roots_of_unity_brp[i]))
    result = result * (pow(z, width, BLS_MODULUS) - 1) * inverse_width % BLS_MODULUS
    return result
```

### KZG

KZG core functions. These are also defined in EIP-4844 execution specs.

#### `blob_to_kzg_commitment`

```python
def blob_to_kzg_commitment(blob: Blob) -> KZGCommitment:
    return g1_lincomb(bit_reversal_permutation(KZG_SETUP_LAGRANGE), blob_to_polynomial(blob))
```

#### `verify_kzg_proof`

```python
def verify_kzg_proof(polynomial_kzg: KZGCommitment,
                     z: BLSFieldElement,
                     y: BLSFieldElement,
                     kzg_proof: KZGProof) -> bool:
    """
    Verify KZG proof that ``p(z) == y`` where ``p(z)`` is the polynomial represented by ``polynomial_kzg``.
    """
    # Verify: P - y = Q * (X - z)
    X_minus_z = bls.add(bls.bytes96_to_G2(KZG_SETUP_G2[1]), bls.multiply(bls.G2, BLS_MODULUS - z))
    P_minus_y = bls.add(bls.bytes48_to_G1(polynomial_kzg), bls.multiply(bls.G1, BLS_MODULUS - y))
    return bls.pairing_check([
        [P_minus_y, bls.neg(bls.G2)],
        [bls.bytes48_to_G1(kzg_proof), X_minus_z]
    ])
```

#### `compute_kzg_proof`

```python
def compute_kzg_proof(polynomial: Polynomial, z: BLSFieldElement) -> KZGProof:
    """
    Compute KZG proof at point `z` with `polynomial` being in evaluation form
    Do this by computing the quotient polynomial in evaluation form: q(x) = (p(x) - p(z)) / (x - z)
    """

    # To avoid SSZ overflow/underflow, convert element into int
    polynomial = [int(i) for i in polynomial]
    z = int(z)

    y = evaluate_polynomial_in_evaluation_form(polynomial, z)
    polynomial_shifted = [(p - int(y)) % BLS_MODULUS for p in polynomial]

    # Make sure we won't divide by zero during division
    assert z not in ROOTS_OF_UNITY
    denominator_poly = [(int(x) - z) % BLS_MODULUS for x in bit_reversal_permutation(ROOTS_OF_UNITY)]

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
    """
    # Convert blobs to polynomials
    polynomials = [blob_to_polynomial(blob) for blob in blobs]

    # Generate random linear combination challenges
    r = hash_to_bls_field(polynomials, kzg_commitments)
    r_powers, evaluation_challenge = compute_challenges(r, len(kzg_commitments))

    # Create aggregated polynomial in evaluation form
    aggregated_poly = Polynomial(poly_lincomb(polynomials, r_powers))

    # Compute commitment to aggregated polynomial
    aggregated_poly_commitment = KZGCommitment(g1_lincomb(kzg_commitments, r_powers))

    return aggregated_poly, aggregated_poly_commitment, evaluation_challenge
```

#### `compute_aggregate_kzg_proof`

```python
def compute_aggregate_kzg_proof(blobs: Sequence[Blob]) -> KZGProof:
    commitments = [blob_to_kzg_commitment(blob) for blob in blobs]
    aggregated_poly, aggregated_poly_commitment, evaluation_challenge = compute_aggregated_poly_and_commitment(
        blobs,
        commitments
    )
    return compute_kzg_proof(aggregated_poly, evaluation_challenge)
```

#### `verify_aggregate_kzg_proof`

```python
def verify_aggregate_kzg_proof(blobs: Sequence[Blob],
                               expected_kzg_commitments: Sequence[KZGCommitment],
                               kzg_aggregated_proof: KZGCommitment) -> bool:
    aggregated_poly, aggregated_poly_commitment, evaluation_challenge = compute_aggregated_poly_and_commitment(
        blobs,
        expected_kzg_commitments,
    )

    # Evaluate aggregated polynomial at `evaluation_challenge` (evaluation function checks for div-by-zero)
    y = evaluate_polynomial_in_evaluation_form(aggregated_poly, evaluation_challenge)

    # Verify aggregated proof
    return verify_kzg_proof(aggregated_poly_commitment, evaluation_challenge, y, kzg_aggregated_proof)
```
