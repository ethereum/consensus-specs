# EIP-7594 -- Polynomial Commitments Sampling

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Public Methods](#public-methods)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Preset](#preset)
  - [Cells](#cells)
- [Helper functions](#helper-functions)
  - [BLS12-381 helpers](#bls12-381-helpers)
    - [`cell_to_coset_evals`](#cell_to_coset_evals)
    - [`coset_evals_to_cell`](#coset_evals_to_cell)
  - [Linear combinations](#linear-combinations)
    - [`g2_lincomb`](#g2_lincomb)
  - [FFTs](#ffts)
    - [`_fft_field`](#_fft_field)
    - [`fft_field`](#fft_field)
    - [`coset_fft_field`](#coset_fft_field)
  - [Polynomials in coefficient form](#polynomials-in-coefficient-form)
    - [`polynomial_eval_to_coeff`](#polynomial_eval_to_coeff)
    - [`add_polynomialcoeff`](#add_polynomialcoeff)
    - [`neg_polynomialcoeff`](#neg_polynomialcoeff)
    - [`multiply_polynomialcoeff`](#multiply_polynomialcoeff)
    - [`divide_polynomialcoeff`](#divide_polynomialcoeff)
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
    - [`compute_cells_and_kzg_proofs`](#compute_cells_and_kzg_proofs)
    - [`compute_cells`](#compute_cells)
  - [Cell verification](#cell-verification)
    - [`verify_cell_kzg_proof`](#verify_cell_kzg_proof)
    - [`verify_cell_kzg_proof_batch`](#verify_cell_kzg_proof_batch)
- [Reconstruction](#reconstruction)
  - [`construct_vanishing_polynomial`](#construct_vanishing_polynomial)
  - [`recover_data`](#recover_data)
  - [`recover_cells_and_kzg_proofs`](#recover_cells_and_kzg_proofs)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document extends [polynomial-commitments.md](polynomial-commitments.md) with the functions required for data availability sampling (DAS). It is not part of the core Deneb spec but an extension that can be optionally implemented to allow nodes to reduce their load using DAS.

## Public Methods

For any KZG library extended to support DAS, functions flagged as "Public method" MUST be provided by the underlying KZG library as public functions. All other functions are private functions used internally by the KZG library.

Public functions MUST accept raw bytes as input and perform the required cryptographic normalization before invoking any internal functions.

The following is a list of the public methods:

- [`compute_cells_and_kzg_proofs`](#compute_cells_and_kzg_proofs)
- [`compute_cells`](#compute_cells)
- [`verify_cell_kzg_proof`](#verify_cell_kzg_proof)
- [`verify_cell_kzg_proof_batch`](#verify_cell_kzg_proof_batch)
- [`recover_cells_and_kzg_proofs`](#recover_cells_and_kzg_proofs)

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `PolynomialCoeff` | `List[BLSFieldElement, FIELD_ELEMENTS_PER_EXT_BLOB]` | A polynomial in coefficient form |
| `Coset` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]` | The evaluation domain of a cell |
| `CosetEvals` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]` | The internal representation of a cell (the evaluations over its Coset) |
| `Cell` | `ByteVector[BYTES_PER_FIELD_ELEMENT * FIELD_ELEMENTS_PER_CELL]` | The unit of blob data that can come with its own KZG proof |
| `CellIndex` | `uint64` | Validation: `x < CELLS_PER_EXT_BLOB` |

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
| `CELLS_PER_EXT_BLOB` | `FIELD_ELEMENTS_PER_EXT_BLOB // FIELD_ELEMENTS_PER_CELL` | The number of cells in an extended blob |
| `RANDOM_CHALLENGE_KZG_CELL_BATCH_DOMAIN` | `b'RCKZGCBATCH__V1_'` |

## Helper functions

### BLS12-381 helpers

#### `cell_to_coset_evals`

```python
def cell_to_coset_evals(cell: Cell) -> CosetEvals:
    """
    Convert an untrusted ``Cell`` into a trusted ``CosetEvals``.
    """
    evals = []
    for i in range(FIELD_ELEMENTS_PER_CELL):
        start = i * BYTES_PER_FIELD_ELEMENT
        end = (i + 1) * BYTES_PER_FIELD_ELEMENT
        value = bytes_to_bls_field(cell[start:end])
        evals.append(value)
    return CosetEvals(evals)
```

#### `coset_evals_to_cell`

```python
def coset_evals_to_cell(coset_evals: CosetEvals) -> Cell:
    """
    Convert a trusted ``CosetEval`` into an untrusted ``Cell``.
    """
    cell = []
    for i in range(FIELD_ELEMENTS_PER_CELL):
        cell += bls_field_to_bytes(coset_evals[i])
    return Cell(cell)
```

### Linear combinations

#### `g2_lincomb`

```python
def g2_lincomb(points: Sequence[G2Point], scalars: Sequence[BLSFieldElement]) -> Bytes96:
    """
    BLS multiscalar multiplication in G2. This can be naively implemented using double-and-add.
    """
    assert len(points) == len(scalars)

    if len(points) == 0:
        return bls.G2_to_bytes96(bls.Z2())

    points_g2 = []
    for point in points:
        points_g2.append(bls.bytes96_to_G2(point))

    result = bls.multi_exp(points_g2, scalars)
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

#### `coset_fft_field`

```python
def coset_fft_field(vals: Sequence[BLSFieldElement],
                    roots_of_unity: Sequence[BLSFieldElement],
                    inv: bool=False) -> Sequence[BLSFieldElement]:
    """
    Computes an FFT/IFFT over a coset of the roots of unity. 
    This is useful for when one wants to divide by a polynomial which 
    vanishes on one or more elements in the domain.
    """
    vals = vals.copy()
    
    def shift_vals(vals: Sequence[BLSFieldElement], factor: BLSFieldElement) -> Sequence[BLSFieldElement]:
        """  
        Multiply each entry in `vals` by succeeding powers of `factor`  
        i.e., [vals[0] * factor^0, vals[1] * factor^1, ..., vals[n] * factor^n]  
        """  
        shift = 1
        for i in range(len(vals)):
            vals[i] = BLSFieldElement((int(vals[i]) * shift) % BLS_MODULUS)
            shift = (shift * int(factor)) % BLS_MODULUS
        return vals

    # This is the coset generator; it is used to compute a FFT/IFFT over a coset of
    # the roots of unity.
    shift_factor = BLSFieldElement(PRIMITIVE_ROOT_OF_UNITY)
    if inv:
        vals = fft_field(vals, roots_of_unity, inv)
        shift_inv = bls_modular_inverse(shift_factor)
        return shift_vals(vals, shift_inv)
    else:
        vals = shift_vals(vals, shift_factor)
        return fft_field(vals, roots_of_unity, inv)
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
    a = a.copy()  # Make a copy since `a` is passed by reference
    o: List[BLSFieldElement] = []
    apos = len(a) - 1
    bpos = len(b) - 1
    diff = apos - bpos
    while diff >= 0:
        quot = div(a[apos], b[bpos])
        o.insert(0, quot)
        for i in range(bpos, -1, -1):
            a[diff + i] = (int(a[diff + i]) - int(b[i] + BLS_MODULUS) * int(quot)) % BLS_MODULUS
        apos -= 1
        diff -= 1
    return [x % BLS_MODULUS for x in o]
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
                    summand, [((BLS_MODULUS - int(weight_adjustment)) * int(xs[j])) % BLS_MODULUS, weight_adjustment]
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
        p = multiply_polynomialcoeff(p, [-int(x) + BLS_MODULUS, 1])
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
        zs: Coset) -> Tuple[KZGProof, CosetEvals]:
    """
    Compute a KZG multi-evaluation proof for a set of `k` points.

    This is done by committing to the following quotient polynomial:  
        Q(X) = f(X) - I(X) / Z(X)
    Where:
        - I(X) is the degree `k-1` polynomial that agrees with f(x) at all `k` points
        - Z(X) is the degree `k` polynomial that evaluates to zero on all `k` points
    
    We further note that since the degree of I(X) is less than the degree of Z(X),
    the computation can be simplified in monomial form to Q(X) = f(X) / Z(X)
    """

    # For all points, compute the evaluation of those points
    ys = [evaluate_polynomialcoeff(polynomial_coeff, z) for z in zs]

    # Compute Z(X)
    denominator_poly = vanishing_polynomialcoeff(zs)

    # Compute the quotient polynomial directly in monomial form
    quotient_polynomial = divide_polynomialcoeff(polynomial_coeff, denominator_poly)

    return KZGProof(g1_lincomb(KZG_SETUP_G1_MONOMIAL[:len(quotient_polynomial)], quotient_polynomial)), ys
```

#### `verify_kzg_proof_multi_impl`

```python
def verify_kzg_proof_multi_impl(commitment: KZGCommitment,
                                zs: Coset,
                                ys: CosetEvals,
                                proof: KZGProof) -> bool:
    """
    Verify a KZG multi-evaluation proof for a set of `k` points.

    This is done by checking if the following equation holds:
        Q(x) Z(x) = f(X) - I(X)
    Where:
        f(X) is the polynomial that we want to verify opens at `k` points to `k` values
        Q(X) is the quotient polynomial computed by the prover
        I(X) is the degree k-1 polynomial that evaluates to `ys` at all `zs`` points
        Z(X) is the polynomial that evaluates to zero on all `k` points
    
    The verifier receives the commitments to Q(X) and f(X), so they check the equation
    holds by using the following pairing equation:
        e([Q(X)]_1, [Z(X)]_2) == e([f(X)]_1 - [I(X)]_1, [1]_2)
    """

    assert len(zs) == len(ys)

    # Compute [Z(X)]_2
    zero_poly = g2_lincomb(KZG_SETUP_G2_MONOMIAL[:len(zs) + 1], vanishing_polynomialcoeff(zs))
    # Compute [I(X)]_1
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
def coset_for_cell(cell_index: CellIndex) -> Coset:
    """
    Get the coset for a given ``cell_index``.
    """
    assert cell_index < CELLS_PER_EXT_BLOB
    roots_of_unity_brp = bit_reversal_permutation(
        compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB)
    )
    return Coset(roots_of_unity_brp[FIELD_ELEMENTS_PER_CELL * cell_index:FIELD_ELEMENTS_PER_CELL * (cell_index + 1)])
```

## Cells

### Cell computation

#### `compute_cells_and_kzg_proofs`

```python
def compute_cells_and_kzg_proofs(blob: Blob) -> Tuple[
        Vector[Cell, CELLS_PER_EXT_BLOB],
        Vector[KZGProof, CELLS_PER_EXT_BLOB]]:
    """
    Compute all the cell proofs for an extended blob. This is an inefficient O(n^2) algorithm,
    for performant implementation the FK20 algorithm that runs in O(n log n) should be
    used instead.

    Public method.
    """
    assert len(blob) == BYTES_PER_BLOB
    
    polynomial = blob_to_polynomial(blob)
    polynomial_coeff = polynomial_eval_to_coeff(polynomial)

    cells = []
    proofs = []

    for i in range(CELLS_PER_EXT_BLOB):
        coset = coset_for_cell(CellIndex(i))
        proof, ys = compute_kzg_proof_multi_impl(polynomial_coeff, coset)
        cells.append(coset_evals_to_cell(ys))
        proofs.append(proof)

    return cells, proofs
```

#### `compute_cells`

```python
def compute_cells(blob: Blob) -> Vector[Cell, CELLS_PER_EXT_BLOB]:
    """
    Compute the cell data for an extended blob (without computing the proofs).

    Public method.
    """
    assert len(blob) == BYTES_PER_BLOB
    
    polynomial = blob_to_polynomial(blob)
    polynomial_coeff = polynomial_eval_to_coeff(polynomial)

    extended_data = fft_field(polynomial_coeff + [0] * FIELD_ELEMENTS_PER_BLOB,
                              compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB))
    extended_data_rbo = bit_reversal_permutation(extended_data)
    cells = []
    for cell_index in range(CELLS_PER_EXT_BLOB):
        start = cell_index * FIELD_ELEMENTS_PER_CELL
        end = (cell_index + 1) * FIELD_ELEMENTS_PER_CELL
        cells.append(coset_evals_to_cell(CosetEvals(extended_data_rbo[start:end])))
    return cells
```

### Cell verification

#### `verify_cell_kzg_proof`

```python
def verify_cell_kzg_proof(commitment_bytes: Bytes48,
                          cell_index: CellIndex,
                          cell: Cell,
                          proof_bytes: Bytes48) -> bool:
    """
    Check a cell proof

    Public method.
    """
    assert len(commitment_bytes) == BYTES_PER_COMMITMENT
    assert cell_index < CELLS_PER_EXT_BLOB
    assert len(cell) == BYTES_PER_CELL
    assert len(proof_bytes) == BYTES_PER_PROOF
    
    coset = coset_for_cell(cell_index)

    return verify_kzg_proof_multi_impl(
        bytes_to_kzg_commitment(commitment_bytes),
        coset,
        cell_to_coset_evals(cell),
        bytes_to_kzg_proof(proof_bytes))
```

#### `verify_cell_kzg_proof_batch`

```python
def verify_cell_kzg_proof_batch(row_commitments_bytes: Sequence[Bytes48],
                                row_indices: Sequence[RowIndex],
                                column_indices: Sequence[ColumnIndex],
                                cells: Sequence[Cell],
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
    assert len(cells) == len(proofs_bytes) == len(row_indices) == len(column_indices)
    for commitment_bytes in row_commitments_bytes:
        assert len(commitment_bytes) == BYTES_PER_COMMITMENT
    for row_index in row_indices:
        assert row_index < len(row_commitments_bytes)
    for column_index in column_indices:
        assert column_index < CELLS_PER_EXT_BLOB
    for cell in cells:
        assert len(cell) == BYTES_PER_CELL
    for proof_bytes in proofs_bytes:
        assert len(proof_bytes) == BYTES_PER_PROOF

    # Get commitments via row IDs
    commitments_bytes = [row_commitments_bytes[row_index] for row_index in row_indices]

    # Get objects from bytes
    commitments = [bytes_to_kzg_commitment(commitment_bytes) for commitment_bytes in commitments_bytes]
    cosets_evals = [cell_to_coset_evals(cell) for cell in cells]
    proofs = [bytes_to_kzg_proof(proof_bytes) for proof_bytes in proofs_bytes]

    return all(
        verify_kzg_proof_multi_impl(commitment, coset_for_cell(column_index), coset_evals, proof)
        for commitment, column_index, coset_evals, proof in zip(commitments, column_indices, cosets_evals, proofs)
    )
```

## Reconstruction

### `construct_vanishing_polynomial`

```python
def construct_vanishing_polynomial(missing_cell_ids: Sequence[CellIndex]) -> Sequence[BLSFieldElement]:
    """
    Given the cells IDs that are missing from the data, compute the polynomial that vanishes at every point that
    corresponds to a missing field element.
    
    This method assumes that all of the cells cannot be missing. In this case the vanishing polynomial
    could be computed as Z(x) = x^n - 1, where `n` is FIELD_ELEMENTS_PER_EXT_BLOB.

    We never encounter this case however because this method is used solely for recovery and recovery only
    works if at least half of the cells are available.
    """

    assert len(missing_cell_ids) != 0

    # Get the small domain
    roots_of_unity_reduced = compute_roots_of_unity(CELLS_PER_EXT_BLOB)

    # Compute polynomial that vanishes at all the missing cells (over the small domain)
    short_zero_poly = vanishing_polynomialcoeff([
        roots_of_unity_reduced[reverse_bits(missing_cell_index, CELLS_PER_EXT_BLOB)]
        for missing_cell_index in missing_cell_indices
    ])

    # Extend vanishing polynomial to full domain using the closed form of the vanishing polynomial over a coset
    zero_poly_coeff = [BLSFieldElement(0)] * FIELD_ELEMENTS_PER_EXT_BLOB
    for i, coeff in enumerate(short_zero_poly):
        zero_poly_coeff[i * FIELD_ELEMENTS_PER_CELL] = coeff

    return zero_poly_coeff
```

### `recover_data`

```python
def recover_data(cell_ids: Sequence[CellIndex],
                 cells: Sequence[Cell],
                 ) -> Sequence[BLSFieldElement]:
    """
    Recover the missing evaluations for the extended blob, given at least half of the evaluations.
    """

    # Get the extended domain. This will be referred to as the FFT domain.
    roots_of_unity_extended = compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB)

    # Flatten the cells into evaluations.
    # If a cell is missing, then its evaluation is zero.
    extended_evaluation_rbo = [0] * FIELD_ELEMENTS_PER_EXT_BLOB
    for cell_index, cell in zip(cell_indices, cells):
        start = cell_index * FIELD_ELEMENTS_PER_CELL
        end = (cell_index + 1) * FIELD_ELEMENTS_PER_CELL
        extended_evaluation_rbo[start:end] = cell
    extended_evaluation = bit_reversal_permutation(extended_evaluation_rbo)

    # Compute Z(x) in monomial form
    # Z(x) is the polynomial which vanishes on all of the evaluations which are missing
    missing_cell_ids = [CellIndex(cell_id) for cell_id in range(CELLS_PER_EXT_BLOB) if cell_id not in cell_ids]
    zero_poly_coeff = construct_vanishing_polynomial(missing_cell_ids)

    # Convert Z(x) to evaluation form over the FFT domain
    zero_poly_eval = fft_field(zero_poly_coeff, roots_of_unity_extended)

    # Compute (E*Z)(x) = E(x) * Z(x) in evaluation form over the FFT domain
    extended_evaluation_times_zero = [BLSFieldElement(int(a) * int(b) % BLS_MODULUS)
                                      for a, b in zip(zero_poly_eval, extended_evaluation)]

    # Convert (E*Z)(x) to monomial form 
    extended_evaluation_times_zero_coeffs = fft_field(extended_evaluation_times_zero, roots_of_unity_extended, inv=True)

    # Convert (E*Z)(x) to evaluation form over a coset of the FFT domain
    extended_evaluations_over_coset = coset_fft_field(extended_evaluation_times_zero_coeffs, roots_of_unity_extended)

    # Convert Z(x) to evaluation form over a coset of the FFT domain
    zero_poly_over_coset = coset_fft_field(zero_poly_coeff, roots_of_unity_extended)

    # Compute Q_3(x) = (E*Z)(x) / Z(x) in evaluation form over a coset of the FFT domain
    reconstructed_poly_over_coset = [
        div(a, b)
        for a, b in zip(extended_evaluations_over_coset, zero_poly_over_coset)
    ]

    # Convert Q_3(x) to monomial form
    reconstructed_poly_coeff = coset_fft_field(reconstructed_poly_over_coset, roots_of_unity_extended, inv=True)

    # Convert Q_3(x) to evaluation form over the FFT domain and bit reverse the result
    reconstructed_data = bit_reversal_permutation(fft_field(reconstructed_poly_coeff, roots_of_unity_extended))

    return reconstructed_data
```

### `recover_cells_and_kzg_proofs`

```python
def recover_cells_and_kzg_proofs(cell_indices: Sequence[CellIndex],
                                 cells: Sequence[Cell],
                                 proofs_bytes: Sequence[Bytes48]) -> Tuple[
        Vector[Cell, CELLS_PER_EXT_BLOB],
        Vector[KZGProof, CELLS_PER_EXT_BLOB]]:
    """
    Given at least 50% of cells/proofs for a blob, recover all the cells/proofs.
    This algorithm uses FFTs to recover cells faster than using Lagrange
    implementation, as can be seen here:
    https://ethresear.ch/t/reed-solomon-erasure-code-recovery-in-n-log-2-n-time-with-ffts/3039

    A faster version thanks to Qi Zhou can be found here:
    https://github.com/ethereum/research/blob/51b530a53bd4147d123ab3e390a9d08605c2cdb8/polynomial_reconstruction/polynomial_reconstruction_danksharding.py

    Public method.
    """
    assert len(cell_indices) == len(cells) == len(proofs_bytes)
    # Check we have enough cells to be able to perform the reconstruction
    assert CELLS_PER_EXT_BLOB / 2 <= len(cell_indices) <= CELLS_PER_EXT_BLOB
    # Check for duplicates
    assert len(cell_indices) == len(set(cell_indices))
    # Check that the cell indices are within bounds
    for cell_index in cell_indices:
        assert cell_index < CELLS_PER_EXT_BLOB
    # Check that each cell is the correct length
    for cell in cells:
        assert len(cell) == BYTES_PER_CELL
    # Check that each proof is the correct length
    for proof_bytes in proofs_bytes:
        assert len(proof_bytes) == BYTES_PER_PROOF

    # Convert cells to coset evals
    cosets_evals = [cell_to_coset_evals(cell) for cell in cells]

    reconstructed_data = recover_data(cell_ids, cosets_evals)

    for cell_index, coset_evals in zip(cell_indices, cosets_evals):
        start = cell_index * FIELD_ELEMENTS_PER_CELL
        end = (cell_index + 1) * FIELD_ELEMENTS_PER_CELL
        assert reconstructed_data[start:end] == coset_evals

    recovered_cells = [
        coset_evals_to_cell(reconstructed_data[i * FIELD_ELEMENTS_PER_CELL:(i + 1) * FIELD_ELEMENTS_PER_CELL])
        for i in range(CELLS_PER_EXT_BLOB)]
    
    polynomial_eval = reconstructed_data[:FIELD_ELEMENTS_PER_BLOB]
    polynomial_coeff = polynomial_eval_to_coeff(polynomial_eval)
    recovered_proofs = [None] * CELLS_PER_EXT_BLOB
    for i, cell_index in enumerate(cell_indices):
        recovered_proofs[cell_index] = bytes_to_kzg_proof(proofs_bytes[i])
    for i in range(CELLS_PER_EXT_BLOB):
        if recovered_proofs[i] is None:
            coset = coset_for_cell(CellIndex(i))
            proof, ys = compute_kzg_proof_multi_impl(polynomial_coeff, coset)
            assert coset_evals_to_cell(ys) == recovered_cells[i]
            recovered_proofs[i] = proof
 
    return recovered_cells, recovered_proofs
```
