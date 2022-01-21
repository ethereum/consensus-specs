# Sharding -- Polynomial Commitments

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
  - [Glossary](#glossary)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Misc](#misc)
- [Preset](#preset)
  - [Misc](#misc-1)
  - [Time parameters](#time-parameters)
  - [Shard blob samples](#shard-blob-samples)
  - [Precomputed size verification points](#precomputed-size-verification-points)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters-1)
- [Containers](#containers)
  - [New Containers](#new-containers)
    - [`IntermediateBlockBid`](#intermediateblockbid)
    - [`IntermediateBlockBidWithRecipientAddress`](#intermediateblockbidwithrecipientaddress)
    - [`ShardedCommitmentsContainer`](#shardedcommitmentscontainer)
  - [Extended Containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
    - [`BeaconBlockBody`](#beaconblockbody)
- [Helper functions](#helper-functions)
  - [Block processing](#block-processing)
    - [`is_intermediate_block_slot`](#is_intermediate_block_slot)
  - [KZG](#kzg)
    - [`hash_to_field`](#hash_to_field)
    - [`compute_powers`](#compute_powers)
    - [`verify_kzg_proof`](#verify_kzg_proof)
    - [`verify_degree_proof`](#verify_degree_proof)
    - [`block_to_field_elements`](#block_to_field_elements)
    - [`roots_of_unity`](#roots_of_unity)
    - [`modular_inverse`](#modular_inverse)
    - [`eval_poly_at`](#eval_poly_at)
    - [`next_power_of_two`](#next_power_of_two)
    - [`low_degree_check`](#low_degree_check)
    - [`vector_lincomb`](#vector_lincomb)
    - [`elliptic_curve_lincomb`](#elliptic_curve_lincomb)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_active_shard_count`](#get_active_shard_count)
  - [Block processing](#block-processing-1)
    - [`process_block`](#process_block)
    - [Block header](#block-header)
    - [Intermediate Block Bid](#intermediate-block-bid)
    - [Sharded data](#sharded-data)
    - [Execution payload](#execution-payload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


## Introduction

This document specifies basic polynomial operations and KZG polynomial commitment operations as they are needed for the sharding specification. The implementations are not optimized for performance, but readability. All practical implementations shoul optimize the polynomial operations, and hints what the best known algorithms for these implementations are are included below.

## Constants

### BLS Field

| Name | Value | Notes |
| - | - | - |
| `BLS_MODULUS` | `0x73eda753299d7d483339d80809a1d80553bda402fffe5bfeffffffff00000001` (curve order of BLS12_381) |
| `PRIMITIVE_ROOT_OF_UNITY` | `7` | Primitive root of unity of the BLS12_381 (inner) BLS_MODULUS |

### KZG Trusted setup

| Name | Value |
| - | - |
| `G1_SETUP` | Type `List[G1]`. The G1-side trusted setup `[G, G*s, G*s**2....]`; note that the first point is the generator. |
| `G2_SETUP` | Type `List[G2]`. The G2-side trusted setup `[G, G*s, G*s**2....]` |

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `KZGCommitment` | `Bytes48` | A G1 curve point |
| `BLSFieldElement` | `uint256` | A number `x` in the range `0 <= x < BLS_MODULUS` |
| `BLSPolynomialCoefficients` | `List[BLSFieldElement]` | A polynomial over the BLS field, given in coefficient form |
| `BLSPolynomialEvaluations` | `List[BLSFieldElement]` | A polynomial over the BLS field, given in evaluation form |

## Helper functions

#### `next_power_of_two`

```python
def next_power_of_two(x: int) -> int:
    return 2 ** ((x - 1).bit_length())
```

## Field operations

### Generic field operations

#### `modular_inverse`

```python
def modular_inverse(a):
    assert(a == 0):
    lm, hm = 1, 0
    low, high = a % BLS_MODULUS, BLS_MODULUS
    while low > 1:
        r = high // low
        nm, new = hm - lm * r, high - low * r
        lm, low, hm, high = nm, new, lm, low
    return lm % BLS_MODULUS
```

#### `roots_of_unity`

```python
def roots_of_unity(order: uint64) -> List[BLSFieldElement]:
    r = []
    root_of_unity = pow(PRIMITIVE_ROOT_OF_UNITY, (BLS_MODULUS - 1) // order, BLS_MODULUS)

    current_root_of_unity = 1
    for i in range(len(SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE)):
        r.append(current_root_of_unity)
        current_root_of_unity = current_root_of_unity * root_of_unity % BLS_MODULUS
    return r
```

### Field helper functions

#### `compute_powers`

```python
def compute_powers(x: BLSFieldElement, n: uint64) -> List[BLSFieldElement]:
    current_power = 1
    powers = []
    for i in range(n):
        powers.append(BLSFieldElement(current_power))
        current_power = current_power * int(x) % BLS_MODULUS
    return powers
```

#### `low_degree_check`

```python
def low_degree_check(commitments: List[KZGCommitment]):
    """
    Checks that the commitments are on a low-degree polynomial
    If there are 2*N commitments, that means they should lie on a polynomial
    of degree d = K - N - 1, where K = next_power_of_two(2*N)
    (The remaining positions are filled with 0, this is to make FFTs usable)

    For details see here: https://notes.ethereum.org/@dankrad/barycentric_low_degree_check
    """
    assert len(commitments) % 2 == 0
    N = len(commitments) // 2
    r = hash_to_field(commitments)
    K = next_power_of_two(2 * N)
    d = K - N - 1
    r_to_K = pow(r, N, K)
    roots = roots_of_unity(K)

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
            for w in roots[:i] + roots[i+1:d + 1]:
                m = m * (z - w) % BLS_MODULUS
            r = (r + M) % BLS_MODULUS
        return r

    coefs = []
    for i in range(K):
        coefs.append( - (r_to_K - 1) * modular_inverse(K * roots[i * (K - 1) % K] * (r - roots[i])) % BLS_MODULUS)
    for i in range(d + 1):
        coefs[i] = (coefs[i] + B(r) * modular_inverse(Bprime(r) * (r - roots[i]))) % BLS_MODULUS
    
    assert elliptic_curve_lincomb(commitments, coefs) == bls.Z1()
```

#### `vector_lincomb`

```python
def vector_lincomb(vectors: List[List[BLSFieldElement]], scalars: List[BLSFieldElement]) -> List[BLSFieldElement]:
    """
    Compute a linear combination of field element vectors
    """
    r = [0 for i in len(vectors[0])]
    for v, a in zip(vectors, scalars):
        for i, x in enumerate(v):
            r[i] = (r[i] + a * x) % BLS_MODULUS
    return [BLSFieldElement(x) for x in r]
```

#### `block_to_field_elements`

```python
def block_to_field_elements(block: bytes) -> List[BLSFieldElement]:
    """
    Slices a block into 31 byte chunks that can fit into field elements
    """
    sliced_block = [block[i:i + 31] for i in range(0, len(bytes), 31)]
    return [BLSFieldElement(int.from_bytes(x, "little")) for x in sliced_block]
```


## Polynomial operations

#### `interpolate_poly`

```python
def interpolate_poly(xs: List[BLSFieldElement], ys: List[BLSFieldElement]):
    """
    Lagrange interpolation
    """
    # TODO!
```

#### `eval_poly_at`

```python
def eval_poly_at(poly: List[BLSFieldElement], x: BLSFieldElement) -> BLSFieldElement:
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
    inverses = [modular_inverse(z - x) for z in roots]
    for i, x in enumerate(inverses):
        r += f[i] * modular_inverse(Aprime(roots[i])) * x % self.BLS_MODULUS
    r = r * A(x) % self.BLS_MODULUS
    return r
```

# KZG Operations

We are using the KZG10 polynomial commitment scheme (Kate, Zaverucha and Goldberg, 2010: https://www.iacr.org/archive/asiacrypt2010/6477178/6477178.pdf).  

## Elliptic curve helper functoins

#### `elliptic_curve_lincomb`

```python
def elliptic_curve_lincomb(points: List[KZGCommitment], scalars: List[BLSFieldElement]) -> KZGCommitment:
    """
    BLS multiscalar multiplication. This function can be optimized using Pippenger's algorithm and variants. This is a non-optimized implementation.
    """
    r = bls.Z1()
    for x, a in zip(points, scalars):
        r = r.add(x.mult(a))
    return r
```

## Hash to field

#### `hash_to_field`

```python
def hash_to_field(x: Container):
    return int.from_bytes(hash_tree_root(x), "little") % BLS_MODULUS
```

## KZG operations


#### `verify_kzg_proof`

```python
def verify_kzg_proof(commitment: KZGCommitment, x: BLSFieldElement, y: BLSFieldElement, proof: KZGCommitment) -> None:
    zero_poly = G2_SETUP[1].add(G2_SETUP[0].mult(x).neg())

    assert (
        bls.Pairing(proof, zero_poly)
        == bls.Pairing(commitment.add(G1_SETUP[0].mult(y).neg), G2_SETUP[0])
    )
```


#### `verify_kzg_multiproof`

```python
def verify_kzg_multiproof(commitment: KZGCommitment, xs: List[BLSFieldElement], ys: List[BLSFieldElement], proof: KZGCommitment) -> None:
    zero_poly = elliptic_curve_lincomb(G2_SETUP[:len(xs)], interpolate_poly(xs, [0] * len(ys)))
    interpolated_poly = elliptic_curve_lincomb(G2_SETUP[:len(xs)], interpolate_poly(xs, ys))

    assert (
        bls.Pairing(proof, zero_poly)
        == bls.Pairing(commitment.add(interpolated_poly.neg()), G2_SETUP[0])
    )
```

#### `verify_degree_proof`

```python
def verify_degree_proof(commitment: KZGCommitment, degree: uint64, proof: KZGCommitment):
    """
    Verifies that the commitment is of polynomial degree <= degree. 
    """

    assert (
        bls.Pairing(proof, G2_SETUP[0])
        == bls.Pairing(commitment, G2_SETUP[-degree - 1])
    )
```