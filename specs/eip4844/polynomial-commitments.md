# EIP-4844 -- Polynomial Commitments

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Preset](#preset)
  - [Trusted setup](#trusted-setup)
- [Helper functions](#helper-functions)
  - [BLS12-381 helpers](#bls12-381-helpers)
    - [`bls_modular_inverse`](#bls_modular_inverse)
    - [`div`](#div)
    - [`lincomb`](#lincomb)
  - [KZG](#kzg)
    - [`blob_to_kzg`](#blob_to_kzg)
    - [`verify_kzg_proof`](#verify_kzg_proof)
  - [Polynomials](#polynomials)
    - [`evaluate_polynomial_in_evaluation_form`](#evaluate_polynomial_in_evaluation_form)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->


## Introduction

This document specifies basic polynomial operations and KZG polynomial commitment operations as they are needed for the EIP-4844 specification. The implementations are not optimized for performance, but readability. All practical implementations should optimize the polynomial operations.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `BLSFieldElement` | `uint256` | `x < BLS_MODULUS` |
| `KZGCommitment` | `Bytes48` | Same as BLS standard "is valid pubkey" check but also allows `0x00..00` for point-at-infinity |
| `KZGProof` | `Bytes48` | Same as for `KZGCommitment` |

## Constants

| Name | Value | Notes |
| - | - | - |
| `BLS_MODULUS` | `52435875175126190479447740508185965837690552500527637822603658699938581184513` | Scalar field modulus of BLS12-381 |
| `ROOTS_OF_UNITY` | `Vector[BLSFieldElement, FIELD_ELEMENTS_PER_BLOB]` | Roots of unity of order FIELD_ELEMENTS_PER_BLOB over the BLS12-381 field |

## Preset

### Trusted setup

The trusted setup is part of the preset: during testing a `minimal` insecure variant may be used,
but reusing the `mainnet` settings in public networks is a critical security requirement.

| Name | Value |
| - | - |
| `KZG_SETUP_G2` | `Vector[G2Point, FIELD_ELEMENTS_PER_BLOB]`, contents TBD |
| `KZG_SETUP_LAGRANGE` | `Vector[KZGCommitment, FIELD_ELEMENTS_PER_BLOB]`, contents TBD |

## Helper functions

### BLS12-381 helpers

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
def div(x, y):
    """Divide two field elements: `x` by `y`"""
    return x * inv(y) % BLS_MODULUS
```

#### `lincomb`

```python
def lincomb(points: List[KZGCommitment], scalars: List[BLSFieldElement]) -> KZGCommitment:
    """
    BLS multiscalar multiplication. This function can be optimized using Pippenger's algorithm and variants.
    """
    r = bls.Z1
    for x, a in zip(points, scalars):
        r = bls.add(r, bls.multiply(x, a))
    return r
```

### KZG

KZG core functions. These are also defined in EIP-4844 execution specs.

#### `blob_to_kzg`

```python
def blob_to_kzg(blob: Blob) -> KZGCommitment:
    return lincomb(KZG_SETUP_LAGRANGE, blob)
```

#### `verify_kzg_proof`

```python
def verify_kzg_proof(polynomial_kzg: KZGCommitment,
                     x: BLSFieldElement,
                     y: BLSFieldElement,
                     quotient_kzg: KZGProof) -> bool:
    """Verify KZG proof that `p(x) == y` where `p(x)` is the polynomial represented by `polynomial_kzg`"""
    # Verify: P - y = Q * (X - x)
    X_minus_x = bls.add(KZG_SETUP_G2[1], bls.multiply(bls.G2, BLS_MODULUS - x))
    P_minus_y = bls.add(polynomial_kzg, bls.multiply(bls.G1, BLS_MODULUS - y))
    return bls.pairing_check([
        [P_minus_y, bls.neg(bls.G2)],
        [quotient_kzg, X_minus_x]
    ])
```

### Polynomials

#### `evaluate_polynomial_in_evaluation_form`

```python
def evaluate_polynomial_in_evaluation_form(poly: List[BLSFieldElement], x: BLSFieldElement) -> BLSFieldElement:
    """
    Evaluate a polynomial (in evaluation form) at an arbitrary point `x`
    Uses the barycentric formula:
       f(x) = (1 - x**WIDTH) / WIDTH  *  sum_(i=0)^WIDTH  (f(DOMAIN[i]) * DOMAIN[i]) / (x - DOMAIN[i])
    """
    width = len(poly)
    assert width == FIELD_ELEMENTS_PER_BLOB
    inverse_width = bls_modular_inverse(width)

    for i in range(width):
        r += div(poly[i] * ROOTS_OF_UNITY[i], (x - ROOTS_OF_UNITY[i]) )
    r = r * (pow(x, width, BLS_MODULUS) - 1) * inverse_width % BLS_MODULUS

    return r
```
