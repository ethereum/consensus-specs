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

*Note*: A pre-Gloas block is turned into a header by the function of its own
fork, and the result is brought forward with `upgrade_lc_header_to_gloas`. The
execution block hash and its proof are read from the payload bid, which only a
Gloas block carries.

```python
def block_to_light_client_header(block: SignedBeaconBlock) -> LightClientHeader:
    return LightClientHeader(
        beacon=BeaconBlockHeader(
            slot=block.message.slot,
            proposer_index=block.message.proposer_index,
            parent_root=block.message.parent_root,
            state_root=block.message.state_root,
            body_root=hash_tree_root(block.message.body),
        ),
        # [Modified in Gloas:EIP7732]
        execution_block_hash=(
            block.message.body.signed_execution_payload_bid.message.parent_block_hash
        ),
        # [Modified in Gloas:EIP7732]
        execution_branch=ExecutionBranch(
            data=compute_merkle_proof(block.message.body, EXECUTION_BLOCK_HASH_GINDEX_GLOAS)
        ),
    )
```
