# EIP-8025 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Data structures](#data-structures)
  - [Modified `Store`](#modified-store)
- [Store initialization](#store-initialization)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
- [Handlers](#handlers)
  - [New `on_execution_proof`](#new-on_execution_proof)

<!-- mdformat-toc end -->

## Introduction

This document extends the fork-choice `Store` to retain verified
`ExecutionProofEnvelope`s. Stored proofs are not fork-choice inputs.

*Note*: This specification is built upon [Gloas](../../gloas/fork-choice.md).

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
    execution_proofs: Dict[Root, Dict[ProofType, ExecutionProofEnvelope]]
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
        payload_timeliness_vote={anchor_root: [None] * PTC_SIZE},
        payload_data_availability_vote={anchor_root: [None] * PTC_SIZE},
        # [New in EIP8025]
        execution_proofs={},
    )
```

## Handlers

### New `on_execution_proof`

The handler `on_execution_proof` is called when the node receives a
`SignedExecutionProofEnvelope` for downstream processing. It verifies and stores
the proof envelope without changing fork-choice weights, head selection,
beacon-chain state, or Gloas payload status.

```python
def on_execution_proof(
    store: Store,
    signed_proof_envelope: SignedExecutionProofEnvelope,
    proof_engine: ProofEngine,
) -> None:
    """
    Verify and store a received execution proof envelope.

    Resolve its beacon state and payload from ``store``, verify the envelope
    and execution proof, then store it without changing fork choice or payload
    status.
    """
    proof_envelope = signed_proof_envelope.message
    beacon_block_root = proof_envelope.beacon_block_root

    # The corresponding beacon block must be known and consensus-valid
    assert beacon_block_root in store.blocks
    state = store.block_states.get(beacon_block_root)
    assert state is not None

    # The corresponding execution payload must be available
    payload_envelope = store.payloads.get(beacon_block_root)
    assert payload_envelope is not None

    # Only one verified proof is stored for each beacon block and proof type
    assert proof_envelope.proof_type not in store.execution_proofs.get(beacon_block_root, {})

    process_execution_proof(state, signed_proof_envelope, payload_envelope, proof_engine)

    # Store only proofs that pass downstream verification
    if beacon_block_root not in store.execution_proofs:
        store.execution_proofs[beacon_block_root] = {}
    store.execution_proofs[beacon_block_root][proof_envelope.proof_type] = proof_envelope
```
