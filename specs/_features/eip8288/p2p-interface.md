# EIP-8288 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`execution_payload`](#execution_payload)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [ExecutionPayloadEnvelopesByRange and ExecutionPayloadEnvelopesByRoot](#executionpayloadenvelopesbyrange-and-executionpayloadenvelopesbyroot)
- [Design decision rationale](#design-decision-rationale)
  - [Why is `MAX_PAYLOAD_SIZE` unchanged?](#why-is-max_payload_size-unchanged)

<!-- mdformat-toc end -->

## Introduction

This document contains the networking changes of [EIP-8288](./beacon-chain.md).

*Note*: This specification is built upon [Heze](../../heze/p2p-interface.md).

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### `execution_payload`

The type of the payload of this topic, `SignedExecutionPayloadEnvelope`, carries
the modified `ExecutionPayload`, so its encoding grows by
`len(payload.dependency_proof)`, up to `MAX_DEPENDENCY_PROOF_BYTES`, plus the
field's offset. The validation rules are unchanged: a payload whose
`dependency_proof` exceeds `MAX_DEPENDENCY_PROOF_BYTES` does not decode and is
rejected as malformed.

## The Req/Resp domain

### Messages

#### ExecutionPayloadEnvelopesByRange and ExecutionPayloadEnvelopesByRoot

Responses carry the envelope of this fork with its `dependency_proof`. A node
that has pruned a proof (see
[Dependency proof retention](./beacon-chain.md#dependency-proof-retention))
cannot reconstruct the envelope and MUST NOT respond with it; it responds as for
an envelope it does not have. Nodes SHOULD NOT prune proofs within the weak
subjectivity period.

## Design decision rationale

### Why is `MAX_PAYLOAD_SIZE` unchanged?

`MAX_PAYLOAD_SIZE` (10 MiB) bounds every gossip message and RPC chunk. The
dependency proof adds at most `MAX_DEPENDENCY_PROOF_BYTES` (1 MiB) to an
envelope; measured proofs are about 200-320 KB. The execution payload's other
fields are bounded by the execution layer's
[EIP-7934](https://eips.ethereum.org/EIPS/eip-7934) block size limit, which does
not cover the proof, so an envelope fits in `MAX_PAYLOAD_SIZE` as long as the
RLP block limit stays below `MAX_PAYLOAD_SIZE - MAX_DEPENDENCY_PROOF_BYTES`
minus the envelope's own fields. A fork that raises the block size limit past
that point has to raise `MAX_PAYLOAD_SIZE` with it.
