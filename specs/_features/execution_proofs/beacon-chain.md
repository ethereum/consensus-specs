# Execution Proofs -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=1 -->

- [Execution Proofs -- The Beacon Chain](#execution-proofs----the-beacon-chain)
  - [Table of contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Constants](#constants)
    - [Execution](#execution)
  - [Configuration](#configuration)
  - [Containers](#containers)
    - [New containers](#new-containers)
      - [`ExecutionProof`](#executionproof)
      - [`SignedExecutionProof`](#signedexecutionproof)
    - [Extended Containers](#extended-containers)
  - [Helper functions](#helper-functions)
    - [Execution proof functions](#execution-proof-functions)
      - [`get_el_program`](#get_el_program)
      - [`verify_execution_proof`](#verify_execution_proof)
      - [`verify_execution_proofs`](#verify_execution_proofs)
  - [Beacon chain state transition function](#beacon-chain-state-transition-function)
    - [Execution payload processing](#execution-payload-processing)
      - [Modified `process_execution_payload`](#modified-process_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus specs for Execution Proofs. This enables stateless validation of execution payloads through cryptographic proofs.

*Note*: This specification assumes the reader is familiar with the [zkEVM cryptographic operations](./zkevm.md).

## Constants

### Execution

| Name                                    | Value             |
| --------------------------------------- | ----------------- |
| `MAX_EXECUTION_PROOFS_PER_PAYLOAD`     | `uint64(8)`       |
| `RETH_EL_PROGRAM`                      | `EL_PROGRAM(b"RETH_V1" + b"\x00" * 25)` |
| `GETH_EL_PROGRAM`                      | `EL_PROGRAM(b"GETH_V1" + b"\x00" * 25)` |
| `NETHERMIND_EL_PROGRAM`                | `EL_PROGRAM(b"NETHERMIND_V1" + b"\x00" * 20)` |
| `BESU_EL_PROGRAM`                      | `EL_PROGRAM(b"BESU_V1" + b"\x00" * 25)` |

## Configuration

*Note*: The configuration values are not definitive.

| Name                             | Value                           |
| -------------------------------- | ------------------------------- |
| `MIN_REQUIRED_EXECUTION_PROOFS`  | `uint64(1)`                     |

## Containers

### New containers

#### `ExecutionProof`

```python
class ExecutionProof(Container):
    beacon_root: Root
    zk_proof: ZKProof
    validator_index: ValidatorIndex
```

#### `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
    signature: BLSSignature
```

### Extended Containers

*Note*: `BeaconState` and `BeaconBlockBody` remain the same as Fulu. No modifications are required for execution proofs since they are handled externally.

## Helper functions

### Execution proof functions

#### `get_el_program`

```python
def get_el_program(proof_id: ProofID) -> EL_PROGRAM:
    """
    Get the EL program for a given proof system ID.
    """
    if proof_id == ProofID(0):
        return RETH_EL_PROGRAM
    elif proof_id == ProofID(1):
        return GETH_EL_PROGRAM
    elif proof_id == ProofID(2):
        return NETHERMIND_EL_PROGRAM
    elif proof_id == ProofID(3):
        return BESU_EL_PROGRAM

    assert proof_id < ProofID(4)
```

#### `verify_execution_proof`

```python
def verify_execution_proof(proof: ExecutionProof, parent_hash: Hash32, block_hash: Hash32, state: BeaconState, el_program: EL_PROGRAM) -> bool:
    """
    Verify an execution proof against a payload header using zkEVM verification.
    """

    # Note: proof.beacon_root verification would be done at a higher level

    # Verify the validator signature
    validator = state.validators[proof.validator_index]
    signing_root = compute_signing_root(proof, get_domain(state, DOMAIN_EXECUTION_PROOF))
    if not bls.Verify(validator.pubkey, signing_root, proof.signature):
        return False

    return verify_zkevm_proof(proof.zk_proof, parent_hash, block_hash, el_program)
```

#### `verify_execution_proofs`

```python
def verify_execution_proofs(parent_hash: Hash32, block_hash: Hash32, state: BeaconState) -> bool:
    """
    Verify that execution proofs are available and valid for an execution payload.
    """
    # `retrieve_execution_proofs` is implementation and context dependent
    # It returns all the execution proofs for the given payload block hash
    execution_proofs = retrieve_execution_proofs(block_hash)

    # Verify we have sufficient proofs
    if len(execution_proofs) < MIN_REQUIRED_EXECUTION_PROOFS:
        return False

    # Verify all execution proofs
    for proof in execution_proofs:
        # Get EL program from proof system ID
        # TODO: The proof system ID is really an ID for a proof system and EL combination
        el_program = get_el_program(proof.zk_proof.proof_type)
        if not verify_execution_proof(proof, parent_hash, block_hash, state, el_program):
            return False

    return True
```

## Beacon chain state transition function

### Execution payload processing

#### Modified `process_execution_payload`

```python
def process_execution_payload(
    state: BeaconState, body: BeaconBlockBody, execution_engine: ExecutionEngine, stateless_validation: bool = False
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
        # Traditional validation - execute the payload
        versioned_hashes = [
            kzg_commitment_to_versioned_hash(commitment) for commitment in body.blob_kzg_commitments
        ]
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