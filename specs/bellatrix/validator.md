# Bellatrix -- Honest Validator

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Prerequisites](#prerequisites)
- [Helpers](#helpers)
  - [`GetPayloadResponse`](#getpayloadresponse)
  - [`get_pow_block_at_terminal_total_difficulty`](#get_pow_block_at_terminal_total_difficulty)
  - [`get_terminal_pow_block`](#get_terminal_pow_block)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`get_payload`](#get_payload)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Block proposal](#block-proposal)
    - [Constructing the `BeaconBlockBody`](#constructing-the-beaconblockbody)
      - [ExecutionPayload](#executionpayload)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement executable beacon chain proposal.

## Prerequisites

This document is an extension of the [Altair -- Honest Validator](../altair/validator.md) guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of [Bellatrix](./beacon-chain.md) are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Helpers

### `GetPayloadResponse`

```python
@dataclass
class GetPayloadResponse(object):
    execution_payload: ExecutionPayload
```

### `get_pow_block_at_terminal_total_difficulty`

```python
def get_pow_block_at_terminal_total_difficulty(pow_chain: Dict[Hash32, PowBlock]) -> Optional[PowBlock]:
    # `pow_chain` abstractly represents all blocks in the PoW chain
    for block in pow_chain.values():
        block_reached_ttd = block.total_difficulty >= TERMINAL_TOTAL_DIFFICULTY
        if block_reached_ttd:
            # If genesis block, no parent exists so reaching TTD alone qualifies as valid terminal block
            if block.parent_hash == Hash32():
                return block
            parent = pow_chain[block.parent_hash]
            parent_reached_ttd = parent.total_difficulty >= TERMINAL_TOTAL_DIFFICULTY
            if not parent_reached_ttd:
                return block

    return None
```

### `get_terminal_pow_block`

```python
def get_terminal_pow_block(pow_chain: Dict[Hash32, PowBlock]) -> Optional[PowBlock]:
    if TERMINAL_BLOCK_HASH != Hash32():
        # Terminal block hash override takes precedence over terminal total difficulty
        if TERMINAL_BLOCK_HASH in pow_chain:
            return pow_chain[TERMINAL_BLOCK_HASH]
        else:
            return None

    return get_pow_block_at_terminal_total_difficulty(pow_chain)
```

*Note*: This function does *not* use simple serialize `hash_tree_root` as to
avoid requiring simple serialize hashing capabilities in the Execution Layer.

## Protocols

### `ExecutionEngine`

*Note*: `get_payload` function is added to the `ExecutionEngine` protocol for use as a validator.

The body of this function is implementation dependent.
The Engine API may be used to implement it with an external execution engine.

#### `get_payload`

Given the `payload_id`, `get_payload` returns `GetPayloadResponse` with the most recent version of
the execution payload that has been built since the corresponding call to `notify_forkchoice_updated` method.

```python
def get_payload(self: ExecutionEngine, payload_id: PayloadId) -> GetPayloadResponse:
    """
    Return ``GetPayloadResponse`` object.
    """
    ...
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below. Namely, the transition block handling and the addition of `ExecutionPayload`.

*Note*: A validator must not propose on or attest to a block that isn't deemed valid, i.e. hasn't yet passed the beacon chain state transition and execution validations. In future upgrades, an "execution Proof-of-Custody" will be integrated to prevent outsourcing of execution payload validations.

### Block proposal

#### Constructing the `BeaconBlockBody`

##### ExecutionPayload

To obtain an execution payload, a block proposer building a block on top of a `state` must take the following actions:

1. Set `payload_id = prepare_execution_payload(state, pow_chain, safe_block_hash, finalized_block_hash, suggested_fee_recipient, execution_engine)`, where:
   - `state` is the state object after applying `process_slots(state, slot)` transition to the resulting state of the parent block processing
   - `pow_chain` is a `Dict[Hash32, PowBlock]` dictionary that abstractly represents all blocks in the PoW chain with block hash as the dictionary key
   - `safe_block_hash` is the return value of the `get_safe_execution_block_hash(store: Store)` function call
   - `finalized_block_hash` is the block hash of the latest finalized execution payload (`Hash32()` if none yet finalized)
   - `suggested_fee_recipient` is the value suggested to be used for the `fee_recipient` field of the execution payload

```python
def prepare_execution_payload(state: BeaconState,
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              suggested_fee_recipient: ExecutionAddress,
                              execution_engine: ExecutionEngine,
                              pow_chain: Optional[Dict[Hash32, PowBlock]]=None) -> Optional[PayloadId]:
    if not is_merge_transition_complete(state):
        assert pow_chain is not None
        is_terminal_block_hash_set = TERMINAL_BLOCK_HASH != Hash32()
        is_activation_epoch_reached = get_current_epoch(state) >= TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH
        if is_terminal_block_hash_set and not is_activation_epoch_reached:
            # Terminal block hash is set but activation epoch is not yet reached, no prepare payload call is needed
            return None

        terminal_pow_block = get_terminal_pow_block(pow_chain)
        if terminal_pow_block is None:
            # Pre-merge, no prepare payload call is needed
            return None
        # Signify merge via producing on top of the terminal PoW block
        parent_hash = terminal_pow_block.block_hash
    else:
        # Post-merge, normal payload
        parent_hash = state.latest_execution_payload_header.block_hash

    # Set the forkchoice head and initiate the payload build process
    payload_attributes = PayloadAttributes(
        timestamp=compute_timestamp_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=parent_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```

2. Set `block.body.execution_payload = get_execution_payload(payload_id, execution_engine)`, where:

```python
def get_execution_payload(payload_id: Optional[PayloadId], execution_engine: ExecutionEngine) -> ExecutionPayload:
    if payload_id is None:
        # Pre-merge, empty payload
        return ExecutionPayload()
    else:
        return execution_engine.get_payload(payload_id).execution_payload
```

*Note*: It is recommended for a validator to call `prepare_execution_payload` as soon as input parameters become known,
and make subsequent calls to this function when any of these parameters gets updated.
