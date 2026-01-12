# EIP-8025 -- zkEVM

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Types](#types)
- [Cryptographic types](#cryptographic-types)
- [Containers](#containers)
  - [`ExecutionProof`](#zkevmproof)
  - [`PrivateInput`](#privateinput)
  - [`PublicInput`](#publicinput)
- [Helpers](#helpers)
  - [Preprocessing](#preprocessing)
    - [`generate_keys`](#generate_keys)
  - [Proof verification](#proof-verification)
    - [`verify_execution_proof_impl`](#verify_execution_proof_impl)
    - [`generate_verification_key`](#generate_verification_key)
  - [Proof generation](#proof-generation)
    - [`generate_execution_proof_impl`](#generate_execution_proof_impl)
    - [`generate_proving_key`](#generate_proving_key)
  - [`verify_execution_proof`](#verify_execution_proof)
  - [`generate_execution_proof`](#generate_execution_proof)

<!-- mdformat-toc end -->

## Introduction

This document specifies the cryptographic operations for zkEVM based execution
proofs enabling stateless validation of execution payloads.

*Note*: This specification provides placeholder implementations. Production
implementations should use established zkEVM systems.

## Constants

All of the constants below are subject to change and one should not overindex on
them. `MAX_PROOF_SIZE`, `MAX_PROVING_KEY_SIZE`, and `MAX_VERIFICATION_KEY_SIZE`
are all arbitrary. `MAX_WITNESS_SIZE` is the worst case witness size for the MPT
for a payload with a maximum gas limit of 30M gas.

| Name                        | Value                  |
| --------------------------- | ---------------------- |
| `MAX_PROOF_SIZE`            | `307200` (= 300KiB)    |
| `MAX_PROVING_KEY_SIZE`      | `2**28` (= 256MiB)     |
| `MAX_VERIFICATION_KEY_SIZE` | `2**20` (= 1MiB)       |
| `MAX_WITNESS_SIZE`          | `314572800` (= 300MiB) |

## Types

| Name         | SSZ equivalent | Description                     |
| ------------ | -------------- | ------------------------------- |
| `ExecutionProof` | `Container`    | Proof of execution of a program |

## Cryptographic types

*Note*: `ProgramBytecode` represents the bytecode for a particular execution
layer client. The size depends on the client; `16` is a placeholder.

| Name                 | SSZ equivalent                        | Description                                                   |
| -------------------- | ------------------------------------- | ------------------------------------------------------------- |
| `ProgramBytecode`    | `ByteList[16]`                        | Execution-layer program bytecode                              |
| `ProofID`            | `uint8`                               | Identifier for proof system                                   |
| `ProvingKey`         | `ByteList[MAX_PROVING_KEY_SIZE]`      | Key used for proof generation                                 |
| `VerificationKey`    | `ByteList[MAX_VERIFICATION_KEY_SIZE]` | Key used for proof verification                               |
| `ZKExecutionWitness` | `ByteList[MAX_WITNESS_SIZE]`          | zkEVM execution witness data for stateless program execution  |
| `PrivateInput`       | `Container`                           | Private inputs for execution proof generation                 |
| `PublicInput`        | `Container`                           | Public inputs for execution proof generation and verification |

## Containers

### `ExecutionProof`

```python
class ExecutionProof(Container):
    proof_data: ByteList[MAX_PROOF_SIZE]
    proof_type: ProofID
    public_inputs: PublicInput
```

### `PrivateInput`

```python
class PrivateInput(Container):
    new_payload_request: NewPayloadRequest
    execution_witness: ZKExecutionWitness
```

### `PublicInput`

```python
class PublicInput(Container):
    new_payload_request_root: Root  # hash_tree_root(NewPayloadRequest)
```

## Helpers

### Preprocessing

#### `generate_keys`

```python
def generate_keys(
    program_bytecode: ProgramBytecode, proof_id: ProofID
) -> tuple[ProvingKey, VerificationKey]:
    """
    Generate proving and verification keys for the given program bytecode and proof system.
    """
    proving_key = generate_proving_key(program_bytecode, proof_id)
    verification_key = generate_verification_key(program_bytecode, proof_id)

    return (proving_key, verification_key)
```

### Proof verification

#### `verify_execution_proof_impl`

```python
def verify_execution_proof_impl(proof: ExecutionProof, verification_key: VerificationKey) -> bool:
    """
    Verify a zkEVM execution proof using the verification key.
    """
    if len(proof.proof_data) > MAX_PROOF_SIZE:
        return False

    return True
```

#### `generate_verification_key`

```python
def generate_verification_key(
    program_bytecode: ProgramBytecode, proof_id: ProofID
) -> VerificationKey:
    """
    Generate a verification key for the given program bytecode and proof system.
    """
    verification_key = VerificationKey(program_bytecode + proof_id.to_bytes(1, "little"))
    return verification_key
```

### Proof generation

#### `generate_execution_proof_impl`

```python
def generate_execution_proof_impl(
    private_input: PrivateInput,
    proving_key: ProvingKey,
    proof_id: ProofID,
    public_inputs: PublicInput,
) -> ExecutionProof:
    """
    Generate a zkEVM execution proof using the proving key, private inputs and public inputs.
    """
    proof_data = hash(
        public_inputs.new_payload_request_root + proof_id.to_bytes(1, "little")
    )

    return ExecutionProof(
        proof_data=ByteList(proof_data), proof_type=proof_id, public_inputs=public_inputs
    )
```

#### `generate_proving_key`

```python
def generate_proving_key(program_bytecode: ProgramBytecode, proof_id: ProofID) -> ProvingKey:
    """
    Generate a proving key for the given program bytecode and proof system.
    """
    return ProvingKey(program_bytecode + proof_id.to_bytes(1, "little"))
```

### `verify_execution_proof`

```python
def verify_execution_proof(
    proof: ExecutionProof,
    program_bytecode: ProgramBytecode,
) -> bool:
    """
    Public method to verify an execution proof against NewPayloadRequest root.
    """
    _, verification_key = generate_keys(program_bytecode, proof.proof_type)

    return verify_execution_proof_impl(proof, verification_key)
```

### `generate_execution_proof`

```python
def generate_execution_proof(
    new_payload_request: NewPayloadRequest,
    execution_witness: ZKExecutionWitness,
    program_bytecode: ProgramBytecode,
    proof_id: ProofID,
) -> ExecutionProof:
    """
    Public method to generate an execution proof for a NewPayloadRequest.
    """
    proving_key, _ = generate_keys(program_bytecode, proof_id)

    public_inputs = PublicInput(
        new_payload_request_root=hash_tree_root(new_payload_request)
    )
    private_input = PrivateInput(
        new_payload_request=new_payload_request, execution_witness=execution_witness
    )

    return generate_execution_proof_impl(private_input, proving_key, proof_id, public_inputs)
```
