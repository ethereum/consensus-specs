# Sharding -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [`get_pow_block_at_terminal_total_difficulty`](#get_pow_block_at_terminal_total_difficulty)
  - [`get_terminal_pow_block`](#get_terminal_pow_block)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`get_payload`](#get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement executable beacon chain proposal.

## Prerequisites

This document is an extension of the [Bellatrix -- Honest Validator](../bellatrix/validator.md) guide.
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

    # Verify KZG proof
    verify_kzg_multiproof(block.body.sharded_commitments_container.value.sharded_commitments[sample.row],
                          ??? # TODO! Compute the roots of unity for this sample 
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

TODO: Compute what the minimum number of validators online would be that guarantees reconstruction of all samples
