# Ethereum 2.0 Phase 2 -- Data Availability Checks

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

| Name | Value | Description |
| - | - | - |
| `FIELD_ELEMENT_BITS` | `16` | 2 bytes |
| `FIELD_MODULUS` | `65579` | |
| `CHUNKS_PER_ROW` | `2**13 = 8,192` | 256 kB |
| `ROWS_PER_BLOCK` | `MAX_SHARD_BLOCK_SIZE // 32 // CHUNKS_PER_ROW = 4` | |
| `CHUNKS_PER_BLOCK` | `CHUNKS_PER_ROW * ROWS_PER_BLOCK = 32,768` | |
| `DOMAIN_DATA_AVAILABILITY` | `144` | |
| `DOMAIN_DATA_AVAILABILITY_SLASH` | `145` | |

## Data structures

### `DataAvailabilityProof`

```python
{
    'rows': List[Vector[Bytes32, CHUNKS_PER_ROW], ROWS_PER_BLOCK * MAX_SHARDS * MAX_SHARD_BLOCKS_PER_ATTESTATION],
    'extension': List[Vector[Bytes32, CHUNKS_PER_ROW], ROWS_PER_BLOCK * MAX_SHARDS * MAX_SHARD_BLOCKS_PER_ATTESTATION],
    'columns': Vector[List[Bytes32, ROWS_PER_BLOCK * MAX_SHARDS * MAX_SHARD_BLOCKS_PER_ATTESTATION], CHUNKS_PER_ROW * 2],
    'row_cutoff': uint64
    'row_count': uint64
}
```

### `SignedDataAvailabilityProof`

```python
{
    'data': DataAvailabilityProof,
    'signature': BLSSignature
}
```

### `DataExtensionSlashing`

```python
{
    'is_column': bool,
    'checking_extension': bool,
    'indices': List[int],
    'axis_index': int,
    'source_is_column': List[bool],
    'values': List[Bytes32],
    'row_cutoff': uint64,
    'row_count': uint64,
    'actual_full_axis_root': Bytes32,
    'data_availability_root': Bytes32,
    'data_availability_root_signature': BLSSignature,
    'proof': SSZMultiProof,
    'slasher_index': ValidatorIndex,
}
```

### `SignedDataExtensionSlashing`

