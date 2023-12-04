# Deneb -- Polynomial Commitments

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Preset](#preset)
  - [Samples](#samples)
  - [Crypto](#crypto)
- [Helper functions](#helper-functions)
  - [Linear combinations](#linear-combinations)
    - [`g2_lincomb`](#g2_lincomb)
  - [FFTs](#ffts)
    - [`_simple_ft_field`](#_simple_ft_field)
    - [`_fft_field`](#_fft_field)
    - [`fft_field`](#fft_field)
  - [Polynomials in coefficient form](#polynomials-in-coefficient-form)
    - [`polynomial_eval_to_coeff`](#polynomial_eval_to_coeff)
    - [`polynomial_coeff_to_eval`](#polynomial_coeff_to_eval)
    - [`add_polynomialcoeff`](#add_polynomialcoeff)
    - [`neg_polynomialcoeff`](#neg_polynomialcoeff)
    - [`multiply_polynomialcoeff`](#multiply_polynomialcoeff)
    - [`divide_polynomialcoeff`](#divide_polynomialcoeff)
    - [`shift_polynomialcoeff`](#shift_polynomialcoeff)
    - [`interpolate_polynomialcoeff`](#interpolate_polynomialcoeff)
    - [`zero_polynomialcoeff`](#zero_polynomialcoeff)
    - [`evaluate_polynomialcoeff`](#evaluate_polynomialcoeff)
  - [KZG multiproofs](#kzg-multiproofs)
    - [`compute_kzg_proof_multi_impl`](#compute_kzg_proof_multi_impl)
    - [`verify_kzg_proof_multi_impl`](#verify_kzg_proof_multi_impl)
  - [Sample cosets](#sample-cosets)
    - [`coset_for_sample`](#coset_for_sample)
- [Samples](#samples-1)
  - [Sample computation](#sample-computation)
    - [`compute_samples_and_proofs`](#compute_samples_and_proofs)
    - [`compute_samples`](#compute_samples)
  - [Sample verification](#sample-verification)
    - [`verify_sample_proof`](#verify_sample_proof)
    - [`verify_sample_proof_batch`](#verify_sample_proof_batch)
- [Reconstruction](#reconstruction)
  - [`recover_samples_impl`](#recover_samples_impl)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document extends [polynomial-commitments.md](polynomial-commitments.md) with the functions required for data availability sampling (DAS). It is not part of the core Deneb spec but an extension that can be optionally implemented to allow nodes to reduce their load using DAS.

For any KZG library extended to support DAS, functions flagged as "Public method" MUST be provided by the underlying KZG library as public functions. All other functions are private functions used internally by the KZG library.

Public functions MUST accept raw bytes as input and perform the required cryptographic normalization before invoking any internal functions.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `PolynomialCoeff` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_BLOB]` | A polynomial in coefficient form |

## Constants

| Name | Value | Notes |
| - | - | - |

## Preset

### Samples

| Name | Value | Description |
| - | - | - |
| `FIELD_ELEMENTS_PER_SAMPLE` | `uint64(64)` | Number of field elements in a sample |
| `BYTES_PER_SAMPLE` | `FIELD_ELEMENTS_PER_SAMPLE * BYTES_PER_FIELD_ELEMENT` | The number of bytes in a sample |
| `SAMPLES_PER_BLOB` | `((2 * FIELD_ELEMENTS_PER_BLOB) // FIELD_ELEMENTS_PER_SAMPLE)` | The number of samples for a blob |

### Crypto

| Name | Value | Description |
| - | - | - |
| `ROOT_OF_UNITY2` | `pow(PRIMITIVE_ROOT_OF_UNITY, (BLS_MODULUS - 1) // int(FIELD_ELEMENTS_PER_BLOB * 2), BLS_MODULUS)` | Root of unity of order FIELD_ELEMENTS_PER_BLOB * 2 over the BLS12-381 field |
| `ROOTS_OF_UNITY2` | `([pow(ROOT_OF_UNITY, i, BLS_MODULUS) for i in range(FIELD_ELEMENTS_PER_BLOB * 2)])` | Roots of unity of order FIELD_ELEMENTS_PER_BLOB * 2 over the BLS12-381 field |
| `ROOT_OF_UNITY_S` | `pow(PRIMITIVE_ROOT_OF_UNITY, (BLS_MODULUS - 1) // int(SAMPLES_PER_BLOB), BLS_MODULUS)` | Root of unity of order SAMPLES_PER_BLOB over the BLS12-381 field |
| `ROOTS_OF_UNITY_S` | `([pow(ROOT_OF_UNITY, i, BLS_MODULUS) for i in range(SAMPLES_PER_BLOB)])` | Roots of unity of order SAMPLES_PER_BLOB over the BLS12-381 field |

## Helper functions

### Linear combinations

#### `g2_lincomb`

```python
def g2_lincomb(points: Sequence[KZGCommitment], scalars: Sequence[BLSFieldElement]) -> Bytes96:
    """
    BLS multiscalar multiplication in G2. This function can be optimized using Pippenger's algorithm and variants.
    """
    assert len(points) == len(scalars)
    result = bls.Z2()
    for x, a in zip(points, scalars):
        result = bls.add(result, bls.multiply(bls.bytes96_to_G2(x), a))
    return Bytes96(bls.G2_to_bytes96(result))
```

### FFTs

#### `_simple_ft_field`

```python
def _simple_ft_field(vals, roots_of_unity):
    assert len(vals) == len(roots_of_unity)
    L = len(roots_of_unity)
    o = []
    for i in range(L):
        last = 0
        for j in range(L):
            last += int(vals[j]) * int(roots_of_unity[(i * j) % L]) % BLS_MODULUS
        o.append(last % BLS_MODULUS)
    return o
```

#### `_fft_field`

```python
def _fft_field(vals, roots_of_unity):
    if len(vals) <= 4:
        return _simple_ft_field(vals, roots_of_unity)
    L = _fft_field(vals[::2], roots_of_unity[::2])
    R = _fft_field(vals[1::2], roots_of_unity[::2])
    o = [0 for i in vals]
    for i, (x, y) in enumerate(zip(L, R)):
        y_times_root = int(y) * int(roots_of_unity[i]) % BLS_MODULUS
        o[i] = (x + y_times_root) % BLS_MODULUS
        o[i + len(L)] = (x - y_times_root + BLS_MODULUS) % BLS_MODULUS
    return o
```

#### `fft_field`

```python
def fft_field(vals, roots_of_unity, inv=False):
    if inv:
        # Inverse FFT
        invlen = pow(len(vals), BLS_MODULUS - 2, BLS_MODULUS)
        return [(x * invlen) % BLS_MODULUS for x in
                _fft_field(vals, roots_of_unity[0:1] + roots_of_unity[:0:-1])]
    else:
        # Regular FFT
        return _fft_field(vals, roots_of_unity)
```


### Polynomials in coefficient form

#### `polynomial_eval_to_coeff`

```python
def polynomial_eval_to_coeff(polynomial: Polynomial) -> PolynomialCoeff:
    """
    Interpolates a polynomial (given in evaluation form) to a polynomial in coefficient form.
    """
    polynomial_coeff = fft_field(bit_reversal_permutation(list(polynomial)), list(ROOTS_OF_UNITY), inv=True)

    return polynomial_coeff
```

#### `polynomial_coeff_to_eval`

```python
def polynomial_coeff_to_eval(polynomial_coeff: PolynomialCoeff) -> Polynomial:
    """
    Evaluates a polynomial (given in coefficient form) to a polynomial in evaluation form.
    """

    if len(polynomial_coeff) > FIELD_ELEMENTS_PER_BLOB:
        assert all(c == 0 for c in polynomial_coeff[FIELD_ELEMENTS_PER_BLOB:])

    polynomial = bit_reversal_permutation(fft_field(list(polynomial_coeff), list(ROOTS_OF_UNITY), inv=False))

    return polynomial
```

#### `add_polynomialcoeff`

```python
def add_polynomialcoeff(a: PolynomialCoeff, b: PolynomialCoeff) -> PolynomialCoeff:
    """
    Sum the coefficient form polynomials ``a`` and ``b``.
    """
    a, b = (a, b) if len(a) >= len(b) else (b, a)
    return [(a[i] + (b[i] if i < len(b) else 0)) % BLS_MODULUS for i in range(len(a))]
```

#### `neg_polynomialcoeff`

```python
def neg_polynomialcoeff(a: PolynomialCoeff) -> PolynomialCoeff:
    """
    Negative of coefficient form polynomial ``a``
    """
    return [(BLS_MODULUS - x) % BLS_MODULUS for x in a]
```

#### `multiply_polynomialcoeff`

```python
def multiply_polynomialcoeff(a: PolynomialCoeff, b: PolynomialCoeff) -> PolynomialCoeff:
    """
    Multiplies the coefficient form polynomials ``a`` and ``b``
    """
    r = [0]
    for power, coef in enumerate(a):
        summand = [0] * power + [int(coef) * int(x) % BLS_MODULUS for x in b]
        r = add_polynomialcoeff(r, summand)
    return r
```
#### `divide_polynomialcoeff`

```python
def divide_polynomialcoeff(a: PolynomialCoeff, b: PolynomialCoeff) -> PolynomialCoeff:
    """
    Long polynomial division for two coefficient form polynomials ``a`` and ``b``
    """
    a = [x for x in a]
    o = []
    apos = len(a) - 1
    bpos = len(b) - 1
    diff = apos - bpos
    while diff >= 0:
        quot = div(a[apos], b[bpos])
        o.insert(0, quot)
        for i in range(bpos, -1, -1):
            a[diff + i] = (int(a[diff + i]) - int(b[i]) * int(quot)) % BLS_MODULUS
        apos -= 1
        diff -= 1
    return [x % BLS_MODULUS for x in o]
```

#### `shift_polynomialcoeff`

```python
def shift_polynomialcoeff(poly, factor):
    """
    Shift the evaluation of a polynomial in coefficient form by factor.
    This results in a new polynomial g(x) = f(factor * x)
    """
    factor_power = 1
    inv_factor = pow(int(factor), BLS_MODULUS - 2, BLS_MODULUS)
    o = []
    for p in poly:
        o.append(int(p) * factor_power % BLS_MODULUS)
        factor_power = factor_power * inv_factor % BLS_MODULUS
    return o
```

#### `interpolate_polynomialcoeff`

```python
def interpolate_polynomialcoeff(xs: Sequence[BLSFieldElement], ys: Sequence[BLSFieldElement]) -> PolynomialCoeff:
    """
    Lagrange interpolation: Finds the lowest degree polynomial that takes the value ``ys[i]`` at ``x[i]``
    for all i.
    Outputs a coefficient form polynomial. Leading coefficients may be zero.
    """
    assert len(xs) == len(ys)
    r = [0]

    for i in range(len(xs)):
        summand = [ys[i]]
        for j in range(len(ys)):
            if j != i:
                weight_adjustment = bls_modular_inverse(int(xs[i]) - int(xs[j]))
                summand = multiply_polynomialcoeff(
                    summand, [(- int(weight_adjustment) * int(xs[j])) % BLS_MODULUS, weight_adjustment]
                )
        r = add_polynomialcoeff(r, summand)
    
    return r
```

#### `zero_polynomialcoeff`

```python
def zero_polynomialcoeff(xs: Sequence[BLSFieldElement]) -> PolynomialCoeff:
    """
    Compute a zero polynomial on ``xs`` (in coefficient form)
    """
    p = [1]
    for x in xs:
        p = multiply_polynomialcoeff(p, [-int(x), 1])
    return p
```

#### `evaluate_polynomialcoeff`

```python
def evaluate_polynomialcoeff(polynomial_coeff: PolynomialCoeff, z: BLSFieldElement) -> BLSFieldElement:
    """
    Evaluate a coefficient form polynomial at ``z`` using Horner's schema
    """
    y = 0
    for coef in polynomial_coeff[::-1]:
        y = (int(y) * int(z) + coef) % BLS_MODULUS
    return BLSFieldElement(y % BLS_MODULUS)
```

### KZG multiproofs

Extended KZG functions for multiproofs

#### `compute_kzg_proof_multi_impl`

```python
def compute_kzg_proof_multi_impl(
        polynomial_coeff: PolynomialCoeff,
        zs: Sequence[BLSFieldElement]) -> Tuple[KZGProof, Sequence[BLSFieldElement]]:
    """
    Helper function that computes multi-evaluation KZG proofs.
    """

    # For all x_i, compute p(x_i) - p(z)
    ys = [evaluate_polynomialcoeff(polynomial_coeff, z) for z in zs]
    interpolation_polynomial = interpolate_polynomialcoeff(zs, ys)
    polynomial_shifted = add_polynomialcoeff(polynomial_coeff, neg_polynomialcoeff(interpolation_polynomial))

    # For all x_i, compute (x_i - z)
    denominator_poly = zero_polynomialcoeff(zs)

    # Compute the quotient polynomial directly in evaluation form
    quotient_polynomial = divide_polynomialcoeff(polynomial_shifted, denominator_poly)

    return KZGProof(g1_lincomb(KZG_SETUP_G1[:len(quotient_polynomial)], quotient_polynomial)), ys
```

#### `verify_kzg_proof_multi_impl`

```python
def verify_kzg_proof_multi_impl(commitment: KZGCommitment,
                                zs: BLSFieldElement,
                                ys: BLSFieldElement,
                                proof: KZGProof) -> bool:
    """
    Helper function that verifies a KZG multiproof
    """
    zero_poly = g2_lincomb(KZG_SETUP_G2[:len(zs) + 1], zero_polynomialcoeff(zs))
    interpolated_poly = g1_lincomb(KZG_SETUP_G1[:len(zs)], interpolate_polynomialcoeff(zs, ys))

    return (bls.pairing_check([
        [bls.bytes48_to_G1(proof), bls.bytes96_to_G2(zero_poly)],
        [
            bls.add(bls.bytes48_to_G1(commitment), bls.neg(bls.bytes48_to_G1(interpolated_poly))),
            bls.neg(bls.bytes96_to_G2(KZG_SETUP_G2[0])),
        ],
    ]))
```

### Sample cosets

#### `coset_for_sample`

```python
def coset_for_sample(sample_id: int) -> Vector[BLSFieldElement, FIELD_ELEMENTS_PER_SAMPLE]:
    """
    Get the subgroup for a given ``sample_id``
    """
    assert sample_id < SAMPLES_PER_BLOB
    roots_of_unity_brp = bit_reversal_permutation(ROOTS_OF_UNITY2)
    return Vector[BLSFieldElement, FIELD_ELEMENTS_PER_SAMPLE](
        roots_of_unity_brp[FIELD_ELEMENTS_PER_SAMPLE * sample_id:FIELD_ELEMENTS_PER_SAMPLE * (sample_id + 1)]
    )
```

## Samples

### Sample computation

#### `compute_samples_and_proofs`

```python
def compute_samples_and_proofs(blob: Blob) -> Tuple[
        Vector[Vector[BLSFieldElement, FIELD_ELEMENTS_PER_SAMPLE], SAMPLES_PER_BLOB],
        Vector[KZGProof, SAMPLES_PER_BLOB]]:
    """
    Compute all the sample proofs for one blob. This is an inefficient O(n^2) algorithm,
    for performant implementation the FK20 algorithm that runs in O(n log n) should be
    used instead.

    Public method.
    """
    polynomial = blob_to_polynomial(blob)
    polynomial_coeff = polynomial_eval_to_coeff(polynomial)

    samples = []
    proofs = []

    for i in range(SAMPLES_PER_BLOB):
        coset = coset_for_sample(i)
        proof, ys = compute_kzg_proof_multi_impl(polynomial_coeff, coset)
        samples.append(ys)
        proofs.append(proof)

    return samples, proofs
```

#### `compute_samples`

```python
def compute_samples(blob: Blob) -> Vector[Vector[BLSFieldElement, FIELD_ELEMENTS_PER_SAMPLE], SAMPLES_PER_BLOB]:
    """
    Compute the sample data for a blob (without computing the proofs).

    Public method.
    """
    polynomial = blob_to_polynomial(blob)
    polynomial_coeff = polynomial_eval_to_coeff(polynomial)

    extended_data = fft_field(polynomial_coeff + [0] * FIELD_ELEMENTS_PER_BLOB, ROOTS_OF_UNITY2)
    extended_data_rbo = bit_reversal_permutation(extended_data)
    return [extended_data_rbo[i * FIELD_ELEMENTS_PER_SAMPLE:(i + 1) * FIELD_ELEMENTS_PER_SAMPLE]
            for i in range(SAMPLES_PER_BLOB)]
```

### Sample verification

#### `verify_sample_proof`

```python
def verify_sample_proof(commitment: KZGCommitment,
                        sample_id: int,
                        data: Vector[BLSFieldElement, FIELD_ELEMENTS_PER_SAMPLE],
                        proof: KZGProof) -> bool:
    """
    Check a sample proof

    Publiiic method.
    """
    coset = coset_for_sample(sample_id)

    return verify_kzg_proof_multi_impl(commitment, coset, data, proof)
```

#### `verify_sample_proof_batch`

```python
def verify_sample_proof_batch(row_commitments: Sequence[KZGCommitment],
                              row_ids: Sequence[int],
                              column_ids: Sequence[int],
                              datas: Sequence[Vector[BLSFieldElement, FIELD_ELEMENTS_PER_SAMPLE]],
                              proofs: Sequence[KZGProof]) -> bool:
    """
    Check multiple sample proofs. This function implements the naive algorithm of checking every sample
    individually; an efficient algorithm can be found here:
    https://ethresear.ch/t/a-universal-verification-equation-for-data-availability-sampling/13240

    Public method.
    """

    # Get commitments via row IDs
    commitments = [row_commitments[row_id] for row_id in row_ids]
    
    return all(verify_kzg_proof_multi_impl(commitment, coset_for_sample(column_id), data, proof) 
               for commitment, column_id, data, proof in zip(commitments, column_ids, datas, proofs))
```

## Reconstruction

### `recover_samples_impl`

```python
def recover_samples_impl(samples: Sequence[Tuple[int, Sequence[BLSFieldElement]]]) -> Polynomial:
    """
    Recovers a polynomial from 2 * FIELD_ELEMENTS_PER_SAMPLE evaluations, half of which can be missing.

    This algorithm uses FFTs to recover samples faster than using Lagrange implementation. However,
    a faster version thanks to Qi Zhou can be found here:
    https://github.com/ethereum/research/blob/51b530a53bd4147d123ab3e390a9d08605c2cdb8/polynomial_reconstruction/polynomial_reconstruction_danksharding.py

    Public method.
    """
    assert len(samples) >= SAMPLES_PER_BLOB // 2
    sample_ids = [sample_id for sample_id, _ in samples]
    missing_sample_ids = [sample_id for sample_id in range(SAMPLES_PER_BLOB) if sample_id not in sample_ids]
    short_zero_poly = zero_polynomialcoeff([ROOTS_OF_UNITY_S[reverse_bits(sample_id, SAMPLES_PER_BLOB)] for sample_id in missing_sample_ids])

    full_zero_poly = []
    for i in short_zero_poly:
        full_zero_poly.append(i)
        full_zero_poly.extend([0] * (FIELD_ELEMENTS_PER_SAMPLE - 1))
    full_zero_poly = full_zero_poly + [0] * (2 * FIELD_ELEMENTS_PER_BLOB - len(full_zero_poly))

    zero_poly_eval = fft_field(full_zero_poly, ROOTS_OF_UNITY2)
    zero_poly_eval_brp = bit_reversal_permutation(zero_poly_eval)
    for sample_id in missing_sample_ids:
        assert zero_poly_eval_brp[sample_id * FIELD_ELEMENTS_PER_SAMPLE:(sample_id + 1) * FIELD_ELEMENTS_PER_SAMPLE] == \
            [0] * FIELD_ELEMENTS_PER_SAMPLE
    for sample_id in sample_ids:
        assert all(a != 0 for a in zero_poly_eval_brp[sample_id * FIELD_ELEMENTS_PER_SAMPLE:(sample_id + 1) * FIELD_ELEMENTS_PER_SAMPLE])

    extended_evaluation_rbo = [0] * FIELD_ELEMENTS_PER_BLOB * 2
    for sample_id, sample_data in samples:
        extended_evaluation_rbo[sample_id * FIELD_ELEMENTS_PER_SAMPLE:(sample_id + 1) * FIELD_ELEMENTS_PER_SAMPLE] = \
            sample_data
    extended_evaluation = bit_reversal_permutation(extended_evaluation_rbo)

    extended_evaluation_times_zero = [a * b % BLS_MODULUS for a, b in zip(zero_poly_eval, extended_evaluation)]

    extended_evaluations_fft = fft_field(extended_evaluation_times_zero, ROOTS_OF_UNITY2, inv=True)

    shift_factor = PRIMITIVE_ROOT_OF_UNITY
    shift_inv = div(1, PRIMITIVE_ROOT_OF_UNITY)

    shifted_extended_evaluation = shift_polynomialcoeff(extended_evaluations_fft, shift_factor)
    shifted_zero_poly = shift_polynomialcoeff(full_zero_poly, shift_factor)

    eval_shifted_extended_evaluation = fft_field(shifted_extended_evaluation, ROOTS_OF_UNITY2)
    eval_shifted_zero_poly = fft_field(shifted_zero_poly, ROOTS_OF_UNITY2)
    
    eval_shifted_reconstructed_poly = [
        div(a, b)
        for a, b in zip(eval_shifted_extended_evaluation, eval_shifted_zero_poly)
    ]

    shifted_reconstructed_poly = fft_field(eval_shifted_reconstructed_poly, ROOTS_OF_UNITY2, inv=True)

    reconstructed_poly = shift_polynomialcoeff(shifted_reconstructed_poly, shift_inv)

    reconstructed_data = bit_reversal_permutation(fft_field(reconstructed_poly, ROOTS_OF_UNITY2))

    for sample_id, sample_data in samples:
        assert reconstructed_data[sample_id * FIELD_ELEMENTS_PER_SAMPLE:(sample_id + 1) * FIELD_ELEMENTS_PER_SAMPLE] == \
            sample_data
    
    return reconstructed_data
```
