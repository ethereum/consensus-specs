# EIP-8025 -- Networking

This document contains the networking specifications for EIP-8025.

*Note*: This specification is built upon [Gloas](../../gloas/p2p-interface.md)
and imports proof types from [beacon-chain.md](./beacon-chain.md).

EIP-8025 proofs propagate exclusively through gossip. No EIP-8025-specific
Req/Resp protocol is defined.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Constants](#constants)
  - [Execution](#execution)
  - [Type-specific SSZ bounds](#type-specific-ssz-bounds)
- [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
  - [Topics and messages](#topics-and-messages)
    - [Global topics](#global-topics)
      - [New `execution_proof`](#new-execution_proof)
- [The discovery domain: discv5](#the-discovery-domain-discv5)
  - [ENR structure](#enr-structure)
    - [Execution proof awareness](#execution-proof-awareness)

<!-- mdformat-toc end -->

## Constants

### Execution

*Note*: The execution values are not definitive.

| Name                               | Value       |
| ---------------------------------- | ----------- |
| `MAX_EXECUTION_PROOFS_PER_PAYLOAD` | `Uint64(4)` |

### Type-specific SSZ bounds

| Name                              | Value                        |
| --------------------------------- | ---------------------------- |
| `MAX_SIGNED_EXECUTION_PROOF_SIZE` | `Uint64(4194497)` (= ~4 MiB) |

## The gossip domain: gossipsub

### Topics and messages

#### Global topics

##### New `execution_proof`

This topic is used to propagate `SignedExecutionProof` messages.

The following validations MUST pass before forwarding the
`signed_execution_proof` on the network, assuming the alias
`proof = signed_execution_proof.message`:

- _[IGNORE]_ The proof has not already been processed -- i.e.
  `hash_tree_root(proof)` has not been seen before.
- _[IGNORE]_ The beacon block identified by
  `proof.public_input.head.beacon_block_root` and its accepted
  `SignedExecutionPayloadEnvelope` have been seen (via gossip or non-gossip
  sources). A client MAY queue the proof until both are available.
- _[IGNORE]_ No *valid* proof has already been received for the tuple
  `(proof.public_input.head.beacon_block_root, proof.proof_type)` -- i.e. no
  *valid* proof for `proof.proof_type` from any prover has been received for the
  same head.
- _[IGNORE]_ The proof is the first proof received for the tuple
  `(proof.public_input.head.beacon_block_root, proof.proof_type, signed_execution_proof.validator_index)`
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
- _[REJECT]_ `proof.proof_type` is less than `MAX_EXECUTION_PROOFS_PER_PAYLOAD`.
- _[REJECT]_ `proof.public_input.origin` equals the locally configured trusted
  `ExecutionCheckpoint`.
- _[REJECT]_ `proof.public_input.head.slot` and
  `proof.public_input.head.beacon_block_root` identify the accepted beacon
  block.
- _[REJECT]_ All of the conditions within `process_execution_proof` pass
  validation.

## The discovery domain: discv5

### ENR structure

#### Execution proof awareness

A new field is added to the ENR under the key `eproof` to facilitate discovery
and peering between nodes that participate in execution-proof gossip.

| Key      | Value                                    |
| -------- | ---------------------------------------- |
| `eproof` | Execution layer proof awareness, `Uint8` |

A node is considered execution proof-aware if the `eproof` key is present and
its value is not `0`. An execution proof-aware node subscribes to the
`execution_proof` gossip topic and implements its validation rules. Clients MAY
prefer execution proof-aware nodes when selecting peers for execution-proof
gossip.
