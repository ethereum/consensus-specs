# EIP-7594 -- Polynomial Commitments

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Preset](#preset)
  - [Cells](#cells)
- [Helper functions](#helper-functions)
  - [BLS12-381 helpers](#bls12-381-helpers)
    - [`bytes_to_cell`](#bytes_to_cell)
  - [Linear combinations](#linear-combinations)
    - [`g2_lincomb`](#g2_lincomb)
  - [FFTs](#ffts)
    - [`_fft_field`](#_fft_field)
    - [`fft_field`](#fft_field)
  - [Polynomials in coefficient form](#polynomials-in-coefficient-form)
    - [`polynomial_eval_to_coeff`](#polynomial_eval_to_coeff)
    - [`add_polynomialcoeff`](#add_polynomialcoeff)
    - [`neg_polynomialcoeff`](#neg_polynomialcoeff)
    - [`multiply_polynomialcoeff`](#multiply_polynomialcoeff)
    - [`divide_polynomialcoeff`](#divide_polynomialcoeff)
    - [`shift_polynomialcoeff`](#shift_polynomialcoeff)
    - [`interpolate_polynomialcoeff`](#interpolate_polynomialcoeff)
    - [`vanishing_polynomialcoeff`](#vanishing_polynomialcoeff)
    - [`evaluate_polynomialcoeff`](#evaluate_polynomialcoeff)
  - [KZG multiproofs](#kzg-multiproofs)
    - [`compute_kzg_proof_multi_impl`](#compute_kzg_proof_multi_impl)
    - [`verify_kzg_proof_multi_impl`](#verify_kzg_proof_multi_impl)
  - [Cell cosets](#cell-cosets)
    - [`coset_for_cell`](#coset_for_cell)
- [Cells](#cells-1)
  - [Cell computation](#cell-computation)
    - [`compute_cells_and_proofs`](#compute_cells_and_proofs)
    - [`compute_cells`](#compute_cells)
  - [Cell verification](#cell-verification)
    - [`verify_cell_proof`](#verify_cell_proof)
    - [`verify_cell_proof_batch`](#verify_cell_proof_batch)
- [Reconstruction](#reconstruction)
  - [`construct_vanishing_polynomial`](#construct_vanishing_polynomial)
  - [`recover_shifted_data`](#recover_shifted_data)
  - [`recover_original_data`](#recover_original_data)
  - [`recover_polynomial`](#recover_polynomial)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document extends [polynomial-commitments.md](polynomial-commitments.md) with the functions required for data availability sampling (DAS). It is not part of the core Deneb spec but an extension that can be optionally implemented to allow nodes to reduce their load using DAS.

For any KZG library extended to support DAS, functions flagged as "Public method" MUST be provided by the underlying KZG library as public functions. All other functions are private functions used internally by the KZG library.

Public functions MUST accept raw bytes as input and perform the required cryptographic normalization before invoking any internal functions.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `PolynomialCoeff` | `List[BLSFieldElement, FIELD_ELEMENTS_PER_EXT_BLOB]` | A polynomial in coefficient form |
| `Cell` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]` | The unit of blob data that can come with their own KZG proofs |
| `CellID` | `uint64` | Cell identifier |
| `RowIndex` | `uint64` | Row identifier |
| `ColumnIndex` | `uint64` | Column identifier |

## Constants

| Name | Value | Notes |
| - | - | - |

## Preset

### Cells

Cells are the smallest unit of blob data that can come with their own KZG proofs. Samples can be constructed from one or several cells (e.g. an individual cell or line).

| Name | Value | Description |
| - | - | - |
| `FIELD_ELEMENTS_PER_EXT_BLOB` | `2 * FIELD_ELEMENTS_PER_BLOB` | Number of field elements in a Reed-Solomon extended blob |
| `FIELD_ELEMENTS_PER_CELL` | `uint64(64)` | Number of field elements in a cell |
| `BYTES_PER_CELL` | `FIELD_ELEMENTS_PER_CELL * BYTES_PER_FIELD_ELEMENT` | The number of bytes in a cell |
| `CELLS_PER_BLOB` | `FIELD_ELEMENTS_PER_EXT_BLOB // FIELD_ELEMENTS_PER_CELL` | The number of cells in a blob |
| `RANDOM_CHALLENGE_KZG_CELL_BATCH_DOMAIN` | `b'RCKZGCBATCH__V1_'` |

## Helper functions

### BLS12-381 helpers

#### `bytes_to_cell`

```python
def bytes_to_cell(cell_bytes: Vector[Bytes32, FIELD_ELEMENTS_PER_CELL]) -> Cell:
    """
    Convert untrusted bytes into a Cell.
    """
    return [bytes_to_bls_field(element) for element in cell_bytes]
```

### Linear combinations

#### `g2_lincomb`

```python
def g2_lincomb(points: Sequence[G2Point], scalars: Sequence[BLSFieldElement]) -> Bytes96:
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

#### `_fft_field`

```python
def _fft_field(vals: Sequence[BLSFieldElement],
               roots_of_unity: Sequence[BLSFieldElement]) -> Sequence[BLSFieldElement]:
    if len(vals) == 1:
        return vals
    L = _fft_field(vals[::2], roots_of_unity[::2])
    R = _fft_field(vals[1::2], roots_of_unity[::2])
    o = [BLSFieldElement(0) for _ in vals]
    for i, (x, y) in enumerate(zip(L, R)):
        y_times_root = (int(y) * int(roots_of_unity[i])) % BLS_MODULUS
        o[i] = BLSFieldElement((int(x) + y_times_root) % BLS_MODULUS)
        o[i + len(L)] = BLSFieldElement((int(x) - y_times_root + BLS_MODULUS) % BLS_MODULUS)
    return o
```

#### `fft_field`

```python
def fft_field(vals: Sequence[BLSFieldElement],
              roots_of_unity: Sequence[BLSFieldElement],
              inv: bool=False) -> Sequence[BLSFieldElement]:
    if inv:
        # Inverse FFT
        invlen = pow(len(vals), BLS_MODULUS - 2, BLS_MODULUS)
        return [BLSFieldElement((int(x) * invlen) % BLS_MODULUS)
                for x in _fft_field(vals, list(roots_of_unity[0:1]) + list(roots_of_unity[:0:-1]))]
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
    roots_of_unity = compute_roots_of_unity(FIELD_ELEMENTS_PER_BLOB)
    polynomial_coeff = fft_field(bit_reversal_permutation(list(polynomial)), roots_of_unity, inv=True)

    return polynomial_coeff
```

#### `add_polynomialcoeff`

```python
def add_polynomialcoeff(a: PolynomialCoeff, b: PolynomialCoeff) -> PolynomialCoeff:
    """
    Sum the coefficient form polynomials ``a`` and ``b``.
    """
    a, b = (a, b) if len(a) >= len(b) else (b, a)
    length_a = len(a)
    length_b = len(b)
    return [(a[i] + (b[i] if i < length_b else 0)) % BLS_MODULUS for i in range(length_a)]
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
    assert len(a) + len(b) <= FIELD_ELEMENTS_PER_EXT_BLOB

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
def shift_polynomialcoeff(polynomial_coeff: PolynomialCoeff, factor: BLSFieldElement) -> PolynomialCoeff:
    """
    Shift the evaluation of a polynomial in coefficient form by factor.
    This results in a new polynomial g(x) = f(factor * x)
    """
    factor_power = 1
    inv_factor = pow(int(factor), BLS_MODULUS - 2, BLS_MODULUS)
    o = []
    for p in polynomial_coeff:
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

#### `vanishing_polynomialcoeff`

```python
def vanishing_polynomialcoeff(xs: Sequence[BLSFieldElement]) -> PolynomialCoeff:
    """
    Compute the vanishing polynomial on ``xs`` (in coefficient form)
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
        y = (int(y) * int(z) + int(coef)) % BLS_MODULUS
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
    denominator_poly = vanishing_polynomialcoeff(zs)

    # Compute the quotient polynomial directly in evaluation form
    quotient_polynomial = divide_polynomialcoeff(polynomial_shifted, denominator_poly)

    return KZGProof(g1_lincomb(KZG_SETUP_G1_MONOMIAL[:len(quotient_polynomial)], quotient_polynomial)), ys
```

#### `verify_kzg_proof_multi_impl`

```python
def verify_kzg_proof_multi_impl(commitment: KZGCommitment,
                                zs: Sequence[BLSFieldElement],
                                ys: Sequence[BLSFieldElement],
                                proof: KZGProof) -> bool:
    """
    Helper function that verifies a KZG multiproof
    """

    assert len(zs) == len(ys)

    zero_poly = g2_lincomb(KZG_SETUP_G2_MONOMIAL[:len(zs) + 1], vanishing_polynomialcoeff(zs))
    interpolated_poly = g1_lincomb(KZG_SETUP_G1_MONOMIAL[:len(zs)], interpolate_polynomialcoeff(zs, ys))

    return (bls.pairing_check([
        [bls.bytes48_to_G1(proof), bls.bytes96_to_G2(zero_poly)],
        [
            bls.add(bls.bytes48_to_G1(commitment), bls.neg(bls.bytes48_to_G1(interpolated_poly))),
            bls.neg(bls.bytes96_to_G2(KZG_SETUP_G2_MONOMIAL[0])),
        ],
    ]))
```

### Cell cosets

#### `coset_for_cell`

```python
def coset_for_cell(cell_id: CellID) -> Cell:
    """
    Get the coset for a given ``cell_id``
    """
    assert cell_id < CELLS_PER_BLOB
    roots_of_unity_brp = bit_reversal_permutation(
        compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB)
    )
    return Cell(roots_of_unity_brp[FIELD_ELEMENTS_PER_CELL * cell_id:FIELD_ELEMENTS_PER_CELL * (cell_id + 1)])
```

## Cells

### Cell computation

#### `compute_cells_and_proofs`

```python
def compute_cells_and_proofs(blob: Blob) -> Tuple[
        Vector[Cell, CELLS_PER_BLOB],
        Vector[KZGProof, CELLS_PER_BLOB]]:
    """
    Compute all the cell proofs for one blob. This is an inefficient O(n^2) algorithm,
    for performant implementation the FK20 algorithm that runs in O(n log n) should be
    used instead.

    Public method.
    """
    polynomial = blob_to_polynomial(blob)
    polynomial_coeff = polynomial_eval_to_coeff(polynomial)

    cells = []
    proofs = []

    for i in range(CELLS_PER_BLOB):
        coset = coset_for_cell(i)
        proof, ys = compute_kzg_proof_multi_impl(polynomial_coeff, coset)
        cells.append(ys)
        proofs.append(proof)

    return cells, proofs
```

#### `compute_cells`

```python
def compute_cells(blob: Blob) -> Vector[Cell, CELLS_PER_BLOB]:
    """
    Compute the cell data for a blob (without computing the proofs).

    Public method.
    """
    polynomial = blob_to_polynomial(blob)
    polynomial_coeff = polynomial_eval_to_coeff(polynomial)

    extended_data = fft_field(polynomial_coeff + [0] * FIELD_ELEMENTS_PER_BLOB,
                              compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB))
    extended_data_rbo = bit_reversal_permutation(extended_data)
    return [extended_data_rbo[i * FIELD_ELEMENTS_PER_CELL:(i + 1) * FIELD_ELEMENTS_PER_CELL]
            for i in range(CELLS_PER_BLOB)]
```

### Cell verification

#### `verify_cell_proof`

```python
def verify_cell_proof(commitment_bytes: Bytes48,
                      cell_id: CellID,
                      cell_bytes: Vector[Bytes32, FIELD_ELEMENTS_PER_CELL],
                      proof_bytes: Bytes48) -> bool:
    """
    Check a cell proof

    Public method.
    """
    coset = coset_for_cell(cell_id)

    return verify_kzg_proof_multi_impl(
        bytes_to_kzg_commitment(commitment_bytes),
        coset,
        bytes_to_cell(cell_bytes),
        bytes_to_kzg_proof(proof_bytes))
```

#### `verify_cell_proof_batch`

```python
def verify_cell_proof_batch(row_commitments_bytes: Sequence[Bytes48],
                            row_indices: Sequence[RowIndex],
                            column_indices: Sequence[ColumnIndex],
                            cells_bytes: Sequence[Vector[Bytes32, FIELD_ELEMENTS_PER_CELL]],
                            proofs_bytes: Sequence[Bytes48]) -> bool:
    """
    Verify a set of cells, given their corresponding proofs and their coordinates (row_id, column_id) in the blob
    matrix. The list of all commitments is also provided in row_commitments_bytes.

    This function implements the naive algorithm of checking every cell
    individually; an efficient algorithm can be found here:
    https://ethresear.ch/t/a-universal-verification-equation-for-data-availability-sampling/13240

    This implementation does not require randomness, but for the algorithm that
    requires it, `RANDOM_CHALLENGE_KZG_CELL_BATCH_DOMAIN` should be used to compute
    the challenge value.

    Public method.
    """
    assert len(cells_bytes) == len(proofs_bytes) == len(row_indices) == len(column_indices)

    # Get commitments via row IDs
    commitments_bytes = [row_commitments_bytes[row_index] for row_index in row_indices]

    # Get objects from bytes
    commitments = [bytes_to_kzg_commitment(commitment_bytes) for commitment_bytes in commitments_bytes]
    cells = [bytes_to_cell(cell_bytes) for cell_bytes in cells_bytes]
    proofs = [bytes_to_kzg_proof(proof_bytes) for proof_bytes in proofs_bytes]

    return all(
        verify_kzg_proof_multi_impl(commitment, coset_for_cell(column_index), cell, proof)
        for commitment, column_index, cell, proof in zip(commitments, column_indices, cells, proofs)
    )
```

## Reconstruction

### `construct_vanishing_polynomial`

```python
def construct_vanishing_polynomial(missing_cell_ids: Sequence[CellID]) -> Tuple[
        Sequence[BLSFieldElement],
        Sequence[BLSFieldElement]]:
    """
    Given the cells that are missing from the data, compute the polynomial that vanishes at every point that
    corresponds to a missing field element.
    """
    # Get the small domain
    roots_of_unity_reduced = compute_roots_of_unity(CELLS_PER_BLOB)

    # Compute polynomial that vanishes at all the missing cells (over the small domain)
    short_zero_poly = vanishing_polynomialcoeff([
        roots_of_unity_reduced[reverse_bits(missing_cell_id, CELLS_PER_BLOB)]
        for missing_cell_id in missing_cell_ids
    ])

    # Extend vanishing polynomial to full domain using the closed form of the vanishing polynomial over a coset
    zero_poly_coeff = [0] * FIELD_ELEMENTS_PER_EXT_BLOB
    for i, coeff in enumerate(short_zero_poly):
        zero_poly_coeff[i * FIELD_ELEMENTS_PER_CELL] = coeff

    # Compute evaluations of the extended vanishing polynomial
    zero_poly_eval = fft_field(zero_poly_coeff,
                               compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB))
    zero_poly_eval_brp = bit_reversal_permutation(zero_poly_eval)

    # Sanity check
    for cell_id in range(CELLS_PER_BLOB):
        start = cell_id * FIELD_ELEMENTS_PER_CELL
        end = (cell_id + 1) * FIELD_ELEMENTS_PER_CELL
        if cell_id in missing_cell_ids:
            assert all(a == 0 for a in zero_poly_eval_brp[start:end])
        else:  # cell_id in cell_ids
            assert all(a != 0 for a in zero_poly_eval_brp[start:end])

    return zero_poly_coeff, zero_poly_eval, zero_poly_eval_brp
```

### `recover_shifted_data`

```python
def recover_shifted_data(cell_ids: Sequence[CellID],
                         cells: Sequence[Cell],
                         zero_poly_eval: Sequence[BLSFieldElement],
                         zero_poly_coeff: Sequence[BLSFieldElement],
                         roots_of_unity_extended: Sequence[BLSFieldElement]) -> Tuple[
                             Sequence[BLSFieldElement],
                             Sequence[BLSFieldElement],
                             BLSFieldElement]:
    """
    Given Z(x), return polynomial Q_1(x)=(E*Z)(k*x) and Q_2(x)=Z(k*x) and k^{-1}.
    """
    shift_factor = BLSFieldElement(PRIMITIVE_ROOT_OF_UNITY)
    shift_inv = div(BLSFieldElement(1), shift_factor)

    extended_evaluation_rbo = [0] * FIELD_ELEMENTS_PER_EXT_BLOB
    for cell_id, cell in zip(cell_ids, cells):
        start = cell_id * FIELD_ELEMENTS_PER_CELL
        end = (cell_id + 1) * FIELD_ELEMENTS_PER_CELL
        extended_evaluation_rbo[start:end] = cell
    extended_evaluation = bit_reversal_permutation(extended_evaluation_rbo)

    # Compute (E*Z)(x)
    extended_evaluation_times_zero = [BLSFieldElement(int(a) * int(b) % BLS_MODULUS)
                                      for a, b in zip(zero_poly_eval, extended_evaluation)]

    extended_evaluations_fft = fft_field(extended_evaluation_times_zero, roots_of_unity_extended, inv=True)

    # Compute (E*Z)(k*x)
    shifted_extended_evaluation = shift_polynomialcoeff(extended_evaluations_fft, shift_factor)
    # Compute Z(k*x)
    shifted_zero_poly = shift_polynomialcoeff(zero_poly_coeff, shift_factor)

    eval_shifted_extended_evaluation = fft_field(shifted_extended_evaluation, roots_of_unity_extended)
    eval_shifted_zero_poly = fft_field(shifted_zero_poly, roots_of_unity_extended)

    return eval_shifted_extended_evaluation, eval_shifted_zero_poly, shift_inv
```

### `recover_original_data`

```python
def recover_original_data(eval_shifted_extended_evaluation: Sequence[BLSFieldElement],
                          eval_shifted_zero_poly: Sequence[BLSFieldElement],
                          shift_inv: BLSFieldElement,
                          roots_of_unity_extended: Sequence[BLSFieldElement]) -> Sequence[BLSFieldElement]:
    """
    Given Q_1, Q_2 and k^{-1}, compute P(x).
    """
    # Compute Q_3 = Q_1(x)/Q_2(x) = P(k*x)
    eval_shifted_reconstructed_poly = [
        div(a, b)
        for a, b in zip(eval_shifted_extended_evaluation, eval_shifted_zero_poly)
    ]

    shifted_reconstructed_poly = fft_field(eval_shifted_reconstructed_poly, roots_of_unity_extended, inv=True)

    # Unshift P(k*x) by k^{-1} to get P(x)
    reconstructed_poly = shift_polynomialcoeff(shifted_reconstructed_poly, shift_inv)

    reconstructed_data = bit_reversal_permutation(fft_field(reconstructed_poly, roots_of_unity_extended))

    return reconstructed_data
```

### `recover_polynomial`

```python
def recover_polynomial(cell_ids: Sequence[CellID],
                       cells_bytes: Sequence[Vector[Bytes32, FIELD_ELEMENTS_PER_CELL]]) -> Polynomial:
    """
    Recover original polynomial from FIELD_ELEMENTS_PER_EXT_BLOB evaluations, half of which can be missing. This
    algorithm uses FFTs to recover cells faster than using Lagrange implementation, as can be seen here:
    https://ethresear.ch/t/reed-solomon-erasure-code-recovery-in-n-log-2-n-time-with-ffts/3039

    A faster version thanks to Qi Zhou can be found here:
    https://github.com/ethereum/research/blob/51b530a53bd4147d123ab3e390a9d08605c2cdb8/polynomial_reconstruction/polynomial_reconstruction_danksharding.py

    Public method.
    """
    assert len(cell_ids) == len(cells_bytes)
    # Check we have enough cells to be able to perform the reconstruction
    assert CELLS_PER_BLOB / 2 <= len(cell_ids) <= CELLS_PER_BLOB
    # Check for duplicates
    assert len(cell_ids) == len(set(cell_ids))

    # Get the extended domain
    roots_of_unity_extended = compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB)

    # Convert from bytes to cells
    cells = [bytes_to_cell(cell_bytes) for cell_bytes in cells_bytes]

    missing_cell_ids = [cell_id for cell_id in range(CELLS_PER_BLOB) if cell_id not in cell_ids]
    zero_poly_coeff, zero_poly_eval, zero_poly_eval_brp = construct_vanishing_polynomial(missing_cell_ids)

    eval_shifted_extended_evaluation, eval_shifted_zero_poly, shift_inv = recover_shifted_data(
        cell_ids,
        cells,
        zero_poly_eval,
        zero_poly_coeff,
        roots_of_unity_extended,
    )

    reconstructed_data = recover_original_data(
        eval_shifted_extended_evaluation,
        eval_shifted_zero_poly,
        shift_inv,
        roots_of_unity_extended,
    )

    for cell_id, cell in zip(cell_ids, cells):
        start = cell_id * FIELD_ELEMENTS_PER_CELL
        end = (cell_id + 1) * FIELD_ELEMENTS_PER_CELL
        assert reconstructed_data[start:end] == cell

    return reconstructed_data
```
