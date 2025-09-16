# Execution Proofs -- Validator

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=1 -->

- [Execution Proofs -- Validator](#execution-proofs----validator)
  - [Table of contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Optional execution proof generation](#optional-execution-proof-generation)
    - [`generate_execution_proof`](#generate_execution_proof)
    - [`broadcast_execution_proof`](#broadcast_execution_proof)

<!-- mdformat-toc end -->

## Introduction

This document represents optional execution proof generation capabilities that validators may choose to implement.

## Prerequisites

This document is an extension of the [Fulu -- Validator](../../fulu/validator.md) guide.

## Configuration

| Name                                    | Value             |
| --------------------------------------- | ----------------- |
| `EXECUTION_PROOF_GENERATION_ENABLED`   | `False`           |

## Optional execution proof generation

Validators MAY choose to generate execution proofs for payloads they propose or receive.

### `generate_execution_proof`

```python
def generate_execution_proof(payload: ExecutionPayload, execution_witness: ZKExecutionWitness, proof_id: ProofID) -> Optional[SignedExecutionProof]:
    """
    Generate an execution proof for the given payload
    """
    if not EXECUTION_PROOF_GENERATION_ENABLED:
        return None

    zk_proof = generate_zkevm_proof(payload, execution_witness, PROGRAM, proof_id)

    if zk_proof is None:
        return None

    validator_index = get_validator_index()
    beacon_root = get_current_beacon_root()

    execution_proof_message = ExecutionProof(
        beacon_root=beacon_root,
        zk_proof=zk_proof,
        validator_index=validator_index,
    )

    signing_root = compute_signing_root(execution_proof_message, get_domain(get_current_state(), DOMAIN_EXECUTION_PROOF))
    signature = bls.Sign(get_validator_private_key(), signing_root)

    return SignedExecutionProof(
        message=execution_proof_message,
        signature=signature,
    )
```

### `broadcast_execution_proof`

```python
def broadcast_execution_proof(signed_proof: SignedExecutionProof) -> None:
    """
    Broadcast an execution proof to the network.
    """
    # Broadcast on the appropriate subnet based on proof system
    subnet_id = compute_subnet_for_execution_proof(signed_proof.message.zk_proof.proof_type)
    topic = f"execution_proof_{subnet_id}"

    broadcast_to_topic(topic, signed_proof)
```
