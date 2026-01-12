# EIP-8025 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Constants](#constants)
  - [Execution](#execution)
  - [Domains](#domains)
- [Configuration](#configuration)
- [Containers](#containers)
  - [New containers](#new-containers)
    - [`SignedExecutionProof`](#signedexecutionproof)
    - [`NewPayloadRequestHeader`](#newpayloadrequestheader)
    - [`ExecutionPayloadHeaderEnvelope`](#executionpayloadheaderenvelope)
    - [`SignedExecutionPayloadHeaderEnvelope`](#signedexecutionpayloadheaderenvelope)
  - [Extended containers](#extended-containers)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Execution proof functions](#execution-proof-functions)
    - [`verify_execution_proofs`](#verify_execution_proofs)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution payload processing](#execution-payload-processing)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
  - [Execution proof handlers](#execution-proof-handlers)
    - [New `process_signed_execution_proof`](#new-process_signed_execution_proof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-8025. This enables
stateless validation of execution payloads through cryptographic proofs.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md).

*Note*: This specification assumes the reader is familiar with the
[public zkEVM methods exposed](./zkevm.md).

## Constants

### Execution

| Name                               | Value                                  |
| ---------------------------------- | -------------------------------------- |
| `MAX_EXECUTION_PROOFS_PER_PAYLOAD` | `uint64(4)`                            |
| `PROGRAM`                          | `ProgramBytecode(b"DEFAULT__PROGRAM")` |

### Domains

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType('0x0D000000')` |

## Configuration

*Note*: The configuration values are not definitive.

| Name                            | Value       |
| ------------------------------- | ----------- |
| `MIN_REQUIRED_EXECUTION_PROOFS` | `uint64(1)` |

```python
WHITELISTED_PROVERS: List[BLSPubkey] = [
    # List of allowed prover public keys
]
```

## Containers

### New containers

#### `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
    prover_id: Union[BuilderIndex, BLSPubkey]
    signature: BLSSignature
```

#### `NewPayloadRequestHeader`

```python
@dataclass
class NewPayloadRequestHeader(object):
    execution_payload_header: ExecutionPayloadHeader
    versioned_hashes: Sequence[VersionedHash]
    parent_beacon_block_root: Root
    execution_requests: ExecutionRequests
```

#### `ExecutionPayloadHeaderEnvelope`

```python
class ExecutionPayloadHeaderEnvelope(Container):
    payload: ExecutionPayloadHeader
    execution_requests: ExecutionRequests
    builder_index: BuilderIndex
    beacon_block_root: Root
    slot: Slot
    blob_kzg_commitments: List[KZGCommitment, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    state_root: Root
```

#### `SignedExecutionPayloadHeaderEnvelope`

```python
class SignedExecutionPayloadHeaderEnvelope(Container):
    message: ExecutionPayloadHeaderEnvelope
    signature: BLSSignature
```

### Extended containers

#### `BeaconState`

```python
class BeaconState(Container):
    # ... existing fields ...
    # [New in EIP-8025]
    execution_proof_store: Map[Root, List[SignedExecutionProof, MAX_EXECUTION_PROOFS_PER_PAYLOAD]]
    pending_execution_proof_store: Map[Root, List[SignedExecutionProof, MAX_EXECUTION_PROOFS_PER_PAYLOAD]]
```

*Note*: `BeaconBlockBody` remains unchanged.

## Helpers

### Execution proof functions

#### `verify_execution_proofs`

```python
def verify_execution_proofs(state: BeaconState, new_payload_request_root: Root) -> bool:
    """
    Verify that execution proofs are available and valid for an execution payload.
    """
    proofs = state.execution_proof_store.get(new_payload_request_root, [])

    # Verify there are sufficient proofs
    if len(proofs) < MIN_REQUIRED_EXECUTION_PROOFS:
        return False

    return True
```

## Beacon chain state transition function

### Execution payload processing

#### Modified `process_execution_payload`

```python
def process_execution_payload(
    state: BeaconState,
    # [Modified in EIP-8025]
    # Accept either full envelope or header-only envelope
    signed_envelope: Union[SignedExecutionPayloadEnvelope, SignedExecutionPayloadHeaderEnvelope],
    execution_engine: ExecutionEngine,
    verify: bool = True,
) -> None:
    """
    Process an execution payload envelope or header.
    When a header is provided, validation uses execution proofs.
    """

    envelope = signed_envelope.message
    payload = envelope.payload

    # Verify signature
    if verify:
        assert verify_execution_payload_envelope_signature(state, signed_envelope)

    # Cache latest block header state root
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Root():
        state.latest_block_header.state_root = previous_state_root

    # Verify consistency with the beacon block
    assert envelope.beacon_block_root == hash_tree_root(state.latest_block_header)
    assert envelope.slot == state.slot

    # Verify consistency with the committed bid
    committed_bid = state.latest_execution_payload_bid
    assert envelope.builder_index == committed_bid.builder_index
    assert committed_bid.blob_kzg_commitments_root == hash_tree_root(envelope.blob_kzg_commitments)
    assert committed_bid.prev_randao == payload.prev_randao

    # Verify consistency with expected withdrawals
    assert hash_tree_root(payload.withdrawals) == hash_tree_root(state.payload_expected_withdrawals)

    # Verify the gas_limit
    assert committed_bid.gas_limit == payload.gas_limit
    # Verify the block hash
    assert committed_bid.block_hash == payload.block_hash
    # Verify consistency of the parent hash with respect to the previous execution payload
    assert payload.parent_hash == state.latest_block_hash
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert (
        len(envelope.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )
    # Verify the execution payload is valid
    versioned_hashes = [
        kzg_commitment_to_versioned_hash(commitment) for commitment in envelope.blob_kzg_commitments
    ]
    requests = envelope.execution_requests

    if isinstance(signed_envelope, SignedExecutionPayloadHeaderEnvelope):
        # Header-only validation using execution proofs
        new_payload_request_header = NewPayloadRequestHeader(
            execution_payload_header=payload,
            versioned_hashes=versioned_hashes,
            parent_beacon_block_root=state.latest_block_header.parent_root,
            execution_requests=requests,
        )
        new_payload_request_root = hash_tree_root(new_payload_request_header)

        # Create entry in execution_proof_store (marks header as received)
        state.execution_proof_store[new_payload_request_root] = []

        # Move pending proofs to execution_proof_store
        if new_payload_request_root in state.pending_execution_proof_store:
            state.execution_proof_store[new_payload_request_root].extend(
                state.pending_execution_proof_store[new_payload_request_root]
            )
            del state.pending_execution_proof_store[new_payload_request_root]

        assert verify_execution_proofs(state, new_payload_request_root)
    else:
        # Full payload validation via ExecutionEngine
        assert execution_engine.verify_and_notify_new_payload(
            NewPayloadRequest(
                execution_payload=payload,
                versioned_hashes=versioned_hashes,
                parent_beacon_block_root=state.latest_block_header.parent_root,
                execution_requests=requests,
            )
        )

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(requests.deposits, process_deposit_request)
    for_ops(requests.withdrawals, process_withdrawal_request)
    for_ops(requests.consolidations, process_consolidation_request)

    # Queue the builder payment
    payment = state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH]
    amount = payment.withdrawal.amount
    if amount > 0:
        state.builder_pending_withdrawals.append(payment.withdrawal)
    state.builder_pending_payments[SLOTS_PER_EPOCH + state.slot % SLOTS_PER_EPOCH] = (
        BuilderPendingPayment()
    )

    # Cache the execution payload hash
    state.execution_payload_availability[state.slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
    state.latest_block_hash = payload.block_hash

    # Verify the state root
    if verify:
        assert envelope.state_root == hash_tree_root(state)
```

### Execution proof handlers

#### New `process_signed_execution_proof`

```python
def process_signed_execution_proof(
    state: BeaconState,
    signed_proof: SignedExecutionProof,
) -> None:
    """
    Handler for SignedExecutionProof.
    Supports both builders (via BuilderIndex) and provers (via BLSPubkey).
    """
    proof_message = signed_proof.message
    prover_id = signed_proof.prover_id

    # Determine pubkey based on prover_id type
    if isinstance(prover_id, BLSPubkey):
        # Prover path - verify whitelist
        assert prover_id in WHITELISTED_PROVERS
        pubkey = prover_id
    else:
        # Builder path
        if prover_id == BUILDER_INDEX_SELF_BUILD:
            validator_index = state.latest_block_header.proposer_index
            pubkey = state.validators[validator_index].pubkey
        else:
            pubkey = state.builders[prover_id].pubkey

    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_message, domain)
    assert bls.Verify(pubkey, signing_root, signed_proof.signature)

    # Verify the execution proof
    program_bytecode = ProgramBytecode(PROGRAM + proof_message.proof_type.to_bytes(1, "little"))
    assert verify_execution_proof(proof_message, program_bytecode)

    # Store proof based on whether header has been received
    new_payload_request_root = proof_message.public_inputs.new_payload_request_root

    if new_payload_request_root in state.execution_proof_store:
        # Header already received, store directly
        state.execution_proof_store[new_payload_request_root].append(signed_proof)

        # Mark payload as available if sufficient proofs gathered
        if len(state.execution_proof_store[new_payload_request_root]) >= MIN_REQUIRED_EXECUTION_PROOFS:
            state.execution_payload_availability[state.slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
    else:
        # Header not yet received, cache in pending store
        if new_payload_request_root not in state.pending_execution_proof_store:
            state.pending_execution_proof_store[new_payload_request_root] = []
        state.pending_execution_proof_store[new_payload_request_root].append(signed_proof)
```
