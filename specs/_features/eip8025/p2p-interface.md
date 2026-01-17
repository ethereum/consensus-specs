# EIP-8025 -- Networking

This document contains the networking specifications for EIP-8025.

*Note*: This specification is built upon [Fulu](../../fulu/p2p-interface.md) and
imports proof types from [proof-engine.md](./proof-engine.md).

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`execution_proof`](#execution_proof)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [ExecutionProofsByRoot](#executionproofsbyroot)

<!-- mdformat-toc end -->

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### `execution_proof`

This topic is used to propagate `ProverSignedExecutionProof` messages.

The following validations MUST pass before forwarding a proof on the network:

- _[IGNORE]_ The proof's corresponding new payload request (identified by
  `proof.message.public_input.new_payload_request_root`) has been seen (via
  gossip or non-gossip sources) (a client MAY queue proofs for processing once
  the new payload request is retrieved).
- _[IGNORE]_ The proof is the first valid proof received for the tuple
  `(proof.message.public_input.new_payload_request_root, proof.message.proof_type, prover_pubkey)`.

For `ProverSignedExecutionProof`:

- _[REJECT]_ The `prover_pubkey` is in the prover whitelist.
- _[REJECT]_ The signature is valid with respect to the prover's public key.
- _[REJECT]_ The `proof.message.proof_data` is non-empty.
- _[REJECT]_ The `proof.message.proof_data` is not larger than `MAX_PROOF_SIZE`.
- _[REJECT]_ The execution proof is valid as verified by the appropriate
  handler.

## The Req/Resp domain

### Messages

#### ExecutionProofsByRoot

**Protocol ID:** `/eth2/beacon_chain/req/execution_proofs_by_root/1/`

The `<context-bytes>` field is calculated as
`context = compute_fork_digest(fork_version, genesis_validators_root)`.

Request Content:

```
(
  block_root: Root
)
```

Response Content:

```
(
  List[ProverSignedExecutionProof, MAX_EXECUTION_PROOFS_PER_PAYLOAD]
)
```

Requests execution proofs for the given `block_root`. The response MUST contain
all available proofs for the requested beacon block, up to
`MAX_EXECUTION_PROOFS_PER_PAYLOAD`.

The following validations MUST pass:

- _[REJECT]_ The `block_root` is a 32-byte value.

The response MUST contain:

- All available execution proofs for the requested `block_root`.
- The response MUST NOT contain more than `MAX_EXECUTION_PROOFS_PER_PAYLOAD`
  proofs.
