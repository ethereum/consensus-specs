# EIP-8025 -- Networking

This document contains the networking specifications for EIP-8025.

*Note*: This specification is built upon [Fulu](../../fulu/p2p-interface.md) and
imports proof types from [proof-engine.md](./proof-engine.md).

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Constants](#constants)
  - [Execution](#execution)
- [Helpers](#helpers)
  - [Modified `compute_fork_version`](#modified-compute_fork_version)
- [MetaData](#metadata)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [`execution_proof`](#execution_proof)
- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [ExecutionProofsByRoot](#executionproofsbyroot)
    - [GetMetaData v4](#getmetadata-v4)
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

## Helpers

### Modified `compute_fork_version`

```python
def compute_fork_version(epoch: Epoch) -> Version:
    """
    Return the fork version at the given ``epoch``.
    """
    if epoch >= EIP8025_FORK_EPOCH:
        return EIP8025_FORK_VERSION
    if epoch >= FULU_FORK_EPOCH:
        return FULU_FORK_VERSION
    if epoch >= ELECTRA_FORK_EPOCH:
        return ELECTRA_FORK_VERSION
    if epoch >= DENEB_FORK_EPOCH:
        return DENEB_FORK_VERSION
    if epoch >= CAPELLA_FORK_EPOCH:
        return CAPELLA_FORK_VERSION
    if epoch >= BELLATRIX_FORK_EPOCH:
        return BELLATRIX_FORK_VERSION
    if epoch >= ALTAIR_FORK_EPOCH:
        return ALTAIR_FORK_VERSION
    return GENESIS_FORK_VERSION
```

## MetaData

The `MetaData` stored locally by clients is updated with an additional field to
communicate execution proof awareness.

```
(
  seq_number: uint64
  attnets: Bitvector[ATTESTATION_SUBNET_COUNT]
  syncnets: Bitvector[SYNC_COMMITTEE_SUBNET_COUNT]
  custody_group_count: uint64  # cgc
  execution_proof_aware: bool  # eproof
)
```

Where

- `seq_number`, `attnets`, `syncnets`, and `custody_group_count` have the same
  meaning defined in the previous documents.
- `execution_proof_aware` indicates whether the node is aware of optional
  execution proofs. A value of `True` signals that the node understands
  execution proof gossip topics and can participate in execution proof
  propagation.

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### `execution_proof`

This topic is used to propagate `SignedExecutionProof` messages.

The following validations MUST pass before forwarding the
`signed_execution_proof` on the network, assuming the alias
`proof = signed_execution_proof.message`:

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
  List[SignedExecutionProof, MAX_EXECUTION_PROOFS_PER_PAYLOAD]
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

#### GetMetaData v4

**Protocol ID:** `/eth2/beacon_chain/req/metadata/4/`

No Request Content.

Response Content:

```
(
  MetaData
)
```

Requests the MetaData of a peer, using the new `MetaData` definition given above
that is extended from Altair. Other conditions for the `GetMetaData` protocol
are unchanged from the Altair p2p networking document.

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