```python
{
    'data': DataExtensionSlashing,
    'slasher_signature': BLSSignature
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

### `multi_evaluate`

`multi_evaluate` is defined as the function `multi_evaluate(xs: List[int], polynomial: List[int]) -> List[int]` that returns `[eval_polynomial_at(polynomial, x) for x in xs]`, though there are faster Fast Fourier Transform-based algorithms.

### `interpolate`

`interpolate` is defined as the function `interpolate(xs: List[int], values: List[int]) -> List[int]` that returns the `polynomial` such that for all `0 <= i < len(xs)`, `eval_polynomial_at(polynomial, xs[i]) == values[i]`. This can be implemented via Lagrange interpolation in `O(N**2)` time or Fast Fourier transform in `O(N * log(N))` time.

You can find a sample implementation here: [https://github.com/ethereum/research/tree/master/binary_fft](https://github.com/ethereum/research/tree/master/binary_fft)

### `fill`

```python
def fill(xs: List[int], values: List[int], length: int) -> List[int]:
    """
    Takes the minimal polynomial that returns values[i] at xs[i] and computes
    its outputs for all values in range(0, length)
    """
    poly = interpolate(xs, values)
    return multi_evaluate(list(range(length)), poly)
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
    data = [[bytes_to_int(a[i: FIELD_ELEMENT_BITS//8]) for a in values] for i in range(0, 32, FIELD_ELEMENT_BITS)]
    newdata = [fill(xs, d, length) for d in data]
    return [b''.join([int_to_bytes(n[i], FIELD_ELEMENT_BITS//8) for n in newdata]) for i in range(length)]
```

### `get_full_data_availability_proof`

```python
def get_full_data_availability_proof(blocks: List[Bytes[MAX_SHARD_BLOCK_SIZE]]) -> DataAvailabilityProof:
    """
    Converts data into a row_count * ROW_SIZE rectangle, padding with zeroes if necessary,
    and then extends both dimensions by 2x, in the row case only adding one new row per
    nonzero row
    """
    # Split blocks into rows, express rows as sequences of 32-byte chunks
    rows = []
    for block in blocks:
        block = block + b'\x00' * (MAX_SHARD_BLOCK_SIZE - len(block))
        for pos in range(0, CHUNKS_PER_BLOCK, CHUNKS_PER_ROW):
            rows.append([block[i: i+32] for i in range(pos, pos + CHUNKS_PER_ROW, 32)])
    # Number of rows that are not entirely zero bytes
    nonzero_row_count = len([row for row in rows if row != [ZERO_HASH] * CHUNKS_PER_ROW])
    # Add one vertical extension row for every nonzero row
    new_rows = [[] for _ in range(nonzero_row_count)]
    for i in range(CHUNKS_PER_ROW):
        vertical_extension = fill_axis(list(range(len(rows))), [row[i] for row in rows], len(rows) + nonzero_row_count)
        for new_row, new_value in zip(new_rows, vertical_extension[len(rows):]):
            new_row.append(new_value)
    rows.extend(new_rows)
    # Extend all rows horizontally
    extension = []
    for row in rows:
        extension.append(fill_axis(list(range(CHUNKS_PER_ROW)), row, CHUNKS_PER_ROW * 2)[CHUNKS_PER_ROW:])
    # Compute columns
    columns = (
        [[row[i] for row in rows] for i in range(CHUNKS_PER_ROW)] +
        [[row[i] for row in extension] for i in range(CHUNKS_PER_ROW)]
    )
    return DataAvailabilityProof(rows, extension, columns, len(blocks) * ROWS_PER_BLOCK, len(rows))
```

### `process_data_extension_slashing`

```python
def process_data_extension_slashing(state: BeaconState, signed_proof: SignedDataExtensionSlashing):
    """
    Slashes for an invalid extended data root. Covers both mismatches within a
    row and column and mismatches between rows and columns.

    This is done by allowing the prover to provide >=1/2 of the data in an axis by
    arbitrarily mix-and-matching merkle proofs from the row-then-column tree and
    the column-then-row tree.
    """
    # Verify the signature
    assert bls_verify(
        pubkey=state.validators[get_signer_index(proof)].pubkey,
        message_hash=proof.data_availability_root,
        signature=proof.data_availability_root_signature,
        domain=get_domain(state, DOMAIN_DATA_AVAILABILITY, get_current_epoch(state))
    )
    proof = signed_proof.data
    assert bls_verify(
        pubkey=state.validators[proof.slasher_index].pubkey,
        message_hash=proof,
        signature=signed_proof.signature,
        domain=get_domain(state, DOMAIN_DATA_AVAILABILITY_SLASH, get_current_epoch(state))
    )
    # Get generalized indices (for proof verification)
    generalized_indices = [get_generalized_index(DataAvailabilityProof, 'row_cutoff')]
    if proof.is_column:
        # Case 1: proof is getting indices along a column
        assert proof.checking_extension is False
        generalized_indices.append(get_generalized_index(DataAvailabilityProof, 'columns', proof.axis_index))
        coordinates = [(index, proof.axis_index) for index in proof.indices]
    elif proof.checking_extension:
        # Case 2: proof is getting indices along a row, we are checking against the extension root
        generalized_indices.append(get_generalized_index(DataAvailabilityProof, 'extension', proof.axis_index - CHUNKS_PER_ROW))
        coordinates = [(proof.axis_index, index) for index in proof.indices]
    else:
        # Case 3: proof is getting indices along a row, we are checking against the row root
        generalized_indices.append(get_generalized_index(DataAvailabilityProof, 'rows', proof.axis_index))
        coordinates = [(proof.axis_index, index) for index in proof.indices]
    # Each individual element can be come from the row/extension trees, or from the column tree
    assert proof.indices == sorted(set(proof.indices))
    for source_is_column, (row, column) in zip(proof.source_is_column, proof.coordinates):
        assert row < proof.row_count and column < CHUNKS_PER_ROW * 2
        if source_is_column:
            new_index = get_generalized_index(DataAvailabilityProof, 'columns', column, row)
        else:
            if proof.axis_index < CHUNKS_PER_ROW:
                new_index = get_generalized_index(DataAvailabilityProof, 'rows', row, column)
            else:
                new_index = get_generalized_index(DataAvailabilityProof, 'extension', row - CHUNKS_PER_ROW, column)
        generalized_indices.append(new_index)
    assert len(proof.indices) >= (proof.row_cutoff if proof.is_column else CHUNKS_PER_ROW)
    # Verify Merkle proof
    assert verify_merkle_multiproof(
        [int_to_bytes32(proof.row_cutoff), proof.actual_full_axis_root] + proof.values,
        proof,
        generalized_indices,
        proof.data_availability_root
    )
    # Verify erasure code extension mismatches
    axis_length = CHUNKS_PER_ROW * 2 if proof.is_column else proof.row_count
    filled_values = fill_axis(proof.indices, proof.values, axis_length)
    assert root(filled_values) != proof.actual_full_axis_root
        
    # Slash every attester
    slash_validator(state, get_signer_index(proof), proof.slasher_index)
