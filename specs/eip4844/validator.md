# EIP-4844 -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [`is_data_available`](#is_data_available)
  - [`verify_blobs_sidecar`](#verify_blobs_sidecar)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [Blob commitments](#blob-commitments)
  - [Beacon Block publishing time](#beacon-block-publishing-time)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement EIP-4844.

## Prerequisites

This document is an extension of the [Bellatrix -- Honest Validator](../bellatrix/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated [Beacon Chain doc of EIP4844](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

### `is_data_available`

The implementation of `is_data_available` is meant to change with later sharding upgrades.
Initially, it requires every verifying actor to retrieve the matching `BlobsSidecar`,
and verify the sidecar with `verify_blobs`.

Without the sidecar the block may be processed further optimistically,
but MUST NOT be considered valid until a valid `BlobsSidecar` has been downloaded.

```python
def is_data_available(slot: Slot, beacon_block_root: Root, kzgs: Sequence[KZGCommitment]):
    sidecar = retrieve_blobs_sidecar(slot, beacon_block_root)  # implementation dependent, raises an exception if not available
    verify_blobs_sidecar(slot, beacon_block_root, kzgs, sidecar)
```

### `verify_blobs_sidecar`

```python
def hash_to_bls_field(x: Container) -> BLSFieldElement:
    """
    This function is used to generate Fiat-Shamir challenges. The output is not uniform over the BLS field.
    """
    return int.from_bytes(hash_tree_root(x), "little") % BLS_MODULUS


def compute_powers(x: BLSFieldElement, n: uint64) -> List[BLSFieldElement]:
    current_power = 1
    powers = []
    for _ in range(n):
        powers.append(BLSFieldElement(current_power))
        current_power = current_power * int(x) % BLS_MODULUS
    return powers


def vector_lincomb(vectors: List[List[BLSFieldElement]], scalars: List[BLSFieldElement]) -> List[BLSFieldElement]:
    """
    Given a list of vectors, compute the linear combination of each column with `scalars`, and return the resulting
    vector.
    """
    r = [0]*len(vectors[0])
    for v, a in zip(vectors, scalars):
        for i, x in enumerate(v):
            r[i] = (r[i] + a * x) % BLS_MODULUS
    return [BLSFieldElement(x) for x in r]


def bls_modular_inverse(x: BLSFieldElement) -> BLSFieldElement:
    """
    Compute the modular inverse of x using the eGCD algorithm
    i.e. return y such that x * y % BLS_MODULUS == 1 and return 0 for x == 0
    """
    if x == 0:
        return 0

    lm, hm = 1, 0
    low, high = x % BLS_MODULUS, BLS_MODULUS
    while low > 1:
        r = high // low
        nm, new = hm - lm * r, high - low * r
        lm, low, hm, high = nm, new, lm, low
    return lm % BLS_MODULUS


def div(x, y):
    """Divide two field elements: `x` by `y`"""
    return x * inv(y) % MODULUS


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


def verify_blobs_sidecar(slot: Slot, beacon_block_root: Root,
                         expected_kzgs: Sequence[KZGCommitment], blobs_sidecar: BlobsSidecar):
    assert slot == blobs_sidecar.beacon_block_slot
    assert beacon_block_root == blobs_sidecar.beacon_block_root
    blobs = blobs_sidecar.blobs
    kzg_aggregated_proof = blobs_sidecar.kzg_aggregated_proof
    assert len(expected_kzgs) == len(blobs)

    # Generate random linear combination challenges
    r = hash_to_bls_field([blobs, expected_kzgs])
    r_powers = compute_powers(r, len(expected_kzgs))

    # Compute commitment to aggregated polynomial
    aggregated_poly_commitment = lincomb(expected_kzgs, r_powers)

    # Create aggregated polynomial in evaluation form
    aggregated_poly = vector_lincomb(blobs, r_powers)

    # Generate challenge `x` and evaluate the aggregated polynomial at `x`
    x = hash_to_bls_field([aggregated_poly, aggregated_poly_commitment])
    y = evaluate_polynomial_in_evaluation_form(aggregated_poly, x)

    # Verify aggregated proof
    assert verify_kzg_proof(aggregated_poly_commitment, x, y, kzg_aggregated_proof)
```


## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.
Namely, the blob handling and the addition of `BlobsSidecar`.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### Blob commitments

After retrieving the execution payload from the execution engine as specified in Bellatrix,
the blobs are retrieved and processed: 

```python
# execution_payload = execution_engine.get_payload(payload_id)
# block.body.execution_payload = execution_payload
# ...

kzgs, blobs = get_blobs(payload_id)

# Optionally sanity-check that the KZG commitments match the versioned hashes in the transactions
assert verify_kzgs_against_transactions(execution_payload.transactions, kzgs)

# Optionally sanity-check that the KZG commitments match the blobs (as produced by the execution engine)
assert len(kzgs) == len(blobs) and [blob_to_kzg(blob) == kzg for blob, kzg in zip(blobs, kzgs)]

# Update the block body 
block.body.blob_kzgs = kzgs
```

The `blobs` should be held with the block in preparation of publishing.
Without the `blobs`, the published block will effectively be ignored by honest validators.

Note: This API is *unstable*. `get_blobs` and `get_payload` may be unified.
Implementers may also retrieve blobs individually per transaction.

### Beacon Block publishing time

Before publishing a prepared beacon block proposal, the corresponding blobs are packaged into a sidecar object for distribution to the network:

```python
blobs_sidecar = BlobsSidecar(
    beacon_block_root=hash_tree_root(beacon_block)
    beacon_block_slot=beacon_block.slot
    shard=0,
    blobs=blobs,
)
```

And then signed:

```python
domain = get_domain(state, DOMAIN_BLOBS_SIDECAR, blobs_sidecar.beacon_block_slot / SLOTS_PER_EPOCH)
signing_root = compute_signing_root(blobs_sidecar, domain)
signature = bls.Sign(privkey, signing_root)
signed_blobs_sidecar = SignedBlobsSidecar(message=blobs_sidecar, signature=signature)
```

This `signed_blobs_sidecar` is then published to the global `blobs_sidecar` topic as soon as the `beacon_block` is published.

After publishing the sidecar peers on the network may request the sidecar through sync-requests, or a local user may be interested.
The validator MUST hold on to blobs for `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` epochs and serve when capable,
to ensure the data-availability of these blobs throughout the network.

After `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` nodes MAY prune the blobs and/or stop serving them.

