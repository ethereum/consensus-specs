<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Ethereum 2.0 Phase 1 -- Shard Transition and Fraud Proofs](#ethereum-20-phase-1----shard-transition-and-fraud-proofs)
  - [Table of contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Fraud proofs](#fraud-proofs)
    - [Shard state transition function](#shard-state-transition-function)
    - [Verifying the proof](#verifying-the-proof)
  - [Honest committee member behavior](#honest-committee-member-behavior)
    - [Helper functions](#helper-functions)
    - [Make attestations](#make-attestations)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Ethereum 2.0 Phase 1 -- Shard Transition and Fraud Proofs

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

 TODO

<!-- /TOC -->

## Introduction

This document describes the shard transition function and fraud proofs as part of Phase 1 of Ethereum 2.0.

## Fraud proofs

### Shard state transition function

```python
def shard_state_transition(beacon_state: BeaconState,
                           shard: Shard,
                           slot: Slot,
                           shard_state: ShardState,
                           beacon_parent_root: Root,
                           signed_block: SignedShardBlock) -> None:
    # Update shard state
    shard_state.data = hash(
        hash_tree_root(shard_state) + hash_tree_root(beacon_parent_root) + hash_tree_root(signed_block.message.body)
    )
    shard_state.slot = slot
    shard_state.latest_block_root = hash_tree_root(signed_block.message)
```

```python
def verify_shard_block_signature(beacon_state: BeaconState,
                                 signed_block: SignedShardBlock) -> bool:
    proposer = beacon_state.validators[signed_block.message.proposer_index]
    domain = get_domain(beacon_state, DOMAIN_SHARD_PROPOSAL, compute_epoch_at_slot(signed_block.message.slot))
    signing_root = compute_signing_root(signed_block.message, domain)
    return bls.Verify(proposer.pubkey, signing_root, signed_block.signature)
```

### Verifying the proof

TODO. The intent is to have a single universal fraud proof type, which contains the following parts:

1. An on-time attestation `attestation` on some shard `shard` signing a `transition: ShardTransition`
2. An index `offset_index` of a particular position to focus on
3. The `transition: ShardTransition` itself
4. The full body of the shard block `shard_block`
5. A Merkle proof to the `shard_states` in the parent block the attestation is referencing

Call the following function to verify the proof:

```python
def verify_fraud_proof(beacon_state: BeaconState,
                       attestation: Attestation,
                       offset_index: uint64,
                       transition: ShardTransition,
                       signed_block: SignedShardBlock,
                       subkey: BLSPubkey,
                       beacon_parent_block: BeaconBlock) -> bool:
    # 1. Check if `custody_bits[offset_index][j] != generate_custody_bit(subkey, block_contents)` for any `j`.
    shard = get_shard(beacon_state, attestation)
    slot = attestation.data.slot
    custody_bits = attestation.custody_bits_blocks
    for j in range(custody_bits[offset_index]):
        if custody_bits[offset_index][j] != generate_custody_bit(subkey, signed_block):
            return True

    # 2. Check if the shard state transition result is wrong between
    # `transition.shard_states[offset_index - 1]` to `transition.shard_states[offset_index]`.
    if offset_index == 0:
        shard_state = beacon_parent_block.shard_transitions[shard].shard_states[-1]
    else:
        shard_state = transition.shard_states[offset_index - 1].copy()  # Not doing the actual state updates here.

    shard_state_transition(
        beacon_state=beacon_state,
        shard=shard,
        slot=slot,
        shard_state=shard_state,
        beacon_parent_root=hash_tree_root(beacon_parent_block),
        signed_block=signed_block,
    )
    if shard_state.latest_block_root != transition.shard_states[offset_index].data:
        return True

    return False
```

```python
def generate_custody_bit(subkey: BLSPubkey, block: ShardBlock) -> bool:
    # TODO
    ...
```

## Honest committee member behavior

### Helper functions

```python
def get_winning_proposal(beacon_state: BeaconState, proposals: Sequence[SignedShardBlock]) -> SignedShardBlock:
    # TODO: Let `winning_proposal` be the proposal with the largest number of total attestations from slots in
    # `state.shard_next_slots[shard]....slot-1` supporting it or any of its descendants, breaking ties by choosing
    # the first proposal locally seen. Do `proposals.append(winning_proposal)`.
    return proposals[-1]  # stub
```

```python
def get_empty_body_block(shard_parent_root: Root,
                         beacon_parent_root: Root,
                         slot: Slot,
                         proposer_index: ValidatorIndex) -> ShardBlock:
    return ShardBlock(
        shard_parent_root=shard_parent_root,
        beacon_parent_root=beacon_parent_root,
        slot=slot,
        proposer_index=proposer_index,
    )
```

```python
def is_empty_body(proposal: ShardBlock) -> bool:
    # TODO
    return len(proposal.body) == 0
```

```python
def compute_shard_data_roots(proposals: Sequence[SignedShardBlock]) -> Sequence[Root]:
    return [hash_tree_root(proposal.message.body) for proposal in proposals]
```

```python
def get_proposal_choices_at_slot(beacon_state: BeaconState,
                                 shard_state: ShardState,
                                 slot: Slot,
                                 shard: Shard,
                                 shard_blocks: Sequence[SignedShardBlock],
                                 validate_result: bool=True) -> Sequence[SignedShardBlock]:
    choices = []
    beacon_parent_root = get_block_root_at_slot(beacon_state, get_previous_slot(beacon_state.slot))
    proposer_index = get_shard_proposer_index(beacon_state, slot, shard)
    shard_blocks_at_slot = [block for block in shard_blocks if block.message.slot == slot]
    for block in shard_blocks_at_slot:
        temp_shard_state = shard_state.copy()  # Not doing the actual state updates here.
        # Try to apply state transition to temp_shard_state.
        try:
            # Verify the proposer_index and signature
            assert block.message.proposer_index == proposer_index
            if validate_result:
                assert verify_shard_block_signature(beacon_state, block)

            shard_state_transition(
                beacon_state=beacon_state,
                shard=shard,
                slot=slot,
                shard_state=temp_shard_state,
                beacon_parent_root=beacon_parent_root,
                signed_block=block,
            )
        except Exception:
            pass  # TODO: throw error in the test helper
        else:
            choices.append(block)
    return choices
```

```python
def get_proposal_at_slot(beacon_state: BeaconState,
                         shard_state: ShardState,
                         slot: Shard,
                         shard: Shard,
                         shard_parent_root: Root,
                         shard_blocks: Sequence[SignedShardBlock],
                         validate_result: bool=True) -> Tuple[SignedShardBlock, ShardState, Root]:
    beacon_parent_root = get_block_root_at_slot(beacon_state, get_previous_slot(beacon_state.slot))
    proposer_index = get_shard_proposer_index(beacon_state, slot, shard)
    shard_state = shard_state.copy()  # Don't update the given shard_state
    choices = get_proposal_choices_at_slot(
        beacon_state=beacon_state,
        shard_state=shard_state,
        slot=slot,
        shard=shard,
        shard_blocks=shard_blocks,
        validate_result=validate_result,
    )
    if len(choices) == 0:
        block_header = get_empty_body_block(
            shard_parent_root=shard_parent_root,
            beacon_parent_root=beacon_parent_root,
            slot=slot,
            proposer_index=proposer_index,
        )
        proposal = SignedShardBlock(message=block_header)
    elif len(choices) == 1:
        proposal = choices[0]
    else:
        proposal = get_winning_proposal(beacon_state, choices)

    shard_parent_root = hash_tree_root(proposal.message)

    if not is_empty_body(proposal.message):
        # Apply state transition to shard_state.
        shard_state_transition(
            beacon_state=beacon_state,
            shard=shard,
            slot=slot,
            shard_state=shard_state,
            beacon_parent_root=beacon_parent_root,
            signed_block=proposal,
        )

    return proposal, shard_state, shard_parent_root
```

```python
def get_shard_state_transition_result(
    beacon_state: BeaconState,
    shard: Shard,
    shard_blocks: Sequence[SignedShardBlock],
    validate_result: bool=True,
) -> Tuple[Sequence[SignedShardBlock], Sequence[ShardState], Sequence[Root]]:
    proposals = []
    shard_states = []
    shard_state = beacon_state.shard_states[shard].copy()
    shard_parent_root = beacon_state.shard_states[shard].latest_block_root
    for slot in get_offset_slots(beacon_state, shard):
        proposal, shard_state, shard_parent_root = get_proposal_at_slot(
            beacon_state=beacon_state,
            shard_state=shard_state,
            slot=slot,
            shard=shard,
            shard_parent_root=shard_parent_root,
            shard_blocks=shard_blocks,
            validate_result=validate_result,
        )
        shard_states.append(shard_state)
        proposals.append(proposal)

    shard_data_roots = compute_shard_data_roots(proposals)

    return proposals, shard_states, shard_data_roots
```

### Make attestations

Suppose you are a committee member on shard `shard` at slot `current_slot` and you have received shard blocks `shard_blocks` since the latest successful crosslink for `shard` into the beacon chain. Let `state` be the head beacon state you are building on, and let `QUARTER_PERIOD = SECONDS_PER_SLOT // 4`. `2 * QUARTER_PERIOD` seconds into slot `current_slot`, run `get_shard_transition(beacon_state, shard, shard_blocks)` to get `shard_transition`.

```python
def get_shard_transition(beacon_state: BeaconState,
                         shard: Shard,
                         shard_blocks: Sequence[SignedShardBlock]) -> ShardTransition:
    offset_slots = get_offset_slots(beacon_state, shard)
    start_slot = offset_slots[0]
    proposals, shard_states, shard_data_roots = get_shard_state_transition_result(beacon_state, shard, shard_blocks)

    assert len(proposals) > 0
    assert len(shard_data_roots) > 0

    shard_block_lengths = []
    proposer_signatures = []
    for proposal in proposals:
        shard_block_lengths.append(len(proposal.message.body))
        if proposal.signature != BLSSignature():
            proposer_signatures.append(proposal.signature)

    proposer_signature_aggregate = bls.Aggregate(proposer_signatures)

    return ShardTransition(
        start_slot=start_slot,
        shard_block_lengths=shard_block_lengths,
        shard_data_roots=shard_data_roots,
        shard_states=shard_states,
        proposer_signature_aggregate=proposer_signature_aggregate,
    )
```
