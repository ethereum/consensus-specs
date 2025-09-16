# Execution Proofs -- zkEVM

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Custom types](#custom-types)
- [Cryptographic types](#cryptographic-types)
- [Preset](#preset)
  - [Proof parameters](#proof-parameters)
- [Containers](#containers)
  - [`ZKProof`](#zkproof)
  - [`PrivateInput`](#privateinput)
  - [`PublicInput`](#publicinput)
- [Helper functions](#helper-functions)
  - [Compilation](#compilation)
    - [`compile_execution_layer`](#compile_execution_layer)
  - [Proof verification](#proof-verification)
    - [`verify_execution_proof_impl`](#verify_execution_proof_impl)
    - [`generate_verification_key`](#generate_verification_key)
  - [Proof generation](#proof-generation)
    - [`generate_execution_proof_impl`](#generate_execution_proof_impl)
    - [`generate_proving_key`](#generate_proving_key)
  - [`verify_zkevm_proof`](#verify_zkevm_proof)
  - [`generate_zkevm_proof`](#generate_zkevm_proof)

<!-- mdformat-toc end -->

## Introduction

This document specifies the cryptographic operations for zkEVM based execution
proofs that enable stateless validation of execution payloads.

*Note*: This specification provides placeholder implementations. Production
implementations should use established zkEVM systems.

## Constants

| Name                        | Value                  |
| --------------------------- | ---------------------- |
| `MAX_PROOF_SIZE`            | `307200` (= 300KiB)    |
| `MAX_PROVING_KEY_SIZE`      | `2**28` (= 256MiB)     |
| `MAX_VERIFICATION_KEY_SIZE` | `2**20` (= 1MiB)       |
| `MAX_WITNESS_SIZE`          | `314572800` (= 300MiB) |

## Custom types

| Name      | SSZ equivalent | Description                       |
| --------- | -------------- | --------------------------------- |
| `ZKProof` | `Container`    | Zero-knowledge proof of execution |

## Cryptographic types

| Name                 | SSZ equivalent                        | Description                                                   |
| -------------------- | ------------------------------------- | ------------------------------------------------------------- |
| `ProgramBytecode`    | `ByteList[64]`                        | Execution layer program bytecode with proof ID                |
| `ProofID`            | `uint8`                               | Identifier for proof system                                   |
| `ProvingKey`         | `ByteList[MAX_PROVING_KEY_SIZE]`      | Key used for proof generation                                 |
| `VerificationKey`    | `ByteList[MAX_VERIFICATION_KEY_SIZE]` | Key used for proof verification                               |
| `ZKExecutionWitness` | `ByteList[MAX_WITNESS_SIZE]`          | zkEVM execution witness data for proof generation             |
| `PrivateInput`       | `Container`                           | Private inputs for execution proof generation                 |
| `PublicInput`        | `Container`                           | Public inputs for execution proof generation and verification |

## Preset

### Proof parameters

*Note*: Proof system parameters are determined by the specific zkEVM
implementation.

## Containers

### `ZKProof`

```python
class ZKProof(Container):
    proof_data: ByteList[MAX_PROOF_SIZE]
    proof_type: ProofID
    public_inputs: PublicInput
```

### `PrivateInput`

```python
class PrivateInput(Container):
    execution_payload: ExecutionPayload
    execution_witness: ZKExecutionWitness
```

### `PublicInput`

```python
class PublicInput(Container):
    block_hash: Hash32
    parent_hash: Hash32
```

## Helper functions

### Compilation

#### `compile_execution_layer`

```python
def compile_execution_layer(
    program_bytecode: ProgramBytecode, proof_id: ProofID
) -> tuple[ProvingKey, VerificationKey]:
    """
    Compile an execution layer program with proof ID to produce proving and verification keys for a specific proof system.

    Note: This function is unsafe. In production, we will use a well-established compiler.
    """

    proving_key = generate_proving_key(program_bytecode, proof_id)
    verification_key = generate_verification_key(program_bytecode, proof_id)

    return (proving_key, verification_key)
```

### Proof verification

#### `verify_execution_proof_impl`

```python
def verify_execution_proof_impl(proof: ZKProof, verification_key: VerificationKey) -> bool:
    """
    Verify a zkEVM execution proof using the verification key.

    This is a placeholder implementation. Production systems should use
    established zkEVM verification libraries.
    """
    # Basic validation
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

    verification_key = VerificationKey(program_bytecode)

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
) -> ZKProof:
    """
    Generate a zkEVM execution proof using the proving key, private inputs and public inputs
    """

    proof_data = hash(
        public_inputs.block_hash + public_inputs.parent_hash + proof_id.to_bytes(1, "little")
    )

    return ZKProof(
        proof_data=ByteList(proof_data), proof_type=proof_id, public_inputs=public_inputs
    )
```

#### `generate_proving_key`

```python
def generate_proving_key(program_bytecode: ProgramBytecode, proof_id: ProofID) -> ProvingKey:
    """
    Generate a proving key for the given program bytecode and proof system.
    """

    return ProvingKey(program_bytecode)
```

### `verify_zkevm_proof`

```python
def verify_zkevm_proof(
    zk_proof: ZKProof, parent_hash: Hash32, block_hash: Hash32, program_bytecode: ProgramBytecode
) -> bool:
    """
    Public method to verify a zkEVM execution proof against block hashes.
    """

    # Validate that public inputs match the provided parent and current block hash
    if zk_proof.public_inputs.block_hash != block_hash:
        return False
    if zk_proof.public_inputs.parent_hash != parent_hash:
        return False

    proving_key, verification_key = compile_execution_layer(program_bytecode, zk_proof.proof_type)

    return verify_execution_proof_impl(zk_proof, verification_key)
```

### `generate_zkevm_proof`

```python
def generate_zkevm_proof(
    execution_payload: ExecutionPayload,
    execution_witness: ZKExecutionWitness,
    program_bytecode: ProgramBytecode,
    proof_id: ProofID,
) -> Optional[ZKProof]:
    """
    Public method to generate an execution proof for a payload.
    """

    proving_key, verification_key = compile_execution_layer(program_bytecode, proof_id)

    public_inputs = PublicInput(
        block_hash=execution_payload.block_hash, parent_hash=execution_payload.parent_hash
    )

    private_input = PrivateInput(
        execution_payload=execution_payload, execution_witness=execution_witness
    )

    return generate_execution_proof_impl(private_input, proving_key, proof_id, public_inputs)
```
