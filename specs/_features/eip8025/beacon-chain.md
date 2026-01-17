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
  - [Extended containers](#extended-containers)
- [Helpers](#helpers)
  - [Execution proof functions](#execution-proof-functions)
    - [`verify_execution_proof`](#verify_execution_proof)
    - [`verify_execution_proofs`](#verify_execution_proofs)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution payload processing](#execution-payload-processing)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-8025. This enables
stateless validation of execution payloads through cryptographic proofs.

*Note*: This specification is built upon [Fulu](../../fulu/beacon-chain.md).

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
    beacon_root: Root
    zk_proof: ZKEVMProof
    validator_index: ValidatorIndex
```

#### `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
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
    signed_proof: SignedExecutionProof,
    parent_hash: Hash32,
    block_hash: Hash32,
    state: BeaconState,
    el_program: ProgramBytecode,
) -> bool:
    """
    Verify an execution proof against a payload header using zkEVM verification.
    """

    # Note: signed_proof.message.beacon_root verification will be done at a higher level

    # Verify the validator signature
    proof_message = signed_proof.message
    validator = state.validators[proof_message.validator_index]
    signing_root = compute_signing_root(proof_message, get_domain(state, DOMAIN_EXECUTION_PROOF))
    if not bls.Verify(validator.pubkey, signing_root, signed_proof.signature):
        return False

    # Derive program bytecode from the EL program identifier and proof type
    program_bytecode = ProgramBytecode(
        el_program + proof_message.zk_proof.proof_type.to_bytes(1, "little")
    )

    return verify_zkevm_proof(proof_message.zk_proof, parent_hash, block_hash, program_bytecode)
```

#### `verify_execution_proofs`

```python
def verify_execution_proofs(parent_hash: Hash32, block_hash: Hash32, state: BeaconState) -> bool:
    """
    Verify that execution proofs are available and valid for an execution payload.
    """
    # `retrieve_execution_proofs` is implementation and context dependent.
    # It returns all execution proofs for the given payload block hash.
    signed_execution_proofs = retrieve_execution_proofs(block_hash)

    # Verify there are sufficient proofs
    if len(signed_execution_proofs) < MIN_REQUIRED_EXECUTION_PROOFS:
        return False

    # Verify all execution proofs
    for signed_proof in signed_execution_proofs:
        if not verify_execution_proof(signed_proof, parent_hash, block_hash, state, PROGRAM):
            return False

    return True
```

## Beacon chain state transition function

### Execution payload processing

#### Modified `process_execution_payload`

```python
def process_execution_payload(
    state: BeaconState,
    body: BeaconBlockBody,
    execution_engine: ExecutionEngine,
    stateless_validation: bool = False,
) -> None:
    """
    Note: This function is modified to support optional stateless validation with execution proofs.
    """
    payload = body.execution_payload

    # Verify consistency of the parent hash with respect to the previous execution payload header
    assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_time_at_slot(state, state.slot)
    # Verify commitments are under limit
    assert (
        len(body.blob_kzg_commitments)
        <= get_blob_parameters(get_current_epoch(state)).max_blobs_per_block
    )

    if stateless_validation:
        # Stateless validation using execution proofs
        assert verify_execution_proofs(payload.parent_hash, payload.block_hash, state)
    else:
        # Compute list of versioned hashes
        versioned_hashes = [
            kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments
        ]

        # Verify the execution payload is valid
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
