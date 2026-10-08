# EIP-9998 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Data structures](#data-structures)
  - [Modified `Store`](#modified-store)
- [Handlers](#handlers)
  - [Modified `on_execution_proof`](#modified-on_execution_proof)

<!-- mdformat-toc end -->

## Introduction

This document follows the change to signed execution proofs. The store retains
verified `ExecutionProof`s. The handler does not require the execution payload,
since an execution chain proof is verified from its roots alone.

*Note*: A stored proof does not imply that the head's execution payload is
available, or that any later block applied it. Stored proofs are not a sync
anchor for payload availability.

*Note*: This specification is built upon [EIP-8025](../eip8025/fork-choice.md).

## Data structures

### Modified `Store`

```python
@dataclass
class Store:
    time_ms: Uint64
    genesis_time_ms: Uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: set[ValidatorIndex]
    blocks: dict[Root, BeaconBlock]
    block_states: dict[Root, BeaconState]
    block_timeliness: dict[Root, list[bool]]
    checkpoint_states: dict[Checkpoint, BeaconState]
    latest_messages: dict[ValidatorIndex, LatestMessage]
    unrealized_justifications: dict[Root, Checkpoint]
    payloads: dict[Root, ExecutionPayloadEnvelope]
    payload_timeliness_vote: dict[Root, list[Boolean | None]]
    payload_data_availability_vote: dict[Root, list[Boolean | None]]
    # [Modified in EIP9998]
    execution_proofs: defaultdict[Root, dict[ProofType, ExecutionProof]]
```

## Handlers

### Modified `on_execution_proof`

```python
def on_execution_proof(
    store: Store,
    # [Modified in EIP9998]
    signed_proof: SignedExecutionProof,
    proof_engine: ProofEngine,
) -> None:
    """
    Verify and store a received execution proof.
    """
    proof = signed_proof.message
    # [Modified in EIP9998]
    head_block_root = proof.head_block_root

    # The corresponding beacon block must be known and consensus-valid
    assert head_block_root in store.blocks
    state = store.block_states.get(head_block_root)
    assert state is not None

    # Only one verified proof is stored for each beacon block and proof type
    assert proof.proof_type not in store.execution_proofs.get(head_block_root, {})

    # [Modified in EIP9998]
    process_execution_proof(state, signed_proof, proof_engine)

    # Store only proofs that pass downstream verification
    store.execution_proofs[head_block_root][proof.proof_type] = proof
```
