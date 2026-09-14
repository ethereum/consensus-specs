# EIP-8025 execution-proof test vectors

This directory defines a fixture contract for EIP-8025 execution-proof vectors. It is independent of any proving system: vectors describe consensus inputs and expected outcomes, while proof bytes remain opaque fixtures supplied by the vector producer.

## Scope

The first vector set should cover the boundary between gossip validation, proof verification, and store mutation. Reference behaviours are implemented in:

- specs/_features/eip8025/fork-choice.md
- specs/_features/eip8025/p2p-interface.md
- tests/core/pyspec/eth_consensus_specs/test/eip8025/unittests/test_gossip_execution_proof.py
- tests/core/pyspec/eth_consensus_specs/test/eip8025/unittests/test_prover.py

## Fixture shape

Each case should be a directory containing meta.yaml, the serialized consensus objects required by the case, and an optional opaque proof fixture. The metadata should contain:

    case: missing-block-context
    fork: eip8025
    proof_type: 0
    input:
      beacon_block_root: 0x...
      proof_data: 0x...
      prover_index: 0
    context:
      block: present | missing
      block_state: present | missing
      execution_payload: present | missing
    proof_engine:
      result: valid | invalid
    expected:
      gossip: valid | ignore | reject
      handler: stored | not_stored | assertion
      reason: stable human-readable reason

The fixture format must keep proof_data opaque. A consumer must pass the complete proof input to the configured proof engine and compare the consensus outcome; it must not infer validity from the encoding.

## Initial scenario matrix

| Case | Purpose | Expected outcome |
| --- | --- | --- |
| valid-first-proof | Known block, state and payload; engine accepts | Gossip valid; proof stored under block root and proof type |
| unknown-block | Proof references an absent block | Gossip ignored until context is available |
| missing-state | Block exists but post-state is absent | Handler rejects; store unchanged |
| missing-payload | Block and state exist but payload is absent | Handler rejects; store unchanged |
| payload-root-mismatch | Payload root differs from envelope context | Handler rejects; no proof stored |
| engine-rejects | Complete context but engine returns invalid | Handler rejects; no proof stored |
| duplicate-same-type | Same root and proof type appears twice | Second gossip input is ignored |
| different-proof-type | Same root with an unverified alternate type | Alternate proof remains eligible |
| different-prover | Same proof from another prover | Duplicate is ignored by root and proof type |

## Determinism and checks

A vector runner should compare both the classified result and the reason where exposed. Store assertions must verify that failed verification does not mutate execution_proofs, and that accepted proofs are keyed by both beacon block root and proof type.

Vectors should use fixed roots, indexes, and proof bytes; no wall-clock value, random seed, network call, or locally generated signature should be required. A future proof-engine-specific suite can add cryptographic witnesses without changing this consensus-level contract.

## Acceptance checklist

- Every case identifies the fork and proof type.
- Every case states which context objects are present.
- Every accepted case records the exact store key and resulting proof type.
- Every ignored or rejected case records why no store mutation occurs.
- The same fixture produces the same result for the pyspec runner and downstream client consumers.
- Invalid proof bytes are test data only and contain no secret.

This document defines the fixture contract and coverage plan. It does not claim that vectors or a proof engine have been executed yet; serialized cases can follow this matrix in issue #5072.
