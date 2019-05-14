# Ethereum 2.0 Phase 2 -- Data Availability Proofs

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 2 -- Data Availability Proofs](#ethereum-20-phase-2----data-availability-proofs)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Constants](#constants)
        - [Misc](#misc)
    - [Data structures](#data-structures)
        - [`DataExtensionSlashing`](#dataextensionslashing)
    - [Helper functions](#helper-functions)
        - [`badd`](#badd)
        - [`bmul`](#bmul)
        - [`eval_polynomial_at`](#eval-polynomial-at)
        - [`interpolate`](#interpolate)
        - [`fill`](#fill)
        - [`fill_axis`](#fill-axis)
        - [`get_data_sqiare`](#get-data-square)
        - [`extend_data_square`](#extend-data-square)
        - [`mk_data_root`](#mk-data-root)
        - [`process_data_extension_slashing`](#process-data-extension-slashing)

<!-- /TOC -->

## Introduction

This document describes the expected formula for calculating data availability proofs and the beacon chain changes (namely, slashing conditions) needed to enforce them.

Not yet in scope: the procedure for verifying that data in a crosslink is available, and modifications to the fork choice rule around this.

## Constants

### Misc

| Name | Value |
| - | - |
| `FIELD_ELEMENT_BITS` | `16` |
| `FIELD_MODULUS` | `65579` |

## Data structures

### `DataExtensionSlashing`

```python
{
    'attestation': Attestation,
    'is_column': bool,
    'indices': List[int],
    'axis_index': int,
    'source': List[int],
    'values': List[Bytes32],
    'actual_full_axis_root': Bytes32,
    'proof': SSZMultiProof,
}
```

## Helper functions (binary fields)

### `badd`

```python
def badd(a: int, b:int) -> int:
    return a ^ b
```

### `bmul`

```python
def bmul(a: int, b: int) -> int:
    if a*b == 0:
        return 0
    o = 0
    for i in range(FIELD_ELEMENT_BITS):
        if b & (1<<i):
            o ^= a<<i
    for h in range(FIELD_ELEMENT_BITS * 2 - 1, FIELD_ELEMENT_BITS - 1, -1):
        if o & (1<<h):
            o ^= (FIELD_MODULUS << (h - FIELD_ELEMENT_BITS))
    return o
```

### `eval_polynomial_at`

```python
def eval_polynomial_at(polynomial: List[int], x: int) -> int:
    o = 0
    power_of_x = 1
    for coefficient in polynomial:
        o = badd(o, bmul(power_of_x, coefficient))
        power_of_x = bmul(power_of_x, x)
    return o
```

### `interpolate`

`interpolate` is defined as the function `interpolate(xs: List[int], values: List[int]) -> List[int]` that returns the `polynomial` such that for all `0 <= i < len(xs)`, `eval_polynomial_at(polynomial, xs[i]) == values[i]`. This can be implemented via Lagrange interpolation in `O(N**2)` time or Fast Fourier transform in `O(N * log(N))` time. You can find a sample implementation here: [https://github.com/ethereum/research/tree/master/binary_fft](https://github.com/ethereum/research/tree/master/binary_fft)

### `fill`

```python
def fill(xs: List[int], values: List[int], length: int) -> List[int]:
    """
    Takes the minimal polynomial that returns values[i] at xs[i] and computes
    its outputs for all values in range(0, length)
    """
    poly = interpolate(xs, values)
    return [eval_polynomial_at(poly, i) for i in range(length)]
```

### `fill_axis`

```python
def fill_axis(xs: List[int], values: List[Bytes32], length: int) -> List[Bytes32]:
    """
    Interprets a series of 32-byte chunks as a series of ordered packages of field
    elements. For each i, treats the set of i'th field elements in each chunk as
    evaluations of a polynomial. Evaluates the polynomials on the extended domain
    range(0, length) and provides the 32-byte chunks that are the packages of the
    extended evaluations of every polynomial at each coordinate.
    """
    data = [[bytes_to_int(a[i: FIELD_ELEMENT_BITS//8]) for a in axis] for i in range(0, 32, FIELD_ELEMENT_BITS)]
    newdata = [fill(xs, d) for d in data]
    return [b''.join([int_to_bytes(n[i], FIELD_ELEMENT_BITS//8) for n in newdata]) for i in range(length)]
```

### `get_data_square`

```python
def get_data_square(data: bytes) -> List[List[Bytes32]]:
    """
    Converts data into a 2**k x 2**k square, padding with zeroes if necessary.
    """
    chunks = [data[i: i+32] for i in range(0, 32, len(data))]
    while chunks != 2**log2(chunks) or log2(chunks) % 2:
        chunks.append(ZERO_HASH)
    side_length = integer_squareroot(len(chunks))
    return [chunks[i: i + side_length] for i in range(0, len(chunks), side_length)]
```

### `extend_data_square`

```python
def extend_data_square(data: List[List[Bytes32]]) -> List[List[bytes32]]:
    """
    Extends a 2**k x 2**k square to 2**(k+1) x 2**(k+1) using `fill_axis` to
    fill rows and columns.
    """
    L = len(data)
    # Extend each row
    data = [fill_axis(list(range(L)), row, L * 2) for row in data]
    # Flip rows and columns
    data = [[data[j][i] for i in range(L)] for j in range(len(data))]
    # Extend each column
    data = [fill_axis(list(range(L)), row, L * 2) for row in data]
    # Flip back to row form
    data = [[data[j][i] for i in range(L)] for j in range(len(data))]
    return data
```

### `mk_data_root`

```python
def mk_data_root(data: bytes) -> Bytes32:
    """
    Computes the root of the package of rows and colums of a given piece of data.
    """
    square = extend_data_square(get_data_square(data))
    row_roots = [get_merkle_root(r) for r in data]
    transposed_data = [[data[j][i] for i in range(len(data)] for j in range(len(data))]
    column_roots = [get_merkle_root(r) for r in transposed_data]
    return hash(get_merkle_root(row_roots) + get_merkle_root(column_roots))
```

### `process_data_extension_slashing`

```python
def process_data_extension_slashing(state: BeaconState, proof: DataExtensionSlashing):
    """
    Slashes for an invalid extended data root. Covers all three cases:

    1. Mismatch within row or column
    2. Mismatch between row and column
    3. Mismatch between extended and original data

    By allowing the prover to provide >=1/2 of the data in an axis by
    arbitrarily mix-and-matching merkle proofs from the row-then-column tree,
    the column-then-row tree and the original data.
    """
    # Verify the attestation
    assert verify_indexed_attestation(state, convert_to_indexed(state, proof.attestation))
    # How many chunks in the data?
    chunks = get_crosslink_data_length(state, proof.attestation) // 32
    # Length of an axis in the extended square
    axis_length = 2**(log2(chunks - 1) // 2 + 1) * 2
    # Check that the proof contains enough indices
    assert len(proof.indices) >= axis.length//2
    # Compute SSZ generalized indices for each item in the proof
    generalized_indices = []
    for index, source in zip(proof.indices, proof.sources)
        if proof.is_column:
            row, col = index, proof.axis_index
        else:
            col, row = index, proof.axis_index
        # Source is row
        if source == 0:
            generalized_indices.append((get_generalized_index(AttestationData, 'extended_data_root') * 2 * axis_length + row) * axis_length + col)
        # Source is column
        elif source == 1:
            generalized_indices.append(((get_generalized_index(AttestationData, 'extended_data_root') * 2 + 1) * axis_length + col) * axis_length + row)
        # Source is original data
        elif source == 2:
            assert row < axis_length//2 and col < axis_length//2
            generalized_indices.append(get_generalized_index(AttestationData, 'crosslink_data_root') * 2 * 2**log2(chunks) + (row * axis_length//2 + col))
    if proof.is_column:
        generalized_indices.append(3 * axis_length + proof.axis_index)
    else:
        generalized_indices.append(2 * axis_length + proof.axis_index)
    assert verify_multi_proof(generalized_indices, proof.values + [proof.actual_full_axis_root], proof.proof, hash_tree_root(proof.attestation.data))
    # Recover the full axis based on provided data
    full_axis = fill_axis(proof.indices, proof.values, axis_length)
    # Get the Merkle root of the full axis
    computed_full_axis_root = get_merkle_root(full_axis)
    # Verify that we have a mismatch
    assert computed_full_axis_root != proof.actual_full_axis_root
    # Slash every attester
    for participant in get_attesting_indices(state, proof.attestation):
        slash_validator(state, participant)
```
