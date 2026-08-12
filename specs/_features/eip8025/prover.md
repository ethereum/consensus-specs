# EIP-8025 -- Honest Prover

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `get_execution_proof_signature`](#new-get_execution_proof_signature)
- [Execution proof](#execution-proof)
  - [Obtaining an execution witness](#obtaining-an-execution-witness)
  - [Constructing the `SignedExecutionProof`](#constructing-the-signedexecutionproof)

<!-- mdformat-toc end -->

## Introduction

This document represents the prover guide accompanying EIP-8025. Provers are
active validators who voluntarily generate and submit execution proofs without
direct protocol-level compensation. They provide a public good by enabling
stateless validation during the optional proof phase.

*Note*: Provers are a transitional mechanism. In future mandatory proof forks,
builders will be required to produce and gossip execution proofs as part of
their block production duties, and the prover role will be deprecated.

*Note*: This specification is built upon [Gloas](../../gloas/beacon-chain.md)
and imports proof types from [proof-engine.md](./proof-engine.md).

## Helpers

### New `get_execution_proof_signature`

```python
def get_execution_proof_signature(
    state: BeaconState, proof: ExecutionProof, privkey: int
) -> BLSSignature:
    domain = get_domain(state, DOMAIN_EXECUTION_PROOF, compute_epoch_at_slot(state.slot))
    signing_root = compute_signing_root(proof, domain)
    return bls.Sign(privkey, signing_root)
```

## Execution proof

### Obtaining an execution witness

The execution witness is obtained from the execution layer through a versioned
Engine API `newPayloadWithWitness` method. This is an EL method: the consensus
client sends the same `NewPayloadRequest` used by `engine_newPayload`, and the
EL returns payload validation status together with the execution witness needed
by the stateless guest.

- `VALID` with a witness permits proof generation.
- `SYNCING` or `ACCEPTED` is retryable and does not permit proof generation yet.
- `INVALID` is terminal for that payload and no proof is requested.
- A missing or malformed witness is an error even when the status is `VALID`.

The locally configured execution `ChainConfig` is not supplied by the EL and is
committed separately as `chain_config_root`. Transaction public keys are derived
by the prover host from the payload transactions in the canonical form expected
by the execution-specs stateless verifier.

### Constructing the `SignedExecutionProof`

An honest prover who is an active validator and wants to generate execution
proofs for a `SignedExecutionPayloadEnvelope` performs the following steps:

1. At startup, subscribe to:
   - `execution_payload` events from the beacon node via SSE.
   - Proof completion events from the proof engine via SSE. The concrete SSE
     event shape is defined by the proof engine API specification.
2. Upon receiving an `execution_payload` event:
   - Fetch the accepted `SignedExecutionPayloadEnvelope` and its target beacon
     block.
   - Select the latest compatible proof for each requested proof type, or the
     configured `ExecutionCheckpoint` origin if no proof exists.
   - Fetch every produced beacon block from that predecessor through the target
     block, inclusive. Slot gaps represent missed slots and require no witness.
   - Build a `BeaconBlockBidWitness` for each fetched block by extracting its
     `SignedExecutionPayloadBid` and its Merkle branch against the block
     header's `body_root`. The resulting `beacon_lineage` starts with the
     predecessor checkpoint and ends with the target block.
   - Call the EL `newPayloadWithWitness` Engine API method for the target
     payload and require a `VALID` response with an `ExecutionWitness`. Load the
     locally configured `ChainConfig`, derive the transaction public keys, and
     compute the trusted `chain_config_root`. The terminal parent header in the
     execution witness MUST correspond to the execution block hash opened from
     the predecessor checkpoint bid. If any intermediate produced block is
     *full*, first generate a separate recursive proof for that transition.
   - Build `BeaconStateWitness` branches for `genesis_time`, `fork`,
     `genesis_validators_root`, `payload_expected_withdrawals`, and the selected
     envelope signer public key against the target block's state root.
   - For each desired `proof_type`, assemble a `BeaconChainWitness` from its
     compatible predecessor, beacon lineage, and signed envelope. Combine it
     with the execution witness, chain configuration, and transaction public
     keys as `PrivateInput`.
   - Call
     `beacon_block_root = proof_engine.request_proof(private_input, proof_type, trusted_chain_config_root)`
     to initiate proof generation, tracking the request by
     `(beacon_block_root, proof_type)`.
3. The proof engine runs `process_private_input` in the selected guest. Proof
   generation is abandoned if the selected lineage ceases to be canonical; a
   later proof starts from the latest compatible predecessor.
4. Upon receiving a proof completion event for a tracked
   `(beacon_block_root, proof_type)`:
   - Fetch the completed `ExecutionProof` from the proof engine.
   - Check that `proof.claim.head.beacon_block_root` equals the tracked
     `beacon_block_root` and that `proof.claim.head.slot` equals the target
     block slot.
   - Let `validator_index` be the prover's validator index.
   - Let
     `signature = get_execution_proof_signature(state, proof, prover_privkey)`.
   - Let
     `signed_proof = SignedExecutionProof(message=proof, validator_index=validator_index, signature=signature)`.
   - Broadcast `signed_proof` on the `execution_proof` gossip topic.
