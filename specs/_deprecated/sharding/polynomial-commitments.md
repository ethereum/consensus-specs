# Sharding -- Polynomial Commitments

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [BLS Field](#bls-field)
  - [KZG Trusted setup](#kzg-trusted-setup)
- [Custom types](#custom-types)
- [Helper functions](#helper-functions)
  - [`next_power_of_two`](#next_power_of_two)
  - [`reverse_bit_order`](#reverse_bit_order)
  - [`list_to_reverse_bit_order`](#list_to_reverse_bit_order)
- [Field operations](#field-operations)
  - [Generic field operations](#generic-field-operations)
    - [`bls_modular_inverse`](#bls_modular_inverse)
    - [`roots_of_unity`](#roots_of_unity)
  - [Field helper functions](#field-helper-functions)
    - [`compute_powers`](#compute_powers)
    - [`low_degree_check`](#low_degree_check)
    - [`vector_lincomb`](#vector_lincomb)
    - [`bytes_to_field_elements`](#bytes_to_field_elements)
- [Polynomial operations](#polynomial-operations)
  - [`add_polynomials`](#add_polynomials)
  - [`multiply_polynomials`](#multiply_polynomials)
  - [`interpolate_polynomial`](#interpolate_polynomial)
  - [`evaluate_polynomial_in_evaluation_form`](#evaluate_polynomial_in_evaluation_form)
- [KZG Operations](#kzg-operations)
  - [Elliptic curve helper functions](#elliptic-curve-helper-functions)
    - [`elliptic_curve_lincomb`](#elliptic_curve_lincomb)
  - [Hash to field](#hash-to-field)
    - [`hash_to_bls_field`](#hash_to_bls_field)
  - [KZG operations](#kzg-operations)
    - [`verify_kzg_proof`](#verify_kzg_proof)
    - [`verify_kzg_multiproof`](#verify_kzg_multiproof)
    - [`verify_degree_proof`](#verify_degree_proof)

<!-- mdformat-toc end -->

## Introduction

This document specifies basic polynomial operations and KZG polynomial
commitment operations as they are needed for the sharding specification. The
implementations are not optimized for performance, but readability. All
practical implementations should optimize the polynomial operations, and hints
what the best known algorithms for these implementations are included below.

## Constants

### BLS Field

| Name                      | Value                                                                                           | Notes                                                        |
| ------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `BLS_MODULUS`             | `0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001` (curve order of BLS12_381) |                                                              |
| `PRIMITIVE_ROOT_OF_UNITY` | `7`                                                                                             | Primitive root of unity of the BLS12_381 (inner) BLS_MODULUS |

### KZG Trusted setup

| Name       | Value                                                                                                          |
| ---------- | -------------------------------------------------------------------------------------------------------------- |
| `G1_SETUP` | Type `List[G1]`. The G1-side trusted setup `[G, G*s, G*s**2....]`; note that the first point is the generator. |
| `G2_SETUP` | Type `List[G2]`. The G2-side trusted setup `[G, G*s, G*s**2....]`                                              |

## Custom types

We define the following Python custom types for type hinting and readability:

| Name                          | SSZ equivalent          | Description                                                |
| ----------------------------- | ----------------------- | ---------------------------------------------------------- |
| `KZGCommitment`               | `Bytes48`               | A G1 curve point                                           |
| `BLSFieldElement`             | `uint256`               | A number `x` in the range `0 <= x < BLS_MODULUS`           |
| `BLSPolynomialByCoefficients` | `List[BLSFieldElement]` | A polynomial over the BLS field, given in coefficient form |
| `BLSPolynomialByEvaluations`  | `List[BLSFieldElement]` | A polynomial over the BLS field, given in evaluation form  |

## Helper functions

#### `next_power_of_two`

```python
def next_power_of_two(x: int) -> int:
    assert x > 0
    return 2 ** ((x - 1).bit_length())
```

#### `reverse_bit_order`

```python
def reverse_bit_order(n: int, order: int) -> int:
    """
    Reverse the bit order of an integer n
    """
    assert is_power_of_two(order)
    # Convert n to binary with the same number of bits as "order" - 1, then reverse its bit order
    return int(('{:0' + str(order.bit_length() - 1) + 'b}').format(n)[::-1], 2)
```

#### `list_to_reverse_bit_order`

```python
def list_to_reverse_bit_order(l: List[int]) -> List[int]:
    """
    Convert a list between normal and reverse bit order. The permutation is an involution (inverts itself)..
    """
    return [l[reverse_bit_order(i, len(l))] for i in range(len(l))]
```

## Field operations

### Generic field operations

#### `bls_modular_inverse`

```python
def bls_modular_inverse(x: BLSFieldElement) -> BLSFieldElement:
    """
    Compute the modular inverse of x, i.e. y such that x * y % BLS_MODULUS == 1 and return 1 for x == 0
    """
    lm, hm = 1, 0
    low, high = x % BLS_MODULUS, BLS_MODULUS
    while low > 1:
        r = high // low
        nm, new = hm - lm * r, high - low * r
        lm, low, hm, high = nm, new, lm, low
    return lm % BLS_MODULUS
```

#### `roots_of_unity`

```python
def roots_of_unity(order: uint64) -> List[BLSFieldElement]:
    """
    Compute a list of roots of unity for a given order.
    The order must divide the BLS multiplicative group order, i.e. BLS_MODULUS - 1
    """
    assert (BLS_MODULUS - 1) % order == 0
    roots = []
    root_of_unity = pow(PRIMITIVE_ROOT_OF_UNITY, (BLS_MODULUS - 1) // order, BLS_MODULUS)

    current_root_of_unity = 1
    for i in range(SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE):
        roots.append(current_root_of_unity)
        current_root_of_unity = current_root_of_unity * root_of_unity % BLS_MODULUS
    return roots
```

### Field helper functions

#### `compute_powers`

```python
def compute_powers(x: BLSFieldElement, n: uint64) -> List[BLSFieldElement]:
    current_power = 1
    powers = []
    for _ in range(n):
        powers.append(BLSFieldElement(current_power))
        current_power = current_power * int(x) % BLS_MODULUS
    return powers
```

#### `low_degree_check`

```python
def low_degree_check(commitments: List[KZGCommitment]):
    """
    Checks that the commitments are on a low-degree polynomial.
    If there are 2*N commitments, that means they should lie on a polynomial
    of degree d = K - N - 1, where K = next_power_of_two(2*N)
    (The remaining positions are filled with 0, this is to make FFTs usable)

    For details see here: https://notes.ethereum.org/@dankrad/barycentric_low_degree_check
    """
    assert len(commitments) % 2 == 0
    N = len(commitments) // 2
    r = hash_to_bls_field(commitments, 0)
    K = next_power_of_two(2 * N)
    d = K - N - 1
    r_to_K = pow(r, N, K)
    roots = list_to_reverse_bit_order(roots_of_unity(K))

    # For an efficient implementation, B and Bprime should be precomputed
    def B(z):
        r = 1
        for w in roots[:d + 1]:
            r = r * (z - w) % BLS_MODULUS
        return r

    def Bprime(z):
        r = 0
        for i in range(d + 1):
            m = 1
            for w in roots[:i] + roots[i + 1:d + 1]:
                m = m * (z - w) % BLS_MODULUS
            r = (r + m) % BLS_MODULUS
        return r

    coefs = []
    for i in range(K):
        coefs.append( - (r_to_K - 1) * bls_modular_inverse(K * roots[i * (K - 1) % K] * (r - roots[i])) % BLS_MODULUS)
    for i in range(d + 1):
        coefs[i] = (coefs[i] + B(r) * bls_modular_inverse(Bprime(r) * (r - roots[i]))) % BLS_MODULUS

    assert elliptic_curve_lincomb(commitments, coefs) == bls.inf_G1()
```

#### `vector_lincomb`

```python
def vector_lincomb(vectors: List[List[BLSFieldElement]], scalars: List[BLSFieldElement]) -> List[BLSFieldElement]:
    """
    Compute a linear combination of field element vectors.
    """
    r = [0]*len(vectors[0])
    for v, a in zip(vectors, scalars):
        for i, x in enumerate(v):
            r[i] = (r[i] + a * x) % BLS_MODULUS
    return [BLSFieldElement(x) for x in r]
```

#### `bytes_to_field_elements`

```python
def bytes_to_field_elements(block: bytes) -> List[BLSFieldElement]:
    """
    Slices a block into 31-byte chunks that can fit into field elements.
    """
    sliced_block = [block[i:i + 31] for i in range(0, len(bytes), 31)]
    return [BLSFieldElement(int.from_bytes(x, "little")) for x in sliced_block]
```

## Polynomial operations

#### `add_polynomials`

```python
def add_polynomials(a: BLSPolynomialByCoefficients, b: BLSPolynomialByCoefficients) -> BLSPolynomialByCoefficients:
    """
    Sum the polynomials ``a`` and ``b`` given by their coefficients.
    """
    a, b = (a, b) if len(a) >= len(b) else (b, a)
    return [(a[i] + (b[i] if i < len(b) else 0)) % BLS_MODULUS for i in range(len(a))]
```

#### `multiply_polynomials`

```python
def multiply_polynomials(a: BLSPolynomialByCoefficients, b: BLSPolynomialByCoefficients) -> BLSPolynomialByCoefficients:
    """
    Multiplies the polynomials `a` and `b` given by their coefficients
    """
    r = [0]
    for power, coef in enumerate(a):
        summand = [0] * power + [coef * x % BLS_MODULUS for x in b]
        r = add_polynomials(r, summand)
    return r
```

#### `interpolate_polynomial`

```python
def interpolate_polynomial(xs: List[BLSFieldElement], ys: List[BLSFieldElement]) -> BLSPolynomialByCoefficients:
    """
    Lagrange interpolation
    """
    assert len(xs) == len(ys)
    r = [0]

    for i in range(len(xs)):
        summand = [ys[i]]
        for j in range(len(ys)):
            if j != i:
                weight_adjustment = bls_modular_inverse(xs[j] - xs[i])
                summand = multiply_polynomials(
                    summand, [weight_adjustment, ((BLS_MODULUS - weight_adjustment) * xs[i])]
                )
        r = add_polynomials(r, summand)

    return r
```

#### `evaluate_polynomial_in_evaluation_form`

```python
def evaluate_polynomial_in_evaluation_form(poly: BLSPolynomialByEvaluations, x: BLSFieldElement) -> BLSFieldElement:
    """
    Evaluates a polynomial (in evaluation form) at an arbitrary point
    """
    field_elements_per_blob = SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE
    roots = roots_of_unity(field_elements_per_blob)

    def A(z):
        r = 1
        for w in roots:
            r = r * (z - w) % BLS_MODULUS
        return r

    def Aprime(z):
        return field_elements_per_blob * pow(z, field_elements_per_blob - 1, BLS_MODULUS)

    r = 0
    inverses = [bls_modular_inverse(z - x) for z in roots]
    for i, x in enumerate(inverses):
        r += poly[i] * bls_modular_inverse(Aprime(roots[i])) * x % BLS_MODULUS
    r = r * A(x) % BLS_MODULUS
    return r
```

## KZG Operations

We are using the KZG10 polynomial commitment scheme (Kate, Zaverucha and
Goldberg, 2010: https://www.iacr.org/archive/asiacrypt2010/6477178/6477178.pdf).

### Elliptic curve helper functions

#### `elliptic_curve_lincomb`

```python
def elliptic_curve_lincomb(points: List[KZGCommitment], scalars: List[BLSFieldElement]) -> KZGCommitment:
    """
    BLS multiscalar multiplication. This function can be optimized using Pippenger's algorithm and variants.
    This is a non-optimized implementation.
    """
    r = bls.inf_G1()
    for x, a in zip(points, scalars):
        r = r.add(x.mult(a))
    return r
```

### Hash to field

#### `hash_to_bls_field`

```python
def hash_to_bls_field(x: Container, challenge_number: uint64) -> BLSFieldElement:
    """
    This function is used to generate Fiat-Shamir challenges. The output is not uniform over the BLS field.
    """
    return (
        (int.from_bytes(hash(hash_tree_root(x) + int.to_bytes(challenge_number, 32, "little")), "little"))
        % BLS_MODULUS
    )
```

### KZG operations

#### `verify_kzg_proof`

```python
def verify_kzg_proof(commitment: KZGCommitment, x: BLSFieldElement, y: BLSFieldElement, proof: KZGCommitment) -> None:
    """
    Check that `proof` is a valid KZG proof for the polynomial committed to by `commitment` evaluated
    at `x` equals `y`.
    """
    zero_poly = G2_SETUP[1].add(G2_SETUP[0].mult(x).neg())

    assert (
        bls.Pairing(proof, zero_poly)
        == bls.Pairing(commitment.add(G1_SETUP[0].mult(y).neg), G2_SETUP[0])
    )
```

#### `verify_kzg_multiproof`

```python
def verify_kzg_multiproof(commitment: KZGCommitment,
                          xs: List[BLSFieldElement],
                          ys: List[BLSFieldElement],
                          proof: KZGCommitment) -> None:
    """
    Verify a KZG multiproof.
    """
    zero_poly = elliptic_curve_lincomb(G2_SETUP[:len(xs)], interpolate_polynomial(xs, [0] * len(ys)))
    interpolated_poly = elliptic_curve_lincomb(G2_SETUP[:len(xs)], interpolate_polynomial(xs, ys))

    assert (
        bls.Pairing(proof, zero_poly)
        == bls.Pairing(commitment.add(interpolated_poly.neg()), G2_SETUP[0])
    )
```

#### `verify_degree_proof`

```python
def verify_degree_proof(commitment: KZGCommitment, degree_bound: uint64, proof: KZGCommitment):
    """
    Verifies that the commitment is of polynomial degree < degree_bound.
    """

    assert (
        bls.Pairing(proof, G2_SETUP[0])
        == bls.Pairing(commitment, G2_SETUP[-degree_bound])
    )
```
