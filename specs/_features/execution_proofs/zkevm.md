# Execution Proofs -- zkEVM

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Public Methods](#public-methods)
- [Custom types](#custom-types)
- [Cryptographic types](#cryptographic-types)
- [Constants](#constants)
- [Preset](#preset)
  - [Proof parameters](#proof-parameters)
- [Helper functions](#helper-functions)
  - [Compilation](#compilation)
    - [`compile_execution_layer`](#compile_execution_layer)
  - [Proof verification](#proof-verification)
    - [`verify_execution_proof_impl`](#verify_execution_proof_impl)
    - [`generate_verification_key`](#generate_verification_key)
  - [Proof generation](#proof-generation)
    - [`generate_execution_proof_impl`](#generate_execution_proof_impl)
    - [`generate_proving_key`](#generate_proving_key)

<!-- mdformat-toc end -->

## Introduction

This document specifies the cryptographic operations for zkEVM based execution proofs that enable stateless validation of execution payloads.

*Note*: This specification provides placeholder implementations. Production implementations should use established zkEVM systems.

## Public Methods

For public API consumers, this document provides the following **public methods**:

- [`verify_zkevm_proof`](#verify_zkevm_proof)
- [`generate_zkevm_proof`](#generate_zkevm_proof)

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `ZKProof` | `Container` | Zero-knowledge proof of execution |

## Cryptographic types

| Name | SSZ equivalent | Description |
| - | - | - |
| `EL_PROGRAM` | `ByteList[32]` | Execution layer program |
| `ProgramBytecode` | `ByteList[64]` | Execution layer program bytecode with proof ID |
| `ProofID` | `uint8` | Identifier for proof system |
| `ProvingKey` | `ByteList[MAX_PROVING_KEY_SIZE]` | Key used for proof generation |
| `VerificationKey` | `ByteList[MAX_VERIFICATION_KEY_SIZE]` | Key used for proof verification |
| `ExecutionWitness` | `ByteList[MAX_WITNESS_SIZE]` | Execution witness data for proof generation |
| `PrivateInput` | `Container` | Private inputs for execution proof generation |
| `PublicInput` | `Container` | Public inputs for execution proof generation and verification |

## Constants

| Name | Value |
| - | - |
| `MAX_PROOF_SIZE` | `307200` (= 300KB) |
| `MAX_PROVING_KEY_SIZE` | `2**28` (= 256MB) | <!-- placeholder value -->
| `MAX_VERIFICATION_KEY_SIZE` | `2**20` (= 1MB) | <!-- placeholder value -->
| `MAX_WITNESS_SIZE` | `314572800` (= 300MB) |
| `MAX_PROOF_SYSTEMS` | `uint64(8)` |

## Preset

### Proof parameters

*Note*: Proof system parameters are determined by the specific zkEVM implementation.

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
    execution_witness: ExecutionWitness
```

### `PublicInput`

```python
class PublicInput(Container):
    block_hash: Hash32
    parent_hash: Hash32
```

## Helper functions

### Compilation

```python
def compile_execution_layer(el_program: EL_PROGRAM, proof_id: ProofID) -> tuple[ProvingKey, VerificationKey]:
    """
    Compile an execution layer program with proof ID to produce proving and verification keys for a specific proof system.

    Note: This function is unsafe. In production, we will use a well-established compiler.

    Args:
        el_program: Execution layer program
        proof_id: Proof system identifier

    Returns:
        Tuple of (proving_key, verification_key) for the EL program and proof system
    """

    # Validate proof system ID
    # Creating proofs is computationally heavy for the builder, so we limit it with `MAX_PROOF_SYSTEMS`
    assert proof_id < MAX_PROOF_SYSTEMS

    # Combine program bytes with proof ID
    combined_data = el_program + proof_id.to_bytes(1, 'little')

    # Create program bytecode (no hashing)
    program_bytecode = ProgramBytecode(combined_data)

    # Generate both keys from the program bytecode
    proving_key = generate_proving_key(program_bytecode, proof_id)
    verification_key = generate_verification_key(program_bytecode, proof_id)

    return (proving_key, verification_key)
```

### Proof verification

#### `verify_execution_proof_impl`

```python
def verify_execution_proof_impl(
    proof: ZKProof,
    verification_key: VerificationKey
) -> bool:
    """
    Verify a zkEVM execution proof using the verification key.

    This is a placeholder implementation. Production systems should use
    established zkEVM verification libraries.
    """
    # Basic validation
    if len(proof.proof_data) > MAX_PROOF_SIZE:
        return False

    # Placeholder verification logic
    # In practice, this would use a zkSNARK verifier with the verification key
    proof_hash = hash(
        proof.proof_data +
        verification_key +
        proof.proof_type.to_bytes(1, 'big') +
        proof.public_inputs.block_hash +
        proof.public_inputs.parent_hash
    )

    # Simple deterministic check (placeholder)
    return proof_hash[0] % 2 == 0
```

#### `generate_verification_key`

```python
def generate_verification_key(program_bytecode: ProgramBytecode, proof_id: ProofID) -> VerificationKey:
    """
    Generate a verification key for the given program bytecode and proof system.

    Args:
        program_bytecode: Execution layer program bytecode
        proof_id: Proof system identifier

    Returns:
        Verification key for verifying proofs
    """
    assert proof_id < MAX_PROOF_SYSTEMS

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
    public_inputs: PublicInput
) -> ZKProof:
    """
    Generate a zkEVM execution proof using the proving key and private inputs.
    """

    proof_data = hash(
        public_inputs.block_hash +
        public_inputs.parent_hash +
        proof_id.to_bytes(1, 'little')
    )

    return ZKProof(
        proof_data=ByteList(proof_data),
        proof_type=proof_id,
        public_inputs=public_inputs
    )
```

#### `compile_execution_layer`

```python
def compile_execution_layer(el_program: EL_PROGRAM, proof_id: ProofID) -> tuple[ProvingKey, VerificationKey]:
    """
    Compile an execution layer program identifier with proof ID to produce proving and verification keys.

    Args:
        el_program: Execution layer program identifier (e.g., "RETH_V1")
        proof_id: Proof system identifier

    Returns:
        Tuple of (proving_key, verification_key) for the EL program and proof system
    """

    assert proof_id < MAX_PROOF_SYSTEMS

    program_bytecode = ProgramBytecode(el_program + proof_id.to_bytes(1, 'little'))

    proving_key = generate_proving_key(program_bytecode, proof_id)
    verification_key = generate_verification_key(program_bytecode, proof_id)

    return (proving_key, verification_key)
```

#### `generate_proving_key`

```python
def generate_proving_key(program_bytecode: ProgramBytecode, proof_id: ProofID) -> ProvingKey:
    """
    Generate a proving key for the given program bytecode and proof system.

    Args:
        program_bytecode: Execution layer program bytecode
        proof_id: Proof system identifier

    Returns:
        Proving key for generating proofs
    """
    assert proof_id < MAX_PROOF_SYSTEMS

    return ProvingKey(program_bytecode)
```

#### `generate_verification_key`

```python
def generate_verification_key(program_bytecode: ProgramBytecode, proof_id: ProofID) -> VerificationKey:
    """
    Generate a verification key for the given program bytecode and proof system.

    Args:
        program_bytecode: Execution layer program bytecode
        proof_id: Proof system identifier

    Returns:
        Verification key for verifying proofs
    """
    assert proof_id < MAX_PROOF_SYSTEMS

    return VerificationKey(program_bytecode)
```

## Public Methods

### `verify_zkevm_proof`

```python
def verify_zkevm_proof(
    zk_proof: ZKProof,
    execution_payload_header: ExecutionPayloadHeader,
    el_program: EL_PROGRAM
) -> bool:
    """
    Public method to verify a zkEVM execution proof against a payload header.

    Args:
        zk_proof: The zkEVM proof to verify
        execution_payload_header: The execution payload header
        el_program: Execution layer program
    """
    # Validate proof system ID
    if zk_proof.proof_type >= MAX_PROOF_SYSTEMS:
        return False

    # Validate that public inputs match the payload header
    if zk_proof.public_inputs.block_hash != execution_payload_header.block_hash:
        return False
    if zk_proof.public_inputs.parent_hash != execution_payload_header.parent_hash:
        return False

    proving_key, verification_key = compile_execution_layer(el_program, zk_proof.proof_type)

    return verify_execution_proof_impl(zk_proof, verification_key)
```

### `generate_zkevm_proof`

```python
def generate_zkevm_proof(
    execution_payload: ExecutionPayload,
    execution_witness: ExecutionWitness,
    el_program: EL_PROGRAM,
    proof_id: ProofID
) -> Optional[ZKProof]:
    """
    Public method to generate an execution proof for a payload.

    Args:
        execution_payload: The execution payload to prove
        execution_witness: Execution witness data containing the pre-state + MPT proofs
        el_program: Execution layer program
        proof_id: Proof system identifier
    """
    # Validate proof system ID
    if proof_id >= MAX_PROOF_SYSTEMS:
        return None

    proving_key, verification_key = compile_execution_layer(el_program, proof_id)

    public_inputs = PublicInput(
        block_hash=execution_payload.block_hash,
        parent_hash=execution_payload.parent_hash
    )

    private_input = PrivateInput(
        execution_payload=execution_payload,
        execution_witness=execution_witness
    )

    return generate_execution_proof_impl(private_input, proving_key, proof_id, public_inputs)
```