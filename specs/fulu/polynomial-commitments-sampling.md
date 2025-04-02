# Fulu -- Polynomial Commitments Sampling

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Public Methods](#public-methods)
- [Custom types](#custom-types)
- [Cryptographic types](#cryptographic-types)
- [Preset](#preset)
  - [Cells](#cells)
- [Helper functions](#helper-functions)
  - [BLS12-381 helpers](#bls12-381-helpers)
    - [`cell_to_coset_evals`](#cell_to_coset_evals)
    - [`coset_evals_to_cell`](#coset_evals_to_cell)
  - [FFTs](#ffts)
    - [`_fft_field`](#_fft_field)
    - [`fft_field`](#fft_field)
    - [`coset_fft_field`](#coset_fft_field)
    - [`compute_verify_cell_kzg_proof_batch_challenge`](#compute_verify_cell_kzg_proof_batch_challenge)
  - [Polynomials in coefficient form](#polynomials-in-coefficient-form)
    - [`polynomial_eval_to_coeff`](#polynomial_eval_to_coeff)
    - [`add_polynomialcoeff`](#add_polynomialcoeff)
    - [`multiply_polynomialcoeff`](#multiply_polynomialcoeff)
    - [`divide_polynomialcoeff`](#divide_polynomialcoeff)
    - [`interpolate_polynomialcoeff`](#interpolate_polynomialcoeff)
    - [`vanishing_polynomialcoeff`](#vanishing_polynomialcoeff)
    - [`evaluate_polynomialcoeff`](#evaluate_polynomialcoeff)
  - [KZG multiproofs](#kzg-multiproofs)
    - [`compute_kzg_proof_multi_impl`](#compute_kzg_proof_multi_impl)
    - [`verify_cell_kzg_proof_batch_impl`](#verify_cell_kzg_proof_batch_impl)
  - [Cell cosets](#cell-cosets)
    - [`coset_shift_for_cell`](#coset_shift_for_cell)
    - [`coset_for_cell`](#coset_for_cell)
- [Cells](#cells-1)
  - [Cell computation](#cell-computation)
    - [`compute_cells`](#compute_cells)
    - [`compute_cells_and_kzg_proofs_polynomialcoeff`](#compute_cells_and_kzg_proofs_polynomialcoeff)
    - [`compute_cells_and_kzg_proofs`](#compute_cells_and_kzg_proofs)
  - [Cell verification](#cell-verification)
    - [`verify_cell_kzg_proof_batch`](#verify_cell_kzg_proof_batch)
- [Reconstruction](#reconstruction)
  - [`construct_vanishing_polynomial`](#construct_vanishing_polynomial)
  - [`recover_polynomialcoeff`](#recover_polynomialcoeff)
  - [`recover_cells_and_kzg_proofs`](#recover_cells_and_kzg_proofs)

<!-- mdformat-toc end -->

## Introduction

This document extends [polynomial-commitments.md](../deneb/polynomial-commitments.md) with the functions required for data availability sampling (DAS). It is not part of the core Deneb spec but an extension that can be optionally implemented to allow nodes to reduce their load using DAS.

## Public Methods

For any KZG library extended to support DAS, functions flagged as "Public method" MUST be provided by the underlying KZG library as public functions. All other functions are private functions used internally by the KZG library.

Public functions MUST accept raw bytes as input and perform the required cryptographic normalization before invoking any internal functions.

The following is a list of the public methods:

- [`compute_cells_and_kzg_proofs`](#compute_cells_and_kzg_proofs)
- [`verify_cell_kzg_proof_batch`](#verify_cell_kzg_proof_batch)
- [`recover_cells_and_kzg_proofs`](#recover_cells_and_kzg_proofs)

## Custom types

| Name              | SSZ equivalent                                                  | Description                                                                  |
| ----------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `Cell`            | `ByteVector[BYTES_PER_FIELD_ELEMENT * FIELD_ELEMENTS_PER_CELL]` | The unit of blob data that can come with its own KZG proof                   |
| `CellIndex`       | `uint64`                                                        | Validation: `x < CELLS_PER_EXT_BLOB`                                         |
| `CommitmentIndex` | `uint64`                                                        | The type which represents the index of an element in the list of commitments |

## Cryptographic types

| Name                                                                                                                                                    | SSZ equivalent                                       | Description                                                  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------ |
| [`PolynomialCoeff`](https://github.com/ethereum/consensus-specs/blob/36a5719b78523c057065515c8f8fcaeba75d065b/pysetup/spec_builders/eip7594.py#L20-L24) | `List[BLSFieldElement, FIELD_ELEMENTS_PER_EXT_BLOB]` | <!-- predefined-type --> A polynomial in coefficient form    |
| [`Coset`](https://github.com/ethereum/consensus-specs/blob/36a5719b78523c057065515c8f8fcaeba75d065b/pysetup/spec_builders/eip7594.py#L27-L33)           | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]`   | <!-- predefined-type --> The evaluation domain of a cell     |
| [`CosetEvals`](https://github.com/ethereum/consensus-specs/blob/36a5719b78523c057065515c8f8fcaeba75d065b/pysetup/spec_builders/eip7594.py#L36-L42)      | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_CELL]`   | <!-- predefined-type --> A cell's evaluations over its coset |

## Preset

### Cells

Cells are the smallest unit of blob data that can come with their own KZG proofs. Samples can be constructed from one or several cells (e.g. an individual cell or line).

| Name                                     | Value                                                    | Description                                              |
| ---------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------- |
| `FIELD_ELEMENTS_PER_EXT_BLOB`            | `2 * FIELD_ELEMENTS_PER_BLOB`                            | Number of field elements in a Reed-Solomon extended blob |
| `FIELD_ELEMENTS_PER_CELL`                | `uint64(64)`                                             | Number of field elements in a cell                       |
| `BYTES_PER_CELL`                         | `FIELD_ELEMENTS_PER_CELL * BYTES_PER_FIELD_ELEMENT`      | The number of bytes in a cell                            |
| `CELLS_PER_EXT_BLOB`                     | `FIELD_ELEMENTS_PER_EXT_BLOB // FIELD_ELEMENTS_PER_CELL` | The number of cells in an extended blob                  |
| `RANDOM_CHALLENGE_KZG_CELL_BATCH_DOMAIN` | `b'RCKZGCBATCH__V1_'`                                    |                                                          |

## Helper functions

### BLS12-381 helpers

#### `cell_to_coset_evals`

```python
def cell_to_coset_evals(cell: Cell) -> CosetEvals:
    """
    Convert an untrusted ``Cell`` into a trusted ``CosetEvals``.
    """
    evals = CosetEvals()
    for i in range(FIELD_ELEMENTS_PER_CELL):
        start = i * BYTES_PER_FIELD_ELEMENT
        end = (i + 1) * BYTES_PER_FIELD_ELEMENT
        evals[i] = bytes_to_bls_field(cell[start:end])
    return evals
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

### FFTs

#### `_fft_field`

```python
def _fft_field(vals: Sequence[BLSFieldElement], roots_of_unity: Sequence[BLSFieldElement]) -> Sequence[BLSFieldElement]:
    if len(vals) == 1:
        return vals
    L = _fft_field(vals[::2], roots_of_unity[::2])
    R = _fft_field(vals[1::2], roots_of_unity[::2])
    o = [BLSFieldElement(0) for _ in vals]
    for i, (x, y) in enumerate(zip(L, R)):
        y_times_root = y * roots_of_unity[i]
        o[i] = x + y_times_root
        o[i + len(L)] = x - y_times_root
    return o
```

#### `fft_field`

```python
def fft_field(vals: Sequence[BLSFieldElement],
              roots_of_unity: Sequence[BLSFieldElement],
              inv: bool=False) -> Sequence[BLSFieldElement]:
    if inv:
        # Inverse FFT
        invlen = BLSFieldElement(len(vals)).pow(BLSFieldElement(BLS_MODULUS - 2))
        return [x * invlen for x in _fft_field(vals, list(roots_of_unity[0:1]) + list(roots_of_unity[:0:-1]))]
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
    vals = [v for v in vals]  # copy

    def shift_vals(vals: Sequence[BLSFieldElement], factor: BLSFieldElement) -> Sequence[BLSFieldElement]:
        """
        Multiply each entry in `vals` by succeeding powers of `factor`
        i.e., [vals[0] * factor^0, vals[1] * factor^1, ..., vals[n] * factor^n]
        """
        updated_vals: List[BLSFieldElement] = []
        shift = BLSFieldElement(1)
        for i in range(len(vals)):
            updated_vals.append(vals[i] * shift)
            shift = shift * factor
        return updated_vals

    # This is the coset generator; it is used to compute a FFT/IFFT over a coset of
    # the roots of unity.
    shift_factor = BLSFieldElement(PRIMITIVE_ROOT_OF_UNITY)
    if inv:
        vals = fft_field(vals, roots_of_unity, inv)
        return shift_vals(vals, shift_factor.inverse())
    else:
        vals = shift_vals(vals, shift_factor)
        return fft_field(vals, roots_of_unity, inv)
```

#### `compute_verify_cell_kzg_proof_batch_challenge`

```python
def compute_verify_cell_kzg_proof_batch_challenge(commitments: Sequence[KZGCommitment],
                                                  commitment_indices: Sequence[CommitmentIndex],
                                                  cell_indices: Sequence[CellIndex],
                                                  cosets_evals: Sequence[CosetEvals],
                                                  proofs: Sequence[KZGProof]) -> BLSFieldElement:
    """
    Compute a random challenge ``r`` used in the universal verification equation. To compute the
    challenge, ``RANDOM_CHALLENGE_KZG_CELL_BATCH_DOMAIN`` and all data that can influence the
    verification is hashed together to deterministically generate a "random" field element via
    the Fiat-Shamir heuristic.
    """
    hashinput = RANDOM_CHALLENGE_KZG_CELL_BATCH_DOMAIN
    hashinput += int.to_bytes(FIELD_ELEMENTS_PER_BLOB, 8, KZG_ENDIANNESS)
    hashinput += int.to_bytes(FIELD_ELEMENTS_PER_CELL, 8, KZG_ENDIANNESS)
    hashinput += int.to_bytes(len(commitments), 8, KZG_ENDIANNESS)
    hashinput += int.to_bytes(len(cell_indices), 8, KZG_ENDIANNESS)
    for commitment in commitments:
        hashinput += commitment
    for k, coset_evals in enumerate(cosets_evals):
        hashinput += int.to_bytes(commitment_indices[k], 8, KZG_ENDIANNESS)
        hashinput += int.to_bytes(cell_indices[k], 8, KZG_ENDIANNESS)
        for coset_eval in coset_evals:
            hashinput += bls_field_to_bytes(coset_eval)
        hashinput += proofs[k]
    return hash_to_bls_field(hashinput)
```

### Polynomials in coefficient form

#### `polynomial_eval_to_coeff`

```python
def polynomial_eval_to_coeff(polynomial: Polynomial) -> PolynomialCoeff:
    """
    Interpolates a polynomial (given in evaluation form) to a polynomial in coefficient form.
    """
    roots_of_unity = compute_roots_of_unity(FIELD_ELEMENTS_PER_BLOB)
    return PolynomialCoeff(fft_field(bit_reversal_permutation(polynomial), roots_of_unity, inv=True))
```

#### `add_polynomialcoeff`

```python
def add_polynomialcoeff(a: PolynomialCoeff, b: PolynomialCoeff) -> PolynomialCoeff:
    """
    Sum the coefficient form polynomials ``a`` and ``b``.
    """
    a, b = (a, b) if len(a) >= len(b) else (b, a)
    length_a, length_b = len(a), len(b)
    return PolynomialCoeff([a[i] + (b[i] if i < length_b else BLSFieldElement(0)) for i in range(length_a)])
```

#### `multiply_polynomialcoeff`

```python
def multiply_polynomialcoeff(a: PolynomialCoeff, b: PolynomialCoeff) -> PolynomialCoeff:
    """
    Multiplies the coefficient form polynomials ``a`` and ``b``.
    """
    assert len(a) + len(b) <= FIELD_ELEMENTS_PER_EXT_BLOB

    r = PolynomialCoeff([BLSFieldElement(0)])
    for power, coef in enumerate(a):
        summand = PolynomialCoeff([BLSFieldElement(0)] * power + [coef * x for x in b])
        r = add_polynomialcoeff(r, summand)
    return r
```

#### `divide_polynomialcoeff`

```python
def divide_polynomialcoeff(a: PolynomialCoeff, b: PolynomialCoeff) -> PolynomialCoeff:
    """
    Long polynomial division for two coefficient form polynomials ``a`` and ``b``.
    """
    a = PolynomialCoeff(a[:])  # copy
    o = PolynomialCoeff([])
    apos = len(a) - 1
    bpos = len(b) - 1
    diff = apos - bpos
    while diff >= 0:
        quot = a[apos] / b[bpos]
        o.insert(0, quot)
        for i in range(bpos, -1, -1):
            a[diff + i] = a[diff + i] - b[i] * quot
        apos -= 1
        diff -= 1
    return o
```

#### `interpolate_polynomialcoeff`

```python
def interpolate_polynomialcoeff(xs: Sequence[BLSFieldElement], ys: Sequence[BLSFieldElement]) -> PolynomialCoeff:
    """
    Lagrange interpolation: Finds the lowest degree polynomial that takes the value ``ys[i]`` at ``x[i]`` for all i.
    Outputs a coefficient form polynomial. Leading coefficients may be zero.
    """
    assert len(xs) == len(ys)

    r = PolynomialCoeff([BLSFieldElement(0)])
    for i in range(len(xs)):
        summand = PolynomialCoeff([ys[i]])
        for j in range(len(ys)):
            if j != i:
                weight_adjustment = (xs[i] - xs[j]).inverse()
                summand = multiply_polynomialcoeff(
                    summand, PolynomialCoeff([-weight_adjustment * xs[j], weight_adjustment])
                )
        r = add_polynomialcoeff(r, summand)
    return r
```

#### `vanishing_polynomialcoeff`

```python
def vanishing_polynomialcoeff(xs: Sequence[BLSFieldElement]) -> PolynomialCoeff:
    """
    Compute the vanishing polynomial on ``xs`` (in coefficient form).
    """
    p = PolynomialCoeff([BLSFieldElement(1)])
    for x in xs:
        p = multiply_polynomialcoeff(p, PolynomialCoeff([-x, BLSFieldElement(1)]))
    return p
```

#### `evaluate_polynomialcoeff`

```python
def evaluate_polynomialcoeff(polynomial_coeff: PolynomialCoeff, z: BLSFieldElement) -> BLSFieldElement:
    """
    Evaluate a coefficient form polynomial at ``z`` using Horner's schema.
    """
    y = BLSFieldElement(0)
    for coef in polynomial_coeff[::-1]:
        y = y * z + coef
    return y
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
    the computation can be simplified in monomial form to Q(X) = f(X) / Z(X).
    """

    # For all points, compute the evaluation of those points
    ys = CosetEvals([evaluate_polynomialcoeff(polynomial_coeff, z) for z in zs])

    # Compute Z(X)
    denominator_poly = vanishing_polynomialcoeff(zs)

    # Compute the quotient polynomial directly in monomial form
    quotient_polynomial = divide_polynomialcoeff(polynomial_coeff, denominator_poly)

    return KZGProof(g1_lincomb(KZG_SETUP_G1_MONOMIAL[:len(quotient_polynomial)], quotient_polynomial)), ys
```

#### `verify_cell_kzg_proof_batch_impl`

```python
def verify_cell_kzg_proof_batch_impl(commitments: Sequence[KZGCommitment],
                                     commitment_indices: Sequence[CommitmentIndex],
                                     cell_indices: Sequence[CellIndex],
                                     cosets_evals: Sequence[CosetEvals],
                                     proofs: Sequence[KZGProof]) -> bool:
    """
    Helper: Verify that a set of cells belong to their corresponding commitment.

    Given a list of ``commitments`` (which contains no duplicates) and four lists representing
    tuples of (``commitment_index``, ``cell_index``, ``evals``, ``proof``), the function
    verifies ``proof`` which shows that ``evals`` are the evaluations of the polynomial associated
    with ``commitments[commitment_index]``, evaluated over the domain specified by ``cell_index``.

    This function is the internal implementation of ``verify_cell_kzg_proof_batch``.
    """
    assert len(commitment_indices) == len(cell_indices) == len(cosets_evals) == len(proofs)
    assert len(commitments) == len(set(commitments))
    for commitment_index in commitment_indices:
        assert commitment_index < len(commitments)

    # The verification equation that we will check is pairing (LL, LR) = pairing (RL, [1]), where
    # LL = sum_k r^k proofs[k],
    # LR = [s^n]
    # RL = RLC - RLI + RLP, where
    #   RLC = sum_i weights[i] commitments[i]
    #   RLI = [sum_k r^k interpolation_poly_k(s)]
    #   RLP = sum_k (r^k * h_k^n) proofs[k]
    #
    # Here, the variables have the following meaning:
    # - k < len(cell_indices) is an index iterating over all cells in the input
    # - r is a random coefficient, derived from hashing all data provided by the prover
    # - s is the secret embedded in the KZG setup
    # - n = FIELD_ELEMENTS_PER_CELL is the size of the evaluation domain
    # - i ranges over all provided commitments
    # - weights[i] is a weight computed for commitment i
    #   - It depends on r and on which cells are associated with commitment i
    # - interpolation_poly_k is the interpolation polynomial for the kth cell
    # - h_k is the coset shift specifying the evaluation domain of the kth cell

    # Preparation
    num_cells = len(cell_indices)
    n = FIELD_ELEMENTS_PER_CELL
    num_commitments = len(commitments)

    # Step 1: Compute a challenge r and its powers r^0, ..., r^{num_cells-1}
    r = compute_verify_cell_kzg_proof_batch_challenge(
        commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs
    )
    r_powers = compute_powers(r, num_cells)

    # Step 2: Compute LL = sum_k r^k proofs[k]
    ll = bls.bytes48_to_G1(g1_lincomb(proofs, r_powers))

    # Step 3: Compute LR = [s^n]
    lr = bls.bytes96_to_G2(KZG_SETUP_G2_MONOMIAL[n])

    # Step 4: Compute RL = RLC - RLI + RLP
    # Step 4.1: Compute RLC = sum_i weights[i] commitments[i]
    # Step 4.1a: Compute weights[i]: the sum of all r^k for which cell k is associated with commitment i.
    # Note: we do that by iterating over all k and updating the correct weights[i] accordingly
    weights = [BLSFieldElement(0)] * num_commitments
    for k in range(num_cells):
        i = commitment_indices[k]
        weights[i] += r_powers[k]
    # Step 4.1b: Linearly combine the weights with the commitments to get RLC
    rlc = bls.bytes48_to_G1(g1_lincomb(commitments, weights))

    # Step 4.2: Compute RLI = [sum_k r^k interpolation_poly_k(s)]
    # Note: an efficient implementation would use the IDFT based method explained in the blog post
    sum_interp_polys_coeff = PolynomialCoeff([BLSFieldElement(0)] * n)
    for k in range(num_cells):
        interp_poly_coeff = interpolate_polynomialcoeff(coset_for_cell(cell_indices[k]), cosets_evals[k])
        interp_poly_scaled_coeff = multiply_polynomialcoeff(PolynomialCoeff([r_powers[k]]), interp_poly_coeff)
        sum_interp_polys_coeff = add_polynomialcoeff(sum_interp_polys_coeff, interp_poly_scaled_coeff)
    rli = bls.bytes48_to_G1(g1_lincomb(KZG_SETUP_G1_MONOMIAL[:n], sum_interp_polys_coeff))

    # Step 4.3: Compute RLP = sum_k (r^k * h_k^n) proofs[k]
    weighted_r_powers = []
    for k in range(num_cells):
        h_k = coset_shift_for_cell(cell_indices[k])
        h_k_pow = h_k.pow(BLSFieldElement(n))
        wrp = r_powers[k] * h_k_pow
        weighted_r_powers.append(wrp)
    rlp = bls.bytes48_to_G1(g1_lincomb(proofs, weighted_r_powers))

    # Step 4.4: Compute RL = RLC - RLI + RLP
    rl = bls.add(rlc, bls.neg(rli))
    rl = bls.add(rl, rlp)

    # Step 5: Check pairing (LL, LR) = pairing (RL, [1])
    return (bls.pairing_check([
        [ll, lr],
        [rl, bls.neg(bls.bytes96_to_G2(KZG_SETUP_G2_MONOMIAL[0]))],
    ]))
```

### Cell cosets

#### `coset_shift_for_cell`

```python
def coset_shift_for_cell(cell_index: CellIndex) -> BLSFieldElement:
    """
    Get the shift that determines the coset for a given ``cell_index``.
    Precisely, consider the group of roots of unity of order FIELD_ELEMENTS_PER_CELL * CELLS_PER_EXT_BLOB.
    Let G = {1, g, g^2, ...} denote its subgroup of order FIELD_ELEMENTS_PER_CELL.
    Then, the coset is defined as h * G = {h, hg, hg^2, ...} for an element h.
    This function returns h.
    """
    assert cell_index < CELLS_PER_EXT_BLOB
    roots_of_unity_brp = bit_reversal_permutation(
        compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB)
    )
    return roots_of_unity_brp[FIELD_ELEMENTS_PER_CELL * cell_index]
```

#### `coset_for_cell`

```python
def coset_for_cell(cell_index: CellIndex) -> Coset:
    """
    Get the coset for a given ``cell_index``.
    Precisely, consider the group of roots of unity of order FIELD_ELEMENTS_PER_CELL * CELLS_PER_EXT_BLOB.
    Let G = {1, g, g^2, ...} denote its subgroup of order FIELD_ELEMENTS_PER_CELL.
    Then, the coset is defined as h * G = {h, hg, hg^2, ...}.
    This function, returns the coset.
    """
    assert cell_index < CELLS_PER_EXT_BLOB
    roots_of_unity_brp = bit_reversal_permutation(
        compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB)
    )
    return Coset(roots_of_unity_brp[FIELD_ELEMENTS_PER_CELL * cell_index:FIELD_ELEMENTS_PER_CELL * (cell_index + 1)])
```

## Cells

### Cell computation

#### `compute_cells`

```python
def compute_cells(blob: Blob) -> Vector[Cell, CELLS_PER_EXT_BLOB]:
    """
    Given a blob, extend it and return all the cells of the extended blob.

    Public method.
    """
    assert len(blob) == BYTES_PER_BLOB

    polynomial = blob_to_polynomial(blob)
    polynomial_coeff = polynomial_eval_to_coeff(polynomial)

    cells = []
    for i in range(CELLS_PER_EXT_BLOB):
        coset = coset_for_cell(CellIndex(i))
        ys = CosetEvals([evaluate_polynomialcoeff(polynomial_coeff, z) for z in coset])
        cells.append(coset_evals_to_cell(CosetEvals(ys)))
    return cells
```

#### `compute_cells_and_kzg_proofs_polynomialcoeff`

```python
def compute_cells_and_kzg_proofs_polynomialcoeff(polynomial_coeff: PolynomialCoeff) -> Tuple[
        Vector[Cell, CELLS_PER_EXT_BLOB],
        Vector[KZGProof, CELLS_PER_EXT_BLOB]]:
    """
    Helper function which computes cells/proofs for a polynomial in coefficient form.
    """
    cells, proofs = [], []
    for i in range(CELLS_PER_EXT_BLOB):
        coset = coset_for_cell(CellIndex(i))
        proof, ys = compute_kzg_proof_multi_impl(polynomial_coeff, coset)
        cells.append(coset_evals_to_cell(CosetEvals(ys)))
        proofs.append(proof)
    return cells, proofs
```

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
    return compute_cells_and_kzg_proofs_polynomialcoeff(polynomial_coeff)
```

### Cell verification

#### `verify_cell_kzg_proof_batch`

```python
def verify_cell_kzg_proof_batch(commitments_bytes: Sequence[Bytes48],
                                cell_indices: Sequence[CellIndex],
                                cells: Sequence[Cell],
                                proofs_bytes: Sequence[Bytes48]) -> bool:
    """
    Verify that a set of cells belong to their corresponding commitments.

    Given four lists representing tuples of (``commitment``, ``cell_index``, ``cell``, ``proof``),
    the function verifies ``proof`` which shows that ``cell`` are the evaluations of the polynomial
    associated with ``commitment``, evaluated over the domain specified by ``cell_index``.

    This function implements the universal verification equation that has been introduced here:
    https://ethresear.ch/t/a-universal-verification-equation-for-data-availability-sampling/13240

    Public method.
    """

    assert len(commitments_bytes) == len(cells) == len(proofs_bytes) == len(cell_indices)
    for commitment_bytes in commitments_bytes:
        assert len(commitment_bytes) == BYTES_PER_COMMITMENT
    for cell_index in cell_indices:
        assert cell_index < CELLS_PER_EXT_BLOB
    for cell in cells:
        assert len(cell) == BYTES_PER_CELL
    for proof_bytes in proofs_bytes:
        assert len(proof_bytes) == BYTES_PER_PROOF

    # Create the list of deduplicated commitments we are dealing with
    deduplicated_commitments = [bytes_to_kzg_commitment(commitment_bytes)
                                for commitment_bytes in set(commitments_bytes)]
    # Create indices list mapping initial commitments (that may contain duplicates) to the deduplicated commitments
    commitment_indices = [CommitmentIndex(deduplicated_commitments.index(commitment_bytes))
                          for commitment_bytes in commitments_bytes]

    cosets_evals = [cell_to_coset_evals(cell) for cell in cells]
    proofs = [bytes_to_kzg_proof(proof_bytes) for proof_bytes in proofs_bytes]

    # Do the actual verification
    return verify_cell_kzg_proof_batch_impl(
        deduplicated_commitments,
        commitment_indices,
        cell_indices,
        cosets_evals,
        proofs)
```

## Reconstruction

### `construct_vanishing_polynomial`

```python
def construct_vanishing_polynomial(missing_cell_indices: Sequence[CellIndex]) -> Sequence[BLSFieldElement]:
    """
    Given the cells indices that are missing from the data, compute the polynomial that vanishes at every point that
    corresponds to a missing field element.

    This method assumes that all of the cells cannot be missing. In this case the vanishing polynomial
    could be computed as Z(x) = x^n - 1, where `n` is FIELD_ELEMENTS_PER_EXT_BLOB.

    We never encounter this case however because this method is used solely for recovery and recovery only
    works if at least half of the cells are available.
    """
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

### `recover_polynomialcoeff`

```python
def recover_polynomialcoeff(cell_indices: Sequence[CellIndex],
                            cosets_evals: Sequence[CosetEvals]) -> PolynomialCoeff:
    """
    Recover the polynomial in coefficient form that when evaluated at the roots of unity will give the extended blob.
    """
    # Get the extended domain. This will be referred to as the FFT domain.
    roots_of_unity_extended = compute_roots_of_unity(FIELD_ELEMENTS_PER_EXT_BLOB)

    # Flatten the cosets evaluations.
    # If a cell is missing, then its evaluation is zero.
    # We let E(x) be a polynomial of degree FIELD_ELEMENTS_PER_EXT_BLOB - 1
    # that interpolates the evaluations including the zeros for missing ones.
    extended_evaluation_rbo = [BLSFieldElement(0)] * FIELD_ELEMENTS_PER_EXT_BLOB
    for cell_index, cell in zip(cell_indices, cosets_evals):
        start = cell_index * FIELD_ELEMENTS_PER_CELL
        end = (cell_index + 1) * FIELD_ELEMENTS_PER_CELL
        extended_evaluation_rbo[start:end] = cell
    extended_evaluation = bit_reversal_permutation(extended_evaluation_rbo)

    # Compute the vanishing polynomial Z(x) in coefficient form.
    # Z(x) is the polynomial which vanishes on all of the evaluations which are missing.
    missing_cell_indices = [CellIndex(cell_index) for cell_index in range(CELLS_PER_EXT_BLOB)
                            if cell_index not in cell_indices]
    zero_poly_coeff = construct_vanishing_polynomial(missing_cell_indices)

    # Convert Z(x) to evaluation form over the FFT domain
    zero_poly_eval = fft_field(zero_poly_coeff, roots_of_unity_extended)

    # Compute (E*Z)(x) = E(x) * Z(x) in evaluation form over the FFT domain
    # Note: over the FFT domain, the polynomials (E*Z)(x) and (P*Z)(x) agree, where
    # P(x) is the polynomial we want to reconstruct (degree FIELD_ELEMENTS_PER_BLOB - 1).
    extended_evaluation_times_zero = [a * b for a, b in zip(zero_poly_eval, extended_evaluation)]

    # We know that (E*Z)(x) and (P*Z)(x) agree over the FFT domain,
    # and we know that (P*Z)(x) has degree at most FIELD_ELEMENTS_PER_EXT_BLOB - 1.
    # Thus, an inverse FFT of the evaluations of (E*Z)(x) (= evaluations of (P*Z)(x))
    # yields the coefficient form of (P*Z)(x).
    extended_evaluation_times_zero_coeffs = fft_field(extended_evaluation_times_zero, roots_of_unity_extended, inv=True)

    # Next step is to divide the polynomial (P*Z)(x) by polynomial Z(x) to get P(x).
    # We do this in evaluation form over a coset of the FFT domain to avoid division by 0.

    # Convert (P*Z)(x) to evaluation form over a coset of the FFT domain
    extended_evaluations_over_coset = coset_fft_field(extended_evaluation_times_zero_coeffs, roots_of_unity_extended)

    # Convert Z(x) to evaluation form over a coset of the FFT domain
    zero_poly_over_coset = coset_fft_field(zero_poly_coeff, roots_of_unity_extended)

    # Compute P(x) = (P*Z)(x) / Z(x) in evaluation form over a coset of the FFT domain
    reconstructed_poly_over_coset = [a / b for a, b in zip(extended_evaluations_over_coset, zero_poly_over_coset)]

    # Convert P(x) to coefficient form
    reconstructed_poly_coeff = coset_fft_field(reconstructed_poly_over_coset, roots_of_unity_extended, inv=True)

    return PolynomialCoeff(reconstructed_poly_coeff[:FIELD_ELEMENTS_PER_BLOB])
```

### `recover_cells_and_kzg_proofs`

```python
def recover_cells_and_kzg_proofs(cell_indices: Sequence[CellIndex],
                                 cells: Sequence[Cell]) -> Tuple[
        Vector[Cell, CELLS_PER_EXT_BLOB],
        Vector[KZGProof, CELLS_PER_EXT_BLOB]]:
    """
    Given at least 50% of cells for a blob, recover all the cells/proofs.
    This algorithm uses FFTs to recover cells faster than using Lagrange
    implementation, as can be seen here:
    https://ethresear.ch/t/reed-solomon-erasure-code-recovery-in-n-log-2-n-time-with-ffts/3039

    A faster version thanks to Qi Zhou can be found here:
    https://github.com/ethereum/research/blob/51b530a53bd4147d123ab3e390a9d08605c2cdb8/polynomial_reconstruction/polynomial_reconstruction_danksharding.py

    Public method.
    """
    # Check we have the same number of cells and indices
    assert len(cell_indices) == len(cells)
    # Check we have enough cells to be able to perform the reconstruction
    assert CELLS_PER_EXT_BLOB // 2 <= len(cell_indices) <= CELLS_PER_EXT_BLOB
    # Check for duplicates
    assert len(cell_indices) == len(set(cell_indices))
    # Check that the cell indices are within bounds
    for cell_index in cell_indices:
        assert cell_index < CELLS_PER_EXT_BLOB
    # Check that each cell is the correct length
    for cell in cells:
        assert len(cell) == BYTES_PER_CELL

    # Convert cells to coset evaluations
    cosets_evals = [cell_to_coset_evals(cell) for cell in cells]

    # Given the coset evaluations, recover the polynomial in coefficient form
    polynomial_coeff = recover_polynomialcoeff(cell_indices, cosets_evals)

    # Recompute all cells/proofs
    return compute_cells_and_kzg_proofs_polynomialcoeff(polynomial_coeff)
```
