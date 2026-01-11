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
    - [`ExecutionProof`](#executionproof)
    - [`SignedExecutionProof`](#signedexecutionproof)
    - [`NewPayloadRequestHeader`](#newpayloadrequestheader)
    - [`ExecutionPayloadHeaderEnvelope`](#executionpayloadheaderenvelope)
    - [`SignedExecutionPayloadHeaderEnvelope`](#signedexecutionpayloadheaderenvelope)
  - [Extended containers](#extended-containers)
- [Helpers](#helpers)
  - [Execution proof functions](#execution-proof-functions)
    - [`verify_execution_proof`](#verify_execution_proof)
    - [`verify_execution_proofs`](#verify_execution_proofs)
  - [ExecutionEngine methods](#executionengine-methods)
    - [Modified `verify_and_notify_new_payload`](#modified-verify_and_notify_new_payload)
    - [New `verify_and_notify_new_execution_proof`](#new-verify_and_notify_new_execution_proof)
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

## Containers

### New containers

#### `ExecutionProof`

```python
class ExecutionProof(Container):
    zk_proof: ZKEVMProof
    builder_index: BuilderIndex
```

#### `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
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

*Note*: `BeaconState` and `BeaconBlockBody` remain the same. No modifications
are required for execution proofs since they are handled externally.

## Helpers

### Execution proof functions

#### `verify_execution_proof`

```python
def verify_execution_proof(
    proof: ExecutionProof,
    el_program: ProgramBytecode,
) -> bool:
    """
    Verify an execution proof against a NewPayloadRequest root using zkEVM verification.
    """
    # Derive program bytecode from the EL program identifier and proof type
    program_bytecode = ProgramBytecode(
        el_program + proof.zk_proof.proof_type.to_bytes(1, "little")
    )

    return verify_zkevm_proof(proof.zk_proof, program_bytecode)
```

#### `verify_execution_proofs`

```python
def verify_execution_proofs(self: ExecutionEngine, new_payload_request_root: Root) -> bool:
    """
    Verify that execution proofs are available and valid for an execution payload.
    """
    # `retrieve_execution_proofs` is implementation and context dependent.
    # It returns all execution proofs for the given new_payload_request_root.
    proofs = self.execution_proof_store[new_payload_request_root]

    # Verify there are sufficient proofs
    if len(proofs) < MIN_REQUIRED_EXECUTION_PROOFS:
        return False

    return True
```

### ExecutionEngine methods

#### Modified `verify_and_notify_new_payload`

```python
def verify_and_notify_new_payload(
    self: ExecutionEngine,
    new_payload_request: NewPayloadRequest | NewPayloadRequestHeader,
) -> bool:
    """
    Return ``True`` if and only if ``new_payload_request`` is valid with respect to ``self.execution_state``.
    When a ``NewPayloadRequestHeader`` is provided, validation uses execution proofs.
    """
    if isinstance(new_payload_request, NewPayloadRequestHeader):
        # Header-only validation using execution proofs
        # The proof verifies the full NewPayloadRequest
        return self.verify_execution_proofs(new_payload_request.hash_tree_root())

    # Full payload validation (existing GLOAS logic)
    execution_payload = new_payload_request.execution_payload
    parent_beacon_block_root = new_payload_request.parent_beacon_block_root

    if b"" in execution_payload.transactions:
        return False

    if not self.is_valid_block_hash(execution_payload, parent_beacon_block_root):
        return False

    if not self.is_valid_versioned_hashes(new_payload_request):
        return False

    if not self.notify_new_payload(execution_payload, parent_beacon_block_root):
        return False

    return True
```

#### New `verify_and_notify_new_execution_proof`

```python
def verify_and_notify_new_execution_proof(
    self: ExecutionEngine,
    proof: ExecutionProof,
) -> bool:
    """
    Verify an execution proof and return the payload status.
    """
    assert verify_execution_proof(proof, PROGRAM)

    # Store the valid proof
    new_payload_request_root = proof.zk_proof.public_inputs.new_payload_request_root
    self.execution_proof_store[new_payload_request_root].append(proof)

    # If we have sufficient proofs, we can consider the payload valid
    if len(self.execution_proof_store[new_payload_request_root]) >= MIN_REQUIRED_EXECUTION_PROOFS:
        return True

    # In practice this represents a SYNCING status until sufficient proofs are gathered
    return False
```

## Beacon chain state transition function

### Execution payload processing

#### Modified `process_execution_payload`

```python
def process_execution_payload(
    state: BeaconState,
    # [Modified in EIP-8025]
    # Accept either full envelope or header-only envelope
    signed_envelope: SignedExecutionPayloadEnvelope | SignedExecutionPayloadHeaderEnvelope,
    execution_engine: ExecutionEngine,
    verify: bool = True,
) -> None:
    """
    Process an execution payload envelope or header.
    When a header is provided, validation uses execution proofs.
    """

    ...

    # The rest of the function remains unchanged
```

### Execution proof handlers

#### New `process_signed_execution_proof`

```python
def process_signed_execution_proof(
    state: BeaconState,
    signed_proof: SignedExecutionProof,
    execution_engine: ExecutionEngine,
) -> None:
    """
    Handler for SignedExecutionProof.
    Verifies the signature and calls verify_and_notify_new_execution_proof on the execution engine.
    """
    proof_message = signed_proof.message

    # Verify the builder signature
    builder_index = proof_message.builder_index
    if builder_index == BUILDER_INDEX_SELF_BUILD:
        validator_index = state.latest_block_header.proposer_index
        pubkey = state.validators[validator_index].pubkey
    else:
        pubkey = state.builders[builder_index].pubkey
    signing_root = compute_signing_root(proof_message, get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot)))
    assert bls.Verify(pubkey, signing_root, signed_proof.signature)

    # Verify the execution proof with the execution engine
    is_valid = execution_engine.verify_and_notify_new_execution_proof(proof_message)

    if is_valid:
        # We have verified enough proofs to consider the payload valid
        # Update the state to reflect this
        state.execution_payload_availability[state.slot % SLOTS_PER_HISTORICAL_ROOT] = 0b1
```
