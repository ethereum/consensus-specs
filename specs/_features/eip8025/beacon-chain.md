# EIP-8025 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Types](#types)
- [Constants](#constants)
  - [Execution](#execution)
  - [Domains](#domains)
- [Containers](#containers)
  - [New `ExecutionPayloadHeader`](#new-executionpayloadheader)
  - [New `BeaconBlockExecutionBinding`](#new-beaconblockexecutionbinding)
  - [New `NewPayloadRequestHeader`](#new-newpayloadrequestheader)
  - [New `PublicInput`](#new-publicinput)
  - [New `ExecutionProof`](#new-executionproof)
  - [New `SignedExecutionProof`](#new-signedexecutionproof)
  - [New `BeaconChainProofPublicInput`](#new-beaconchainproofpublicinput)
  - [New `BeaconChainProof`](#new-beaconchainproof)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Execution proof](#execution-proof)
    - [New `process_execution_proof`](#new-process_execution_proof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications to add EIP-8025, enabling stateless
validation of execution payloads through execution proofs.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md)
and imports proof types from [proof-engine.md](./proof-engine.md).

## Types

| Name        | SSZ equivalent | Description                       |
| ----------- | -------------- | --------------------------------- |
| `ProofType` | `Uint8`        | The type identifier for the proof |

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name             | Value                                  |
| ---------------- | -------------------------------------- |
| `MAX_PROOF_SIZE` | `Uint64(4194304)` (= 4,096 KiB, 4 MiB) |

### Domains

| Name                     | Value                      |
| ------------------------ | -------------------------- |
| `DOMAIN_EXECUTION_PROOF` | `DomainType('0x0F000000')` |

## Containers

### New `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    block_hash: Hash32
    transactions_root: Root
    withdrawals_root: Root
    blob_gas_used: uint64
    excess_blob_gas: uint64
    block_access_list_root: Root
    slot_number: uint64
```

`ExecutionPayloadHeader` is the execution payload header committed by a
`NewPayloadRequestHeader`. It contains `transactions_root` rather than the
transaction list, allowing proof sync to bind the execution payload without
opening transaction data in the recursive guest.

### New `BeaconBlockExecutionBinding`

```python
class BeaconBlockExecutionBinding(Container):
    beacon_header: BeaconBlockHeader
    execution_payload_header: ExecutionPayloadHeader
    signed_execution_payload_bid: SignedExecutionPayloadBid
```

`BeaconBlockExecutionBinding` is the compact proof-sync projection used to bind
a beacon block to execution proof inputs. It contains the canonical
`BeaconBlockHeader`, the execution-payload header, and the signed payload bid
without opening the full beacon block body.

### New `NewPayloadRequestHeader`

```python
class NewPayloadRequestHeader(Container):
    execution_payload_header: ExecutionPayloadHeader
    versioned_hashes: List[VersionedHash, MAX_BLOB_COMMITMENTS_PER_BLOCK]
    parent_beacon_block_root: Root
    execution_requests_root: Root
```

`NewPayloadRequestHeader` is the public commitment used by execution proofs. It
commits to the header of a `NewPayloadRequest` without requiring callers to
expose the full execution payload or execution requests.

### New `PublicInput`

```python
class PublicInput(Container):
    new_payload_request_root: Root
```

### New `ExecutionProof`

```python
class ExecutionProof(Container):
    proof_data: ProgressiveByteList
    proof_type: ProofType
    public_input: PublicInput
```

### New `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
    validator_index: ValidatorIndex
    signature: BLSSignature
```

### New `BeaconChainProofPublicInput`

```python
class BeaconChainProofPublicInput(Container):
    ws_checkpoint_root: Root
    ws_checkpoint_slot: Slot
    head_root: Root
    head_slot: Slot
```

### New `BeaconChainProof`

```python
class BeaconChainProof(Container):
    proof_data: ByteList[MAX_PROOF_SIZE]
    proof_type: ProofType
    public_input: BeaconChainProofPublicInput
```

Each `BeaconChainProof` is for a single `proof_type`. Clients that require
multiple proof types verify one `BeaconChainProof` per required type.

## Beacon chain state transition function

### Execution proof

*Note*: Proof storage is implementation-dependent, managed by the `ProofEngine`.

#### New `process_execution_proof`

```python
def process_execution_proof(
    state: BeaconState,
    signed_proof: SignedExecutionProof,
    proof_engine: ProofEngine,
) -> None:
    proof_message = signed_proof.message
    assert len(proof_message.proof_data) <= MAX_PROOF_SIZE

    # Verify prover is an active validator
    validator = state.validators[signed_proof.validator_index]
    assert is_active_validator(validator, get_current_epoch(state))

    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof_message, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_proof.signature)

    # Verify the execution proof
    assert proof_engine.verify_execution_proof(proof_message)
```
