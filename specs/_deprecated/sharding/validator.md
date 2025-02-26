# Sharding -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

  - [Introduction](#introduction)
  - [Prerequisites](#prerequisites)
  - [Constants](#constants)
    - [Sample counts](#sample-counts)
  - [Helpers](#helpers)
    - [`get_validator_row_subnets`](#get_validator_row_subnets)
    - [`get_validator_column_subnets`](#get_validator_column_subnets)
    - [`reconstruct_polynomial`](#reconstruct_polynomial)
  - [Sample verification](#sample-verification)
    - [`verify_sample`](#verify_sample)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Validator assignments](#validator-assignments)
    - [Attesting](#attesting)
- [Sample reconstruction](#sample-reconstruction)
  - [Minimum online validator requirement](#minimum-online-validator-requirement)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement executable beacon chain proposal.

## Prerequisites

This document is an extension of the [Bellatrix -- Honest Validator](../../bellatrix/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [Sharding](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Constants

### Sample counts

| Name | Value |
| - | - |
| `VALIDATOR_SAMPLE_ROW_COUNT` | `2` |
| `VALIDATOR_SAMPLE_COLUMN_COUNT` | `2` |

## Helpers

### `get_validator_row_subnets`

TODO: Currently the subnets are public (i.e. anyone can derive them.) This is good for a proof of custody with public verifiability, but bad for validator privacy.

```python
def get_validator_row_subnets(validator: Validator, epoch: Epoch) -> List[uint64]:
    return [int.from_bytes(hash_tree_root([validator.pubkey, 0, i])) for i in range(VALIDATOR_SAMPLE_ROW_COUNT)]
```

### `get_validator_column_subnets`

```python
def get_validator_column_subnets(validator: Validator, epoch: Epoch) -> List[uint64]:
    return [int.from_bytes(hash_tree_root([validator.pubkey, 1, i])) for i in range(VALIDATOR_SAMPLE_COLUMN_COUNT)]
```

### `reconstruct_polynomial`

```python
def reconstruct_polynomial(samples: List[SignedShardSample]) -> List[SignedShardSample]:
    """
    Reconstructs one full row/column from at least 1/2 of the samples
    """

```

## Sample verification

### `verify_sample`

```python
def verify_sample(state: BeaconState, block: BeaconBlock, sample: SignedShardSample):
    assert sample.row < 2 * get_active_shard_count(state, get_current_epoch(block.slot))
    assert sample.column < 2 * SAMPLES_PER_BLOB
    assert block.slot == sample.slot

    # Verify builder signature.
    # TODO: We should probably not do this. This should only be done by p2p to verify samples *before* intermediate block is in
    # builder = state.validators[signed_block.message.proposer_index]
    # signing_root = compute_signing_root(sample, get_domain(state, DOMAIN_SHARD_SAMPLE))
    # assert bls.Verify(sample.builder, signing_root, sample.signature)

    roots_in_rbo = list_to_reverse_bit_order(roots_of_unity(SAMPLES_PER_BLOB * FIELD_ELEMENTS_PER_SAMPLE))

    # Verify KZG proof
    verify_kzg_multiproof(block.body.payload_data.value.sharded_commitments_container.sharded_commitments[sample.row],
                          roots_in_rbo[sample.column * FIELD_ELEMENTS_PER_SAMPLE:(sample.column + 1) * FIELD_ELEMENTS_PER_SAMPLE]
                          sample.data,
                          sample.proof)
```

# Beacon chain responsibilities

## Validator assignments

### Attesting

Every attester is assigned `VALIDATOR_SAMPLE_ROW_COUNT` rows and `VALIDATOR_SAMPLE_COLUMN_COUNT` columns of shard samples. As part of their validator duties, they should subscribe to the subnets given by `get_validator_row_subnets` and `get_validator_column_subnets`, for the whole epoch.

A row or column is *available* for a `slot` if at least half of the total number of samples were received on the subnet and passed `verify_sample`. Otherwise it is called unavailable.

If a validator is assigned to an attestation at slot `attestation_slot` and had his previous attestation duty at `previous_attestation_slot`, then they should only attest under the following conditions:

 * For all intermediate blocks `block` with `previous_attestation_slot < block.slot <= attestation_slot`: All sample rows and columns assigned to the validator were available.

If this condition is not fulfilled, then the validator should instead attest to the last block for which the condition holds.

This leads to the security property that a chain that is not fully available cannot have more than 1/16th of all validators voting for it. TODO: This claim is for an "infinite number" of validators. Compute the concrete security due to sampling bias.

# Sample reconstruction

A validator that has received enough samples of a row or column to mark it as available, should reconstruct all samples in that row/column (if they aren't all available already.) The function `reconstruct_polynomial` gives an example implementation for this.

Once they have run the reconstruction function, they should distribute the samples that they reconstructed on all pubsub that
the local node is subscribed to, if they have not already received that sample on that pubsub. As an example:

 * The validator is subscribed to row `2` and column `5`
 * The sample `(row, column) = (2, 5)` is missing in the column `5` pubsub
 * After they have reconstruction of row `2`, the validator should send the sample `(2, 5)` on to the row `2` pubsub (if it was missing) as well as the column `5` pubsub.

TODO: We need to verify the total complexity of doing this and make sure this does not cause too much load on a validator

## Minimum online validator requirement

The data availability construction guarantees that reconstruction is possible if 75% of all samples are available. In this case, at least 50% of all rows and 50% of all columns are independently available. In practice, it is likely that some supernodes will centrally collect all samples and fill in any gaps. However, we want to build a system that reliably reconstructs even absent all supernodes. Any row or column with 50% of samples will easily be reconstructed even with only 100s of validators online; so the only question is how we get to 50% of samples for all rows and columns, when some of them might be completely unseeded.

Each validator will transfer 4 samples between rows and columns where there is overlap. Without loss of generality, look at row 0. Each validator has 1/128 chance of having a sample in this row, and we need 256 samples to reconstruct it. So we expect that we need ~256 * 128 = 32,768 validators to have a fair chance of reconstructing it if it was completely unseeded.

A more elaborate estimate [here](https://notes.ethereum.org/@dankrad/minimum-reconstruction-validators) needs about 55,000 validators to be online for high safety that each row and column will be reconstructed.