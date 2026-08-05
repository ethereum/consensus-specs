# Gloas Light Client -- Full Node

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `block_to_light_client_header`](#modified-block_to_light_client_header)

<!-- mdformat-toc end -->

## Introduction

The execution payload information is reduced to just the block hash as part of
the Gloas upgrade.

## Helpers

### Modified `block_to_light_client_header`

```python
def block_to_light_client_header(block: SignedBeaconBlock) -> LightClientHeader:
    epoch = compute_epoch_at_slot(block.message.slot)

    # [Modified in Gloas:EIP7732]
    if epoch >= GLOAS_FORK_EPOCH:
        execution_block_hash = (
            block.message.body.signed_execution_payload_bid.message.parent_block_hash
        )
        execution_branch = ExecutionBranch(
            compute_merkle_proof(block.message.body, EXECUTION_BLOCK_HASH_GINDEX_GLOAS)
        )
    elif epoch >= DENEB_FORK_EPOCH:
        execution_block_hash = block.message.body.execution_payload.block_hash
        execution_branch = ExecutionBranch(
            normalize_merkle_branch(
                compute_merkle_proof(block.message.body, EXECUTION_BLOCK_HASH_GINDEX_DENEB),
                EXECUTION_BLOCK_HASH_GINDEX_GLOAS,
            )
        )
    elif epoch >= CAPELLA_FORK_EPOCH:
        execution_block_hash = block.message.body.execution_payload.block_hash
        execution_branch = ExecutionBranch(
            normalize_merkle_branch(
                compute_merkle_proof(block.message.body, EXECUTION_BLOCK_HASH_GINDEX),
                EXECUTION_BLOCK_HASH_GINDEX_GLOAS,
            )
        )
    else:
        # Note that during fork transitions, `finalized_header` may still point to earlier forks.
        # While Bellatrix blocks also contain an `ExecutionPayload` (minus `withdrawals_root`),
        # it was not included in the corresponding light client data. To ensure compatibility
        # with legacy data going through `upgrade_lc_header_to_capella`, leave out execution data.
        execution_block_hash = Hash32()
        execution_branch = ExecutionBranch()

    return LightClientHeader(
        beacon=BeaconBlockHeader(
            slot=block.message.slot,
            proposer_index=block.message.proposer_index,
            parent_root=block.message.parent_root,
            state_root=block.message.state_root,
            body_root=hash_tree_root(block.message.body),
        ),
        execution_block_hash=execution_block_hash,
        execution_branch=execution_branch,
    )
```
