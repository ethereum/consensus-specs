# EIP-4844 -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Custom types](#custom-types)
- [Containers](#containers)
  - [`BlobsAndCommmitments`](#blobsandcommmitments)
  - [`PolynomialAndCommitment`](#polynomialandcommitment)
- [Helpers](#helpers)
  - [`is_data_available`](#is_data_available)
  - [`hash_to_bls_field`](#hash_to_bls_field)
  - [`compute_powers`](#compute_powers)
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

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `Polynomial` | `List[BLSFieldElement, MAX_BLOBS_PER_BLOCK]` | a polynomial in evaluation form |

## Containers

### `BlobsAndCommmitments`

```python
class BlobsAndCommmitments(Container):
    blobs: List[Blob, MAX_BLOBS_PER_BLOCK]
    blob_kzgs: List[KZGCommitment, MAX_BLOBS_PER_BLOCK]
```

### `PolynomialAndCommitment`

```python
class PolynomialAndCommitment(Container):
    polynomial: Polynomial
    commitment: KZGCommitment
```


## Helpers

### `is_data_available`

The implementation of `is_data_available` is meant to change with later sharding upgrades.
Initially, it requires every verifying actor to retrieve the matching `BlobsSidecar`,
and verify the sidecar with `verify_blobs_sidecar`.

Without the sidecar the block may be processed further optimistically,
but MUST NOT be considered valid until a valid `BlobsSidecar` has been downloaded.

```python
def is_data_available(slot: Slot, beacon_block_root: Root, kzgs: Sequence[KZGCommitment]):
    # `retrieve_blobs_sidecar` is implementation dependent, raises an exception if not available.
    sidecar = retrieve_blobs_sidecar(slot, beacon_block_root)
    verify_blobs_sidecar(slot, beacon_block_root, kzgs, sidecar)
```

### `hash_to_bls_field`

```python
def hash_to_bls_field(x: Container) -> BLSFieldElement:
    """
    This function is used to generate Fiat-Shamir challenges. The output is not uniform over the BLS field.
    """
    return int.from_bytes(hash_tree_root(x), "little") % BLS_MODULUS
```

### `compute_powers`
```python
def compute_powers(x: BLSFieldElement, n: uint64) -> Sequence[BLSFieldElement]:
    current_power = 1
    powers = []
    for _ in range(n):
        powers.append(BLSFieldElement(current_power))
        current_power = current_power * int(x) % BLS_MODULUS
    return powers
```

### `verify_blobs_sidecar`

```python
def verify_blobs_sidecar(slot: Slot, beacon_block_root: Root,
                         expected_kzgs: Sequence[KZGCommitment], blobs_sidecar: BlobsSidecar) -> bool:
    assert slot == blobs_sidecar.beacon_block_slot
    assert beacon_block_root == blobs_sidecar.beacon_block_root
    blobs = blobs_sidecar.blobs
    kzg_aggregated_proof = blobs_sidecar.kzg_aggregated_proof
    assert len(expected_kzgs) == len(blobs)

    # Generate random linear combination challenges
    r = hash_to_bls_field(BlobsAndCommmitments(blobs=blobs, blob_kzgs=expected_kzgs))
    r_powers = compute_powers(r, len(expected_kzgs))

    # Create aggregated polynomial in evaluation form
    aggregated_poly = Polynomial(matrix_lincomb(blobs, r_powers))

    # Compute commitment to aggregated polynomial
    aggregated_poly_commitment = KZGCommitment(lincomb(expected_kzgs, r_powers))

    # Generate challenge `x` and evaluate the aggregated polynomial at `x`
    x = hash_to_bls_field(PolynomialAndCommitment(polynomial=aggregated_poly, commitment=aggregated_poly_commitment))
    y = evaluate_polynomial_in_evaluation_form(aggregated_poly, x)

    # Verify aggregated proof
    return verify_kzg_proof(aggregated_poly_commitment, x, y, kzg_aggregated_proof)
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below.
Namely, the blob handling and the addition of `BlobsSidecar`.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### Blob commitments

After retrieving the execution payload from the execution engine as specified in Bellatrix,
the blobs are retrieved and processed: 

```
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
def get_blobs_sidecar(block: BeaconBlock, blobs: Sequence[Blob]) -> BlobsSidecar:
    return BlobsSidecar(
        beacon_block_root=hash_tree_root(block),
        beacon_block_slot=block.slot,
        blobs=blobs,
    )
```

And then signed:

```python
def get_signed_blobs_sidecar(state: BeaconState, blobs_sidecar: BlobsSidecar, privkey: int) -> SignedBlobsSidecar:
    domain = get_domain(state, DOMAIN_BLOBS_SIDECAR, blobs_sidecar.beacon_block_slot // SLOTS_PER_EPOCH)
    signing_root = compute_signing_root(blobs_sidecar, domain)
    signature = bls.Sign(privkey, signing_root)
    return SignedBlobsSidecar(message=blobs_sidecar, signature=signature)
```

This `signed_blobs_sidecar` is then published to the global `blobs_sidecar` topic as soon as the `beacon_block` is published.

After publishing the sidecar peers on the network may request the sidecar through sync-requests, or a local user may be interested.
The validator MUST hold on to blobs for `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` epochs and serve when capable,
to ensure the data-availability of these blobs throughout the network.

After `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS` nodes MAY prune the blobs and/or stop serving them.
