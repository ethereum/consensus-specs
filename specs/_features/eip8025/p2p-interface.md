# EIP-8025 -- Networking

This document contains the networking specifications for EIP-8025.

*Note*: This specification is built upon [Gloas](../../gloas/p2p-interface.md).

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Constants](#constants)
- [Containers](#containers)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`signed_execution_payload_envelope_header`](#signed_execution_payload_envelope_header)
      - [`execution_proof_{subnet_id}`](#execution_proof_subnet_id)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [ExecutionProofsByRoot](#executionproofsbyroot)

<!-- mdformat-toc end -->

## Constants

*Note*: There are `MAX_EXECUTION_PROOFS_PER_PAYLOAD` (from
[beacon-chain.md](./beacon-chain.md)) execution proof subnets to provide 1-to-1
mapping with proof systems. Each proof system gets its own dedicated subnet.

## Containers

*Note*: Execution proofs are broadcast as `SignedExecutionProof` containers. No
additional message wrapper is needed.

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### `signed_execution_payload_envelope_header`

This topic is used to propagate `SignedExecutionPayloadHeaderEnvelope` messages.
ZK attesters subscribe to this topic to receive execution payload headers for
which they can generate execution proofs.

The following validations MUST pass before forwarding the
`signed_execution_payload_envelope_header` on the network:

- _[IGNORE]_ The header is the first valid header received for the tuple
  `(signed_execution_payload_envelope_header.message.beacon_block_root, signed_execution_payload_envelope_header.message.slot)`.
- _[REJECT]_ The
  `signed_execution_payload_envelope_header.message.beacon_block_root` refers to
  a known beacon block.
- _[REJECT]_ The
  `signed_execution_payload_envelope_header.message.builder_index` is within the
  known builder registry.
- _[REJECT]_ The `signed_execution_payload_envelope_header.signature` is valid
  with respect to the builder's public key.
- _[REJECT]_ The `signed_execution_payload_envelope_header.message.slot` matches
  the slot of the referenced beacon block.

##### `execution_proof_{subnet_id}`

Execution proof subnets are used to propagate execution proofs for specific
proof systems. `SignedExecutionProof` messages from both builders and provers
are propagated on these subnets.

The execution proof subnet for a given `proof_id` is:

```python
def compute_subnet_for_execution_proof(proof_id: ProofID) -> SubnetID:
    assert proof_id < MAX_EXECUTION_PROOFS_PER_PAYLOAD
    return SubnetID(proof_id)
```

The following validations MUST pass before forwarding a `signed_execution_proof`
on the network:

- _[IGNORE]_ The proof is the first valid proof received for the tuple
  `(signed_execution_proof.message.public_inputs.new_payload_request_root, subnet_id)`.
- _[REJECT]_ If `signed_execution_proof.prover_id` is a `BuilderIndex`: the
  index is within the known builder registry.
- _[REJECT]_ If `signed_execution_proof.prover_id` is a `BLSPubkey`: the pubkey
  is in `WHITELISTED_PROVERS`.
- _[REJECT]_ The `signed_execution_proof.signature` is valid with respect to the
  prover's public key.
- _[REJECT]_ The `signed_execution_proof.message.proof_data` is non-empty.
- _[REJECT]_ The proof system ID matches the subnet:
  `signed_execution_proof.message.proof_type == subnet_id`.
- _[REJECT]_ The execution proof is valid as verified by
  `process_signed_execution_proof()`.

## The Req/Resp domain

### Messages

#### ExecutionProofsByRoot

**Protocol ID:** `/eth2/beacon/req/execution_proofs_by_root/1/`

The `<context-bytes>` field is calculated as
`context = compute_fork_digest(fork_version, genesis_validators_root)`.

Request Content:

```
(
  Root  # new_payload_request_root
)
```

Response Content:

```
(
  List[SignedExecutionProof, MAX_EXECUTION_PROOFS_PER_PAYLOAD]
)
```

Requests execution proofs for the given `new_payload_request_root`. The response
MUST contain all available proofs for the requested root, up to
`MAX_EXECUTION_PROOFS_PER_PAYLOAD`.

The following validations MUST pass:

- _[REJECT]_ The `new_payload_request_root` is a 32-byte value.

The response MUST contain:

- All available execution proofs for the requested `new_payload_request_root`.
- The response MUST NOT contain more than `MAX_EXECUTION_PROOFS_PER_PAYLOAD`
  proofs.
