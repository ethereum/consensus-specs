# Fulu -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Blob schedule](#blob-schedule)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
    - [New `BlobScheduleEntry`](#new-blobscheduleentry)
    - [Modified `compute_fork_digest`](#modified-compute_fork_digest)
    - [New `get_max_blobs_per_block`](#new-get_max_blobs_per_block)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [Execution payload](#execution-payload)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)

<!-- mdformat-toc end -->

## Introduction

*Note*: This specification is built upon [Electra](../electra/beacon-chain.md)
and is under active development.

## Configuration

### Blob schedule

*[New in EIP7892]* This schedule defines the maximum blobs per block limit for a
given epoch.

*Note*: The blob schedule is to be determined.

<!-- list-of-records:blob_schedule -->

| Epoch | Max Blobs Per Block | Description |
| ----- | ------------------- | ----------- |

## Helper functions

### Misc

#### New `BlobScheduleEntry`

```python
@dataclass
class BlobScheduleEntry(object):
    epoch: Epoch
    max_blobs_per_block: uint64
```

#### Modified `compute_fork_digest`

*Note:* The `compute_fork_digest` helper is updated to account for
Blob-Parameter-Only forks.

```python
def compute_fork_digest(
  current_version: Version,
  genesis_validators_root: Root,
  current_epoch: Epoch,  # [New in Fulu:EIP7892]
) -> ForkDigest:
    """
    Return the 4-byte fork digest for the ``current_version`` and ``genesis_validators_root``,
    with a XOR bitmask of the big-endian byte representation of current max_blobs_per_block.

    This is a digest primarily used for domain separation on the p2p layer.
    4-bytes suffices for practical separation of forks/chains.
    """
    base_digest = compute_fork_data_root(current_version, genesis_validators_root)[:4]

    if current_epoch < FULU_FORK_EPOCH:
        return base_digest

    # Find the blob parameters applicable to this epoch
    max_blobs_per_block = get_max_blobs_per_block(current_epoch)

    # Safely bitmask blob parameters into the digest
    # If Fulu is deployed with no concurrent blob parameter changes, we'll bitmask Electra's value.
    mask = max_blobs_per_block.to_bytes(4, 'big')
    masked_digest = bytes(a ^ b for a, b in zip(base_digest, mask))
    return ForkDigest(masked_digest)
```

#### New `get_max_blobs_per_block`

*[New in EIP7892]* This schedule defines the maximum blobs per block limit for a
given epoch.

```python
def get_max_blobs_per_block(epoch: Epoch) -> uint64:
    """
    Return the maximum number of blobs that can be included in a block for a given epoch.
    """
    for entry in sorted(BLOB_SCHEDULE, key=lambda e: e["EPOCH"], reverse=True):
        if epoch >= entry["EPOCH"]:
            return entry["MAX_BLOBS_PER_BLOCK"]
    return MAX_BLOBS_PER_BLOCK_ELECTRA
```

## Beacon chain state transition function

### Block processing

#### Execution payload

##### Modified `process_execution_payload`

```python
def process_execution_payload(state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine) -> None:
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert len(body.blob_kzg_commitments) <= get_max_blobs_per_block(get_current_epoch(state))  # [Modified in Fulu:EIP7892]
    # Verify the execution payload is valid
    versioned_hashes = [kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments]
    assert execution_engine.verify_and_notify_new_payload(
        NewPayloadRequest(
            execution_payload=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=body.execution_requests,
        )
    )
    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        withdrawals_root=hash_tree_root(payload.withdrawals),
        blob_gas_used=payload.blob_gas_used,
        excess_blob_gas=payload.excess_blob_gas,
    )
```
