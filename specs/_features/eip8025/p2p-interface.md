# EIP-8025 -- Networking

This document contains the networking specification for Execution Proofs.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Constants](#constants)
- [Containers](#containers)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`execution_proof_{subnet_id}`](#execution_proof_subnet_id)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [ExecutionProofsByHash](#executionproofsbyhash)

<!-- mdformat-toc end -->

## Constants

*Note*: Execution proof subnets use `MAX_EXECUTION_PROOFS_PER_PAYLOAD` (from
[beacon-chain.md](./beacon-chain.md)) to provide 1-to-1 mapping with proof
systems. Each proof system gets its own dedicated subnet.

## Containers

*Note*: Execution proofs are broadcast directly as `SignedExecutionProof`
containers. No additional message wrapper is needed.

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### `execution_proof_{subnet_id}`

Execution proof subnets are used to propagate execution proofs for specific
proof systems.

The execution proof subnet for a given `proof_id` is:

```python
def compute_subnet_for_execution_proof(proof_id: ProofID) -> SubnetID:
    assert proof_id < MAX_EXECUTION_PROOFS_PER_PAYLOAD
    return SubnetID(proof_id)
```

The following validations MUST pass before forwarding the
`signed_execution_proof` on the network:

- _[IGNORE]_ The proof is the first valid proof received for the tuple
  `(signed_execution_proof.message.zk_proof.public_inputs.block_hash, subnet_id)`.
- _[REJECT]_ The `signed_execution_proof.message.validator_index` is within the
  known validator registry.
- _[REJECT]_ The `signed_execution_proof.signature` is valid with respect to the
  validator's public key.
- _[REJECT]_ The `signed_execution_proof.message.zk_proof.proof_data` is
  non-empty.
- _[REJECT]_ The proof system ID matches the subnet:
  `signed_execution_proof.message.zk_proof.proof_type == subnet_id`.
- _[REJECT]_ The execution proof is valid as verified by
  `verify_execution_proof()` with the appropriate parent and block hashes from
  the execution layer.

Subnet topics follow the pattern: `/eth2/execution_proof_{subnet_id}/ssz_snappy`

## The Req/Resp domain

### Messages

#### ExecutionProofsByHash

**Protocol ID:** `/eth2/beacon/req/execution_proofs_by_hash/1/`

The `<context-bytes>` field is calculated as
`context = compute_fork_digest(fork_version, genesis_validators_root)`.

Request Content:

```
(
  Hash32  # block_hash
)
```

Response Content:

```
(
  List[SignedExecutionProof, MAX_EXECUTION_PROOFS_PER_PAYLOAD]
)
```

Requests execution proofs for the given execution payload `block_hash`. The
response MUST contain all available proofs for the requested block hash, up to
`MAX_EXECUTION_PROOFS_PER_PAYLOAD`.

The following validations MUST pass:

- _[REJECT]_ The `block_hash` is a 32-byte value.

The response MUST contain:

- All available execution proofs for the requested block hash
- The response MUST NOT contain more than `MAX_EXECUTION_PROOFS_PER_PAYLOAD`
  proofs
