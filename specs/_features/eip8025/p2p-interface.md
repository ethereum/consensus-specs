# EIP-8025 -- Networking

This document contains the networking specifications for EIP-8025.

*Note*: This specification is built upon [Fulu](../../fulu/p2p-interface.md) and
imports proof types from [proof-engine.md](./proof-engine.md).

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Constants](#constants)
  - [Execution](#execution)
- [Containers](#containers)
  - [`ProofByRootIdentifier`](#proofbyrootidentifier)
- [Helpers](#helpers)
  - [New `compute_max_request_execution_proofs`](#new-compute_max_request_execution_proofs)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`execution_proof`](#execution_proof)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [ExecutionProofsByRange](#executionproofsbyrange)
    - [ExecutionProofsByRoot](#executionproofsbyroot)
    - [ExecutionProofStatus](#executionproofstatus)
- [The discovery domain: discv5](#the-discovery-domain-discv5)
  - [ENR structure](#enr-structure)
    - [Execution proof awareness](#execution-proof-awareness)

<!-- mdformat-toc end -->

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name                               | Value       |
| ---------------------------------- | ----------- |
| `MAX_EXECUTION_PROOFS_PER_PAYLOAD` | `uint64(4)` |

## Containers

### `ProofByRootIdentifier`

```python
class ProofByRootIdentifier(Container):
    block_root: Root
    proof_types: List[ProofType, MAX_EXECUTION_PROOFS_PER_PAYLOAD]
```

## Helpers

### New `compute_max_request_execution_proofs`

```python
def compute_max_request_execution_proofs() -> uint64:
    """
    Return the maximum number of execution proofs in a single request.
    """
    return uint64(MAX_REQUEST_BLOCKS_DENEB * MAX_EXECUTION_PROOFS_PER_PAYLOAD)
```

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### `execution_proof`

This topic is used to propagate `SignedExecutionProof` messages.

The following validations MUST pass before forwarding the
`signed_execution_proof` on the network, assuming the alias
`proof = signed_execution_proof.message`:

- _[IGNORE]_ The proof has not already been processed -- i.e.
  `hash_tree_root(proof)` has not been seen before.
- _[IGNORE]_ The proof's corresponding new payload request (identified by
  `proof.public_input.new_payload_request_root`) has been seen (via gossip or
  non-gossip sources) (a client MAY queue proofs for processing once the new
  payload request is retrieved).
- _[IGNORE]_ No *valid* proof has already been received for the tuple
  `(proof.public_input.new_payload_request_root, proof.proof_type)` -- i.e. no
  *valid* proof for `proof.proof_type` from any prover has been received.
- _[IGNORE]_ The proof is the first proof received for the tuple
  `(proof.public_input.new_payload_request_root, proof.proof_type, signed_execution_proof.validator_index)`
  -- i.e. the first *valid or invalid* proof for `proof.proof_type` from
  `signed_execution_proof.validator_index`.
- _[IGNORE]_ The validator has not previously sent an invalid proof -- i.e. no
  *invalid* proof from `signed_execution_proof.validator_index` has been
  received.
- _[REJECT]_ The validator with index `signed_execution_proof.validator_index`
  is an active validator -- i.e.
  `is_active_validator(state.validators[signed_execution_proof.validator_index], get_current_epoch(state))`
  returns `True`.
- _[REJECT]_ `signed_execution_proof.signature` is valid with respect to the
  validator's public key.
- _[REJECT]_ `proof.proof_data` is non-empty.
- _[REJECT]_ `proof.proof_data` is not larger than `MAX_PROOF_SIZE`.
- _[REJECT]_ All of the conditions within `process_execution_proof` pass
  validation.
- _[IGNORE]_ No *valid* proof has already been received for the tuple
  `(proof.public_input.new_payload_request_root, proof.proof_type)` -- i.e. no
  *valid* proof for `proof.proof_type` from any prover has been received.

## The Req/Resp domain

### Messages

#### ExecutionProofsByRange

**Protocol ID:** `/eth2/beacon_chain/req/execution_proofs_by_range/1/`

Request Content:

```
(
  start_slot: Slot
  count: uint64
  proof_types: List[ProofType, MAX_EXECUTION_PROOFS_PER_PAYLOAD]
)
```

Response Content:

```
(
  List[SignedExecutionProof, compute_max_request_execution_proofs()]
)
```

Requests execution proofs for a contiguous range of slots, filtered by proof
type. The responding peer iterates through beacon blocks in the range
`[start_slot, start_slot + count)` and returns `SignedExecutionProof` entries
whose `proof_type` is in the requested `proof_types` list. If `proof_types` is
empty, all known proof types are returned for each block in the range.

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `SignedExecutionProof` payload.

Clients MUST keep the total number of requested proofs under
`compute_max_request_execution_proofs()`. Since each slot may contain up to
`MAX_EXECUTION_PROOFS_PER_PAYLOAD` proofs, the `count` field MUST satisfy
`count * MAX_EXECUTION_PROOFS_PER_PAYLOAD <= compute_max_request_execution_proofs()`.

Clients MUST respond with at least one proof, if they have it. Clients MAY limit
the number of proofs in the response.

Clients SHOULD return proofs in slot-ascending order within the requested range.

#### ExecutionProofsByRoot

**Protocol ID:** `/eth2/beacon_chain/req/execution_proofs_by_root/1/`

Request Content:

```
(
  List[ProofByRootIdentifier, MAX_REQUEST_BLOCKS_DENEB]
)
```

Response Content:

```
(
  List[SignedExecutionProof, compute_max_request_execution_proofs()]
)
```

Requests execution proofs by block root and proof types. The response is a list
of `SignedExecutionProof` whose length is less than or equal to
`requested_proofs_count`, where
`requested_proofs_count = sum(len(r.proof_types) for r in request)`. It may be
less in the case that the responding peer is missing blocks or proofs.

No more than `compute_max_request_execution_proofs()` may be requested at a
time.

The response MUST consist of zero or more `response_chunk`. Each _successful_
`response_chunk` MUST contain a single `SignedExecutionProof` payload.

Clients MUST respond with at least one proof, if they have it. Clients MAY limit
the number of proofs in the response.

#### ExecutionProofStatus

**Protocol ID:** `/eth2/beacon_chain/req/execution_proof_status/1/`

Request, Response Content:

```
(
  block_root: Root
  slot: Slot
  proof_types: List[ProofType, MAX_EXECUTION_PROOFS_PER_PAYLOAD]
)
```

This protocol enables peers to exchange their current execution proof
verification status. The request and response use the same type.

As seen by the client at the time of sending the message:

- `block_root`: The `hash_tree_root` root of the most recent block
  (`BeaconBlock`) for which the client has verified sufficient execution proofs
  to consider the block valid.
- `slot`: The slot of the block corresponding to the `block_root`.
- `proof_types`: The proof types that this client supports. This is
  intentionally a dynamic capability advertisement rather than a protocol
  constant, allowing clients to support new proof types without requiring a hard
  fork or new client release. Peers SHOULD use this field to inform proof type
  selection during synchronization.

The request/response MUST be encoded as an SSZ-container.

The response MUST consist of a single `response_chunk`.

Upon receiving an `ExecutionProofStatus` request, the responder MUST reply with
its own local execution proof status. The requester SHOULD use the peer's
response to inform peer selection during execution proof synchronization.

Upon establishing a connection with a peer that is execution proof–aware (i.e.
the peer's ENR contains `eproof != 0`), the dialing client MUST send an
`ExecutionProofStatus` request.

## The discovery domain: discv5

### ENR structure

#### Execution proof awareness

A new field is added to the ENR under the key `eproof` to facilitate discovery
of nodes that are aware of optional execution proofs.

| Key      | Value                                    |
| -------- | ---------------------------------------- |
| `eproof` | Execution layer proof awareness, `uint8` |

A node is considered optional execution proof–aware if the `eproof` key is
present and its value is not 0.
