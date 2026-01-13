# EIP-8025 -- Networking

This document contains the networking specification for EIP-8025.

*Note*: This specification is built upon [Gloas](../../gloas/p2p-interface.md)
and imports proof types from
[eip8025/proof-engine.md](../eip8025/proof-engine.md).

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`signed_execution_payload_header_envelope`](#signed_execution_payload_header_envelope)
      - [`execution_proof`](#execution_proof)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [ExecutionProofsByRoot](#executionproofsbyroot)

<!-- mdformat-toc end -->

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### `signed_execution_payload_header_envelope`

This topic is used to propagate `SignedExecutionPayloadHeaderEnvelope` messages.

The following validations MUST pass before forwarding the
`signed_execution_payload_header_envelope` on the network, assuming the alias
`envelope = signed_execution_payload_header_envelope.message`,
`payload = envelope.payload`:

- _[IGNORE]_ The envelope's block root `envelope.beacon_block_root` has been
  seen (via gossip or non-gossip sources) (a client MAY queue headers for
  processing once the block is retrieved).
- _[IGNORE]_ The node has not seen another valid
  `SignedExecutionPayloadHeaderEnvelope` for this block root from this builder.
- _[IGNORE]_ The envelope is from a slot greater than or equal to the latest
  finalized slot -- i.e. validate that
  `envelope.slot >= compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)`

Let `block` be the block with `envelope.beacon_block_root`. Let `bid` alias
`block.body.signed_execution_payload_bid.message`.

- _[REJECT]_ `block` passes validation.
- _[REJECT]_ `block.slot` equals `envelope.slot`.
- _[REJECT]_ `envelope.builder_index == bid.builder_index`
- _[REJECT]_ `payload.block_hash == bid.block_hash`
- _[REJECT]_ `signed_execution_payload_header_envelope.signature` is valid with
  respect to the builder's public key.

##### `execution_proof`

This topic is used to propagate `SignedExecutionProof` messages.

The following validations MUST pass before forwarding a proof on the network:

- _[IGNORE]_ The proof's corresponding new payload request (identified by
  `proof.message.public_input.new_payload_request_root`) has been seen (via
  gossip or non-gossip sources) (a client MAY queue proofs for processing once
  the new payload request is retrieved).
- _[IGNORE]_ The proof is the first valid proof received for the tuple
  `(proof.message.public_input.new_payload_request_root, proof.message.proof_type, builder_index)`.

For `SignedExecutionProof`:

- _[REJECT]_ The `builder_index` is within the known builder registry.
- _[REJECT]_ The signature is valid with respect to the builder's public key.
- _[REJECT]_ The `proof.message.proof_data` is non-empty.
- _[REJECT]_ The `proof.message.proof_data` is not larger than `MAX_PROOF_SIZE`.
- _[REJECT]_ The execution proof is valid as verified by the appropriate
  handler.

## The Req/Resp domain

### Messages

#### ExecutionProofsByRoot

**Protocol ID:** `/eth2/beacon/req/execution_proofs_by_root/1/`

The `<context-bytes>` field is calculated as
`context = compute_fork_digest(fork_version, genesis_validators_root)`.

Request Content:

```
(
  Root
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
