# EIP-8025 -- Fork Choice

This document contains the fork-choice specifications for EIP-8025.

*Note*: This specification is built upon [Gloas](../../gloas/fork-choice.md).

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Data structures](#data-structures)
  - [Modified `Store`](#modified-store)
- [Store initialization](#store-initialization)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
- [Handlers](#handlers)
  - [New `on_execution_proof`](#new-on_execution_proof)

<!-- mdformat-toc end -->

## Data structures

### Modified `Store`

```python
@dataclass
class Store:
    time: Uint64
    genesis_time: Uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: Set[ValidatorIndex]
    blocks: Dict[Root, BeaconBlock]
    block_states: Dict[Root, BeaconState]
    block_timeliness: Dict[Root, list[Boolean]]
    checkpoint_states: Dict[Checkpoint, BeaconState]
    latest_messages: Dict[ValidatorIndex, LatestMessage]
    unrealized_justifications: Dict[Root, Checkpoint]
    payloads: Dict[Root, ExecutionPayloadEnvelope]
    payload_timeliness_vote: Dict[Root, list[Optional[Boolean]]]
    payload_data_availability_vote: Dict[Root, list[Optional[Boolean]]]
    # [New in EIP8025]
    execution_proofs: Dict[Root, Dict[ProofType, ExecutionProof]]
```

## Store initialization

### Modified `get_forkchoice_store`

```python
def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    anchor_epoch = get_current_epoch(anchor_state)
    justified_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    finalized_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    proposer_boost_root = Root()
    return Store(
        time=Uint64(anchor_state.genesis_time + SLOT_DURATION_MS * anchor_state.slot // 1000),
        genesis_time=anchor_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        unrealized_justified_checkpoint=justified_checkpoint,
        unrealized_finalized_checkpoint=finalized_checkpoint,
        proposer_boost_root=proposer_boost_root,
        equivocating_indices=set(),
        blocks={anchor_root: copy(anchor_block)},
        block_states={anchor_root: copy(anchor_state)},
        block_timeliness={anchor_root: [True, True]},
        checkpoint_states={justified_checkpoint: copy(anchor_state)},
        latest_messages={},
        unrealized_justifications={anchor_root: justified_checkpoint},
        payloads={},
        payload_timeliness_vote={},
        payload_data_availability_vote={},
        # [New in EIP8025]
        execution_proofs={},
    )
```

## Handlers

### New `on_execution_proof`

The handler `on_execution_proof` is called when the node accepts a
`SignedExecutionProof` for downstream processing.

```python
def on_execution_proof(
    store: Store,
    signed_execution_proof: SignedExecutionProof,
    execution_checkpoint: ExecutionCheckpoint,
    proof_engine: ProofEngine,
) -> None:
    proof = signed_execution_proof.message
    head = proof.claim.head
    head_root = head.beacon_block_root

    # The corresponding beacon block must be known and valid
    assert head_root in store.blocks
    assert head_root in store.block_states

    # Only one verified proof is stored for each head and proof type
    assert proof.proof_type not in store.execution_proofs.get(head_root, {})

    # The public input must identify the configured origin and local head block
    assert proof.claim.origin == execution_checkpoint
    assert head.slot == store.blocks[head_root].slot

    # Validate against the state associated with the proof's head block
    state = store.block_states[head_root]
    process_execution_proof(
        state,
        signed_execution_proof,
        proof_engine,
    )

    # Store only proofs that pass downstream verification
    if head_root not in store.execution_proofs:
        store.execution_proofs[head_root] = {}
    store.execution_proofs[head_root][proof.proof_type] = proof
```
