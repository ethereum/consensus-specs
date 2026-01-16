# Deneb -- Polynomial Commitments

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
- [Cryptographic types](#cryptographic-types)
- [Constants](#constants)
- [Preset](#preset)
  - [Blob](#blob)
  - [Trusted setup](#trusted-setup)
- [Helpers](#helpers)
  - [Bit-reversal permutation](#bit-reversal-permutation)
    - [`is_power_of_two`](#is_power_of_two)
    - [`reverse_bits`](#reverse_bits)
    - [`bit_reversal_permutation`](#bit_reversal_permutation)
  - [BLS12-381 helpers](#bls12-381-helpers)
    - [`multi_exp`](#multi_exp)
    - [`hash_to_bls_field`](#hash_to_bls_field)
    - [`bytes_to_bls_field`](#bytes_to_bls_field)
    - [`bls_field_to_bytes`](#bls_field_to_bytes)
    - [`validate_kzg_g1`](#validate_kzg_g1)
    - [`bytes_to_kzg_commitment`](#bytes_to_kzg_commitment)
    - [`bytes_to_kzg_proof`](#bytes_to_kzg_proof)
    - [`blob_to_polynomial`](#blob_to_polynomial)
    - [`compute_challenge`](#compute_challenge)
    - [`g1_lincomb`](#g1_lincomb)
    - [`compute_powers`](#compute_powers)
    - [`compute_roots_of_unity`](#compute_roots_of_unity)
  - [Polynomials](#polynomials)
    - [`evaluate_polynomial_in_evaluation_form`](#evaluate_polynomial_in_evaluation_form)
  - [KZG](#kzg)
    - [`blob_to_kzg_commitment`](#blob_to_kzg_commitment)
    - [`verify_kzg_proof`](#verify_kzg_proof)
    - [`verify_kzg_proof_impl`](#verify_kzg_proof_impl)
    - [`verify_kzg_proof_batch`](#verify_kzg_proof_batch)
    - [`compute_kzg_proof`](#compute_kzg_proof)
    - [`compute_quotient_eval_within_domain`](#compute_quotient_eval_within_domain)
    - [`compute_kzg_proof_impl`](#compute_kzg_proof_impl)
    - [`compute_blob_kzg_proof`](#compute_blob_kzg_proof)
    - [`verify_blob_kzg_proof`](#verify_blob_kzg_proof)
    - [`verify_blob_kzg_proof_batch`](#verify_blob_kzg_proof_batch)

<!-- mdformat-toc end -->

## Introduction

This document specifies basic polynomial operations and KZG polynomial
commitment operations that are essential for the implementation of the EIP-4844
feature in the Deneb specification. The implementations are not optimized for
performance, but readability. All practical implementations should optimize the
polynomial operations.

Functions flagged as "Public method" MUST be provided by the underlying KZG
library as public functions. All other functions are private functions used
internally by the KZG library.

Public functions MUST accept raw bytes as input and perform the required
cryptographic normalization before invoking any internal functions.

## Types

| Name            | SSZ equivalent                                                  | Description                                                                                                                                                                  |
| --------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `G1Point`       | `Bytes48`                                                       |                                                                                                                                                                              |
| `G2Point`       | `Bytes96`                                                       |                                                                                                                                                                              |
| `KZGCommitment` | `Bytes48`                                                       | Validation: Perform [BLS standard's](https://datatracker.ietf.org/doc/html/draft-irtf-cfrg-bls-signature-04#section-2.5) "KeyValidate" check but do allow the identity point |
| `KZGProof`      | `Bytes48`                                                       | Same as for `KZGCommitment`                                                                                                                                                  |
| `Blob`          | `ByteVector[BYTES_PER_FIELD_ELEMENT * FIELD_ELEMENTS_PER_BLOB]` | A basic data blob                                                                                                                                                            |

## Cryptographic types

| Name                                                                                                                                                  | SSZ equivalent                                     | Description                                                                   |
| ----------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------------------------- |
| [`BLSFieldElement`](https://github.com/ethereum/consensus-specs/blob/36a5719b78523c057065515c8f8fcaeba75d065b/pysetup/spec_builders/deneb.py#L18-L19) | `uint256`                                          | <!-- predefined-type --> A value in the finite field defined by `BLS_MODULUS` |
| [`Polynomial`](https://github.com/ethereum/consensus-specs/blob/36a5719b78523c057065515c8f8fcaeba75d065b/pysetup/spec_builders/deneb.py#L22-L28)      | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_BLOB]` | <!-- predefined-type --> A polynomial in evaluation form                      |

## Constants

| Name                      | Value                                                                           | Notes                                                                       |
| ------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `BLS_MODULUS`             | `52435875175126190479447740508185965837690552500527637822603658699938581184513` | Scalar field modulus of BLS12-381                                           |
| `BYTES_PER_COMMITMENT`    | `uint64(48)`                                                                    | The number of bytes in a KZG commitment                                     |
| `BYTES_PER_PROOF`         | `uint64(48)`                                                                    | The number of bytes in a KZG proof                                          |
| `BYTES_PER_FIELD_ELEMENT` | `uint64(32)`                                                                    | Bytes used to encode a BLS scalar field element                             |
| `BYTES_PER_BLOB`          | `uint64(BYTES_PER_FIELD_ELEMENT * FIELD_ELEMENTS_PER_BLOB)`                     | The number of bytes in a blob                                               |
| `G1_POINT_AT_INFINITY`    | `Bytes48(b'\xc0' + b'\x00' * 47)`                                               | Serialized form of the point at infinity on the G1 group                    |
| `KZG_ENDIANNESS`          | `'big'`                                                                         | The endianness of the field elements including blobs                        |
| `PRIMITIVE_ROOT_OF_UNITY` | `7`                                                                             | The primitive root of unity from which all roots of unity should be derived |

## Preset

### Blob

| Name                                | Value                 |
| ----------------------------------- | --------------------- |
| `FIELD_ELEMENTS_PER_BLOB`           | `uint64(4096)`        |
| `FIAT_SHAMIR_PROTOCOL_DOMAIN`       | `b'FSBLOBVERIFY_V1_'` |
| `RANDOM_CHALLENGE_KZG_BATCH_DOMAIN` | `b'RCKZGBATCH___V1_'` |

### Trusted setup

| Name                    | Value                                      |
| ----------------------- | ------------------------------------------ |
| `KZG_SETUP_G2_LENGTH`   | `65`                                       |
| `KZG_SETUP_G1_MONOMIAL` | `Vector[G1Point, FIELD_ELEMENTS_PER_BLOB]` |
| `KZG_SETUP_G1_LAGRANGE` | `Vector[G1Point, FIELD_ELEMENTS_PER_BLOB]` |
| `KZG_SETUP_G2_MONOMIAL` | `Vector[G2Point, KZG_SETUP_G2_LENGTH]`     |

## Helpers

### Bit-reversal permutation

All polynomials (which are always given in Lagrange form) should be interpreted
as being in bit-reversal permutation. In practice, clients can implement this by
storing the lists `KZG_SETUP_G1_LAGRANGE` and roots of unity in bit-reversal
permutation, so these functions only have to be called once at startup.

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
    return int(("{:0" + str(order.bit_length() - 1) + "b}").format(n)[::-1], 2)
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

#### `multi_exp`

This function performs a multi-scalar multiplication between `points` and
`integers`. `points` can either be in G1 or G2.

```python
def multi_exp(_points: Sequence[TPoint], _integers: Sequence[uint64]) -> Sequence[TPoint]: ...
```

#### `hash_to_bls_field`

```python
def hash_to_bls_field(data: bytes) -> BLSFieldElement:
    """
    Hash ``data`` and convert the output to a BLS scalar field element.
    The output is not uniform over the BLS field.
    """
    hashed_data = hash(data)
    return BLSFieldElement(int.from_bytes(hashed_data, KZG_ENDIANNESS) % BLS_MODULUS)
```

#### `bytes_to_bls_field`

```python
def bytes_to_bls_field(b: Bytes32) -> BLSFieldElement:
    """
    Convert untrusted bytes to a trusted and validated BLS scalar field element.
    This function does not accept inputs greater than the BLS modulus.
    """
    field_element = int.from_bytes(b, KZG_ENDIANNESS)
    assert field_element < BLS_MODULUS
    return BLSFieldElement(field_element)
```

#### `bls_field_to_bytes`

```python
def bls_field_to_bytes(x: BLSFieldElement) -> Bytes32:
    return int.to_bytes(int(x), 32, KZG_ENDIANNESS)
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
        value = bytes_to_bls_field(
            blob[i * BYTES_PER_FIELD_ELEMENT : (i + 1) * BYTES_PER_FIELD_ELEMENT]
        )
        polynomial[i] = value
    return polynomial
```

#### `compute_challenge`

```python
def compute_challenge(blob: Blob, commitment: KZGCommitment) -> BLSFieldElement:
    """
    Return the Fiat-Shamir challenge required by the rest of the protocol.
    """

    # Append the degree of the polynomial as a domain separator
    degree_poly = int.to_bytes(FIELD_ELEMENTS_PER_BLOB, 16, KZG_ENDIANNESS)
    data = FIAT_SHAMIR_PROTOCOL_DOMAIN + degree_poly

    data += blob
    data += commitment

    # Transcript has been prepared: time to create the challenge
    return hash_to_bls_field(data)
```

#### `g1_lincomb`

```python
def g1_lincomb(
    points: Sequence[KZGCommitment], scalars: Sequence[BLSFieldElement]
) -> KZGCommitment:
    """
    BLS multiscalar multiplication in G1. This can be naively implemented using double-and-add.
    """
    assert len(points) == len(scalars)

    if len(points) == 0:
        return bls.G1_to_bytes48(bls.Z1())

    points_g1 = []
    for point in points:
        points_g1.append(bls.bytes48_to_G1(point))

    result = bls.multi_exp(points_g1, scalars)
    return KZGCommitment(bls.G1_to_bytes48(result))
```

#### `compute_powers`

```python
def compute_powers(x: BLSFieldElement, n: uint64) -> Sequence[BLSFieldElement]:
    """
    Return ``x`` to power of [0, n-1], if n > 0. When n==0, an empty array is returned.
    """
    current_power = BLSFieldElement(1)
    powers = []
    for _ in range(n):
        powers.append(current_power)
        current_power = current_power * x
    return powers
```

#### `compute_roots_of_unity`

```python
def compute_roots_of_unity(order: uint64) -> Sequence[BLSFieldElement]:
    """
    Return roots of unity of ``order``.
    """
    assert (BLS_MODULUS - 1) % int(order) == 0
    root_of_unity = BLSFieldElement(
        pow(PRIMITIVE_ROOT_OF_UNITY, (BLS_MODULUS - 1) // int(order), BLS_MODULUS)
    )
    return compute_powers(root_of_unity, order)
```

### Polynomials

#### `evaluate_polynomial_in_evaluation_form`

```python
def evaluate_polynomial_in_evaluation_form(
    polynomial: Polynomial, z: BLSFieldElement
) -> BLSFieldElement:
    """
    Evaluate a polynomial (in evaluation form) at an arbitrary point ``z``.
    - When ``z`` is in the domain, the evaluation can be found by indexing the polynomial at the
    position that ``z`` is in the domain.
    - When ``z`` is not in the domain, the barycentric formula is used:
       f(z) = (z**WIDTH - 1) / WIDTH  *  sum_(i=0)^(WIDTH-1) (f(DOMAIN[i]) * DOMAIN[i]) / (z - DOMAIN[i])
    """
    width = len(polynomial)
    assert width == FIELD_ELEMENTS_PER_BLOB
    inverse_width = BLSFieldElement(width).inverse()

    roots_of_unity_brp = bit_reversal_permutation(compute_roots_of_unity(FIELD_ELEMENTS_PER_BLOB))

    # If we are asked to evaluate within the domain, we already know the answer
    if z in roots_of_unity_brp:
        eval_index = roots_of_unity_brp.index(z)
        return polynomial[eval_index]

    result = BLSFieldElement(0)
    for i in range(width):
        a = polynomial[i] * roots_of_unity_brp[i]
        b = z - roots_of_unity_brp[i]
        result += a / b
    r = z.pow(BLSFieldElement(width)) - BLSFieldElement(1)
    result = result * r * inverse_width
    return result
```

### KZG

KZG core functions. These are also defined in Deneb execution specs.

#### `blob_to_kzg_commitment`

```python
def blob_to_kzg_commitment(blob: Blob) -> KZGCommitment:
    """
    Public method.
    """
    assert len(blob) == BYTES_PER_BLOB
    return g1_lincomb(bit_reversal_permutation(KZG_SETUP_G1_LAGRANGE), blob_to_polynomial(blob))
```

#### `verify_kzg_proof`

```python
def verify_kzg_proof(
    commitment_bytes: Bytes48, z_bytes: Bytes32, y_bytes: Bytes32, proof_bytes: Bytes48
) -> bool:
    """
    Verify KZG proof that ``p(z) == y`` where ``p(z)`` is the polynomial represented by ``polynomial_kzg``.
    Receives inputs as bytes.
    Public method.
    """
    assert len(commitment_bytes) == BYTES_PER_COMMITMENT
    assert len(z_bytes) == BYTES_PER_FIELD_ELEMENT
    assert len(y_bytes) == BYTES_PER_FIELD_ELEMENT
    assert len(proof_bytes) == BYTES_PER_PROOF

    return verify_kzg_proof_impl(
        bytes_to_kzg_commitment(commitment_bytes),
        bytes_to_bls_field(z_bytes),
        bytes_to_bls_field(y_bytes),
        bytes_to_kzg_proof(proof_bytes),
    )
```

#### `verify_kzg_proof_impl`

```python
def verify_kzg_proof_impl(
    commitment: KZGCommitment, z: BLSFieldElement, y: BLSFieldElement, proof: KZGProof
) -> bool:
    """
    Verify KZG proof that ``p(z) == y`` where ``p(z)`` is the polynomial represented by ``polynomial_kzg``.
    """
    # Verify: P - y = Q * (X - z)
    X_minus_z = bls.add(
        bls.bytes96_to_G2(KZG_SETUP_G2_MONOMIAL[1]),
        bls.multiply(bls.G2(), -z),
    )
    P_minus_y = bls.add(bls.bytes48_to_G1(commitment), bls.multiply(bls.G1(), -y))
    return bls.pairing_check(
        [[P_minus_y, bls.neg(bls.G2())], [bls.bytes48_to_G1(proof), X_minus_z]]
    )
```

#### `verify_kzg_proof_batch`

```python
def verify_kzg_proof_batch(
    commitments: Sequence[KZGCommitment],
    zs: Sequence[BLSFieldElement],
    ys: Sequence[BLSFieldElement],
    proofs: Sequence[KZGProof],
) -> bool:
    """
    Verify multiple KZG proofs efficiently.
    """

    assert len(commitments) == len(zs) == len(ys) == len(proofs)

    # Compute a random challenge. Note that it does not have to be computed from a hash,
    # r just has to be random.
    degree_poly = int.to_bytes(FIELD_ELEMENTS_PER_BLOB, 8, KZG_ENDIANNESS)
    num_commitments = int.to_bytes(len(commitments), 8, KZG_ENDIANNESS)
    data = RANDOM_CHALLENGE_KZG_BATCH_DOMAIN + degree_poly + num_commitments

    # Append all inputs to the transcript before we hash
    for commitment, z, y, proof in zip(commitments, zs, ys, proofs):
        data += commitment + bls_field_to_bytes(z) + bls_field_to_bytes(y) + proof

    r = hash_to_bls_field(data)
    r_powers = compute_powers(r, len(commitments))

    # Verify: e(sum r^i proof_i, [s]) ==
    # e(sum r^i (commitment_i - [y_i]) + sum r^i z_i proof_i, [1])
    proof_lincomb = g1_lincomb(proofs, r_powers)
    proof_z_lincomb = g1_lincomb(proofs, [z * r_power for z, r_power in zip(zs, r_powers)])
    C_minus_ys = [
        bls.add(bls.bytes48_to_G1(commitment), bls.multiply(bls.G1(), -y))
        for commitment, y in zip(commitments, ys)
    ]
    C_minus_y_as_KZGCommitments = [KZGCommitment(bls.G1_to_bytes48(x)) for x in C_minus_ys]
    C_minus_y_lincomb = g1_lincomb(C_minus_y_as_KZGCommitments, r_powers)

    return bls.pairing_check(
        [
            [
                bls.bytes48_to_G1(proof_lincomb),
                bls.neg(bls.bytes96_to_G2(KZG_SETUP_G2_MONOMIAL[1])),
            ],
            [
                bls.add(bls.bytes48_to_G1(C_minus_y_lincomb), bls.bytes48_to_G1(proof_z_lincomb)),
                bls.G2(),
            ],
        ]
    )
```

#### `compute_kzg_proof`

```python
def compute_kzg_proof(blob: Blob, z_bytes: Bytes32) -> Tuple[KZGProof, Bytes32]:
    """
    Compute KZG proof at point `z` for the polynomial represented by `blob`.
    Do this by computing the quotient polynomial in evaluation form: q(x) = (p(x) - p(z)) / (x - z).
    Public method.
    """
    assert len(blob) == BYTES_PER_BLOB
    assert len(z_bytes) == BYTES_PER_FIELD_ELEMENT
    polynomial = blob_to_polynomial(blob)
    proof, y = compute_kzg_proof_impl(polynomial, bytes_to_bls_field(z_bytes))
    return proof, int(y).to_bytes(BYTES_PER_FIELD_ELEMENT, KZG_ENDIANNESS)
```

#### `compute_quotient_eval_within_domain`

```python
def compute_quotient_eval_within_domain(
    z: BLSFieldElement, polynomial: Polynomial, y: BLSFieldElement
) -> BLSFieldElement:
    """
    Given `y == p(z)` for a polynomial `p(x)`, compute `q(z)`: the KZG quotient polynomial evaluated at `z` for the
    special case where `z` is in roots of unity.

    For more details, read https://dankradfeist.de/ethereum/2021/06/18/pcs-multiproofs.html section "Dividing
    when one of the points is zero". The code below computes q(x_m) for the roots of unity special case.
    """
    roots_of_unity_brp = bit_reversal_permutation(compute_roots_of_unity(FIELD_ELEMENTS_PER_BLOB))
    result = BLSFieldElement(0)
    for i, omega_i in enumerate(roots_of_unity_brp):
        if omega_i == z:  # skip the evaluation point in the sum
            continue

        f_i = polynomial[i] - y
        numerator = f_i * omega_i
        denominator = z * (z - omega_i)
        result += numerator / denominator

    return result
```

#### `compute_kzg_proof_impl`

```python
def compute_kzg_proof_impl(
    polynomial: Polynomial, z: BLSFieldElement
) -> Tuple[KZGProof, BLSFieldElement]:
    """
    Helper function for `compute_kzg_proof()` and `compute_blob_kzg_proof()`.
    """
    roots_of_unity_brp = bit_reversal_permutation(compute_roots_of_unity(FIELD_ELEMENTS_PER_BLOB))

    # For all x_i, compute p(x_i) - p(z)
    y = evaluate_polynomial_in_evaluation_form(polynomial, z)
    polynomial_shifted = [p - y for p in polynomial]

    # For all x_i, compute (x_i - z)
    denominator_poly = [x - z for x in roots_of_unity_brp]

    # Compute the quotient polynomial directly in evaluation form
    quotient_polynomial = [BLSFieldElement(0)] * FIELD_ELEMENTS_PER_BLOB
    for i, (a, b) in enumerate(zip(polynomial_shifted, denominator_poly)):
        if b == BLSFieldElement(0):
            # The denominator is zero hence `z` is a root of unity: we must handle it as a special case
            quotient_polynomial[i] = compute_quotient_eval_within_domain(
                roots_of_unity_brp[i], polynomial, y
            )
        else:
            # Compute: q(x_i) = (p(x_i) - p(z)) / (x_i - z).
            quotient_polynomial[i] = a / b

    return KZGProof(
        g1_lincomb(bit_reversal_permutation(KZG_SETUP_G1_LAGRANGE), quotient_polynomial)
    ), y
```

#### `compute_blob_kzg_proof`

```python
def compute_blob_kzg_proof(blob: Blob, commitment_bytes: Bytes48) -> KZGProof:
    """
    Given a blob, return the KZG proof that is used to verify it against the commitment.
    This method does not verify that the commitment is correct with respect to `blob`.
    Public method.
    """
    assert len(blob) == BYTES_PER_BLOB
    assert len(commitment_bytes) == BYTES_PER_COMMITMENT
    commitment = bytes_to_kzg_commitment(commitment_bytes)
    polynomial = blob_to_polynomial(blob)
    evaluation_challenge = compute_challenge(blob, commitment)
    proof, _ = compute_kzg_proof_impl(polynomial, evaluation_challenge)
    return proof
```

#### `verify_blob_kzg_proof`

```python
def verify_blob_kzg_proof(blob: Blob, commitment_bytes: Bytes48, proof_bytes: Bytes48) -> bool:
    """
    Given a blob and a KZG proof, verify that the blob data corresponds to the provided commitment.

    Public method.
    """
    assert len(blob) == BYTES_PER_BLOB
    assert len(commitment_bytes) == BYTES_PER_COMMITMENT
    assert len(proof_bytes) == BYTES_PER_PROOF

    commitment = bytes_to_kzg_commitment(commitment_bytes)

    polynomial = blob_to_polynomial(blob)
    evaluation_challenge = compute_challenge(blob, commitment)

    # Evaluate polynomial at `evaluation_challenge`
    y = evaluate_polynomial_in_evaluation_form(polynomial, evaluation_challenge)

    # Verify proof
    proof = bytes_to_kzg_proof(proof_bytes)
    return verify_kzg_proof_impl(commitment, evaluation_challenge, y, proof)
```

#### `verify_blob_kzg_proof_batch`

```python
def verify_blob_kzg_proof_batch(
    blobs: Sequence[Blob], commitments_bytes: Sequence[Bytes48], proofs_bytes: Sequence[Bytes48]
) -> bool:
    """
    Given a list of blobs and blob KZG proofs, verify that they correspond to the provided commitments.
    Will return True if there are zero blobs/commitments/proofs.
    Public method.
    """

    assert len(blobs) == len(commitments_bytes) == len(proofs_bytes)

    commitments, evaluation_challenges, ys, proofs = [], [], [], []
    for blob, commitment_bytes, proof_bytes in zip(blobs, commitments_bytes, proofs_bytes):
        assert len(blob) == BYTES_PER_BLOB
        assert len(commitment_bytes) == BYTES_PER_COMMITMENT
        assert len(proof_bytes) == BYTES_PER_PROOF
        commitment = bytes_to_kzg_commitment(commitment_bytes)
        commitments.append(commitment)
        polynomial = blob_to_polynomial(blob)
        evaluation_challenge = compute_challenge(blob, commitment)
        evaluation_challenges.append(evaluation_challenge)
        ys.append(evaluate_polynomial_in_evaluation_form(polynomial, evaluation_challenge))
        proofs.append(bytes_to_kzg_proof(proof_bytes))

    return verify_kzg_proof_batch(commitments, evaluation_challenges, ys, proofs)
```
