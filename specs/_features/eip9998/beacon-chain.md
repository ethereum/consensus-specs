# EIP-9998 -- The Beacon Chain

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Containers](#containers)
  - [Modified `PublicInput`](#modified-publicinput)
  - [Modified `ExecutionProof`](#modified-executionproof)
  - [New `SignedExecutionProof`](#new-signedexecutionproof)
- [Execution proof verification](#execution-proof-verification)
  - [New `verify_signed_execution_proof`](#new-verify_signed_execution_proof)
  - [Modified `process_execution_proof`](#modified-process_execution_proof)

<!-- mdformat-toc end -->

## Introduction

These are the beacon-chain specifications for execution chain proofs. An
execution chain proof attests to valid execution of all payloads in the chain
from the head beacon block to the proof's origin beacon block, and to their
binding to the beacon chain. Execution chain proofs are recursive: each proof
verifies the proof before it.

The public input commits to two beacon block roots: the head, which binds the
proof, and the origin, at which the prover started the recursion. It also
commits to the chain ID and the stateless input schema, which are constants of
the specification.

*Note*: This specification is built upon [EIP-8025](../eip8025/beacon-chain.md).
The recursive guest program is defined in
[guest-program.md](./guest-program.md).

## Containers

### Modified `PublicInput`

```python
class PublicInput(ProgressiveContainer):
    ACTIVE_FIELDS = active_fields(width=4)

    # [New in EIP9998]
    origin_block_root: Root
    # [New in EIP9998]
    head_block_root: Root
    chain_id: Uint64
    schema_id: Uint16
```

*Note*: `new_payload_request_root` and `successful_validation` are removed. An
execution chain proof binds beacon blocks rather than a single payload request,
and it can only be produced for a successful validation.

### Modified `ExecutionProof`

```python
class ExecutionProof(Container):
    proof_data: ProofData
    proof_type: ProofType
    # [Modified in EIP9998]
    # Removed `public_input`
    # [New in EIP9998]
    origin_block_root: Root
    # [New in EIP9998]
    head_block_root: Root
```

`head_block_root` is the root of the beacon block whose payload the proof
proves. `origin_block_root` is the root of the beacon block at which the prover
started the recursion. A proof that starts a recursion has `origin_block_root`
equal to `head_block_root`.

### New `SignedExecutionProof`

```python
class SignedExecutionProof(Container):
    message: ExecutionProof
    validator_index: ValidatorIndex
    signature: BLSSignature
```

## Execution proof verification

### New `verify_signed_execution_proof`

```python
def verify_signed_execution_proof(
    state: BeaconState,
    signed_proof: SignedExecutionProof,
) -> None:
    """
    Verify a signed execution proof against the beacon state.
    The execution proof itself is verified separately by the proof engine.
    """
    proof = signed_proof.message
    assert signed_proof.validator_index < len(state.validators)
    assert len(proof.proof_data) != 0
    assert proof.proof_type in get_supported_proof_types()

    # Verify the prover is an active validator
    validator = state.validators[signed_proof.validator_index]
    assert is_active_validator(validator, get_current_epoch(state))

    # Verify the prover signature
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof, domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_proof.signature)
```

### Modified `process_execution_proof`

```python
def process_execution_proof(
    state: BeaconState,
    # [Modified in EIP9998]
    signed_proof: SignedExecutionProof,
    # [Modified in EIP9998]
    # Removed `payload_envelope`
    proof_engine: ProofEngine,
) -> None:
    """
    Authenticate and verify a signed execution proof.
    """
    # [Modified in EIP9998]
    verify_signed_execution_proof(state, signed_proof)
    # [Modified in EIP9998]
    assert proof_engine.verify_execution_proof(signed_proof.message)
```
