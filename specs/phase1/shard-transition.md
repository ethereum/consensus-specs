# Ethereum 2.0 Phase 1 -- Shard Transition and Fraud Proofs

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Introduction](#introduction)
- [Helper functions](#helper-functions)
  - [Misc](#misc)
  - [Shard block verification functions](#shard-block-verification-functions)
- [Shard state transition](#shard-state-transition)
- [Fraud proofs](#fraud-proofs)
  - [Verifying the proof](#verifying-the-proof)
- [Honest committee member behavior](#honest-committee-member-behavior)
  - [Helper functions](#helper-functions-1)
  - [Make attestations](#make-attestations)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the shard transition function and fraud proofs as part of Phase 1 of Ethereum 2.0.

## Helper functions

### Misc

```python
def compute_shard_transition_digest(beacon_state: BeaconState,
                                    shard_state: ShardState,
                                    beacon_parent_root: Root,
                                    shard_body_root: Root) -> Bytes32:
    # TODO: use SSZ hash tree root
    return hash(
        hash_tree_root(shard_state) + beacon_parent_root + shard_body_root
    )
```

### Shard block verification functions

```python
def verify_shard_block_message(beacon_state: BeaconState,
                               shard_state: ShardState,
                               block: ShardBlock,
                               slot: Slot,
                               shard: Shard) -> bool:
    assert block.shard_parent_root == shard_state.latest_block_root
    assert block.slot == slot
    assert block.proposer_index == get_shard_proposer_index(beacon_state, slot, shard)
    assert 0 < len(block.body) <= MAX_SHARD_BLOCK_SIZE
    return True
```

```python
def verify_shard_block_signature(beacon_state: BeaconState,
                                 signed_block: SignedShardBlock) -> bool:
    proposer = beacon_state.validators[signed_block.message.proposer_index]
    domain = get_domain(beacon_state, DOMAIN_SHARD_PROPOSAL, compute_epoch_at_slot(signed_block.message.slot))
    signing_root = compute_signing_root(signed_block.message, domain)
    return bls.Verify(proposer.pubkey, signing_root, signed_block.signature)
```

## Shard state transition

```python
def shard_state_transition(beacon_state: BeaconState,
                           shard_state: ShardState,
                           block: ShardBlock) -> None:
    # Update shard state
    prev_gasprice = shard_state.gasprice
    if len(block.body) == 0:
        latest_block_root = shard_state.latest_block_root
    else:
        latest_block_root = hash_tree_root(block)

    shard_state.transition_digest = compute_shard_transition_digest(
        beacon_state,
        shard_state,
        block.beacon_parent_root,
        block.body,
    )
    shard_state.gasprice = compute_updated_gasprice(prev_gasprice, len(block.body))
    shard_state.slot = block.slot
    shard_state.latest_block_root = latest_block_root
```

We have a pure function `get_post_shard_state` for describing the fraud proof verification and honest validator behavior.

```python
def get_post_shard_state(beacon_state: BeaconState,
                         shard_state: ShardState,
                         block: ShardBlock) -> ShardState:
    """
    A pure function that returns a new post ShardState instead of modifying the given `shard_state`.
    """
    post_state = shard_state.copy()
    shard_state_transition(beacon_state, post_state, block)
    return post_state
```

## Fraud proofs

### Verifying the proof

TODO. The intent is to have a single universal fraud proof type, which contains the following parts:

1. An on-time attestation `attestation` on some shard `shard` signing a `transition: ShardTransition`
2. An index `offset_index` of a particular position to focus on
3. The `transition: ShardTransition` itself
4. The full body of the shard block `shard_block`
5. A Merkle proof to the `shard_states` in the parent block the attestation is referencing
6. The `subkey` to generate the custody bit

Call the following function to verify the proof:

```python
def is_valid_fraud_proof(beacon_state: BeaconState,
                         attestation: Attestation,
                         offset_index: uint64,
                         transition: ShardTransition,
                         block: ShardBlock,
                         subkey: BLSPubkey,
                         beacon_parent_block: BeaconBlock) -> bool:
    # 1. Check if `custody_bits[offset_index][j] != generate_custody_bit(subkey, block_contents)` for any `j`.
    custody_bits = attestation.custody_bits_blocks
    for j in range(len(custody_bits[offset_index])):
        if custody_bits[offset_index][j] != generate_custody_bit(subkey, block):
            return True

    # 2. Check if the shard state transition result is wrong between
    # `transition.shard_states[offset_index - 1]` to `transition.shard_states[offset_index]`.
    if offset_index == 0:
        shard = get_shard(beacon_state, attestation)
        shard_states = beacon_parent_block.body.shard_transitions[shard].shard_states
        shard_state = shard_states[len(shard_states) - 1]
    else:
        shard_state = transition.shard_states[offset_index - 1]  # Not doing the actual state updates here.

    shard_state = get_post_shard_state(beacon_state, shard_state, block)
    if shard_state.transition_digest != transition.shard_states[offset_index].transition_digest:
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
def compute_shard_body_roots(proposals: Sequence[SignedShardBlock]) -> Sequence[Root]:
    return [hash_tree_root(proposal.message.body) for proposal in proposals]
```

```python
def get_proposal_choices_at_slot(beacon_state: BeaconState,
                                 shard_state: ShardState,
                                 slot: Slot,
                                 shard: Shard,
                                 shard_blocks: Sequence[SignedShardBlock],
                                 validate_signature: bool=True) -> Sequence[SignedShardBlock]:
    """
    Return the valid shard blocks at the given ``slot``.
    Note that this function doesn't change the state.
    """
    choices = []
    shard_blocks_at_slot = [block for block in shard_blocks if block.message.slot == slot]
    for block in shard_blocks_at_slot:
        try:
            # Verify block message and signature
            # TODO these validations should have been checked upon receiving shard blocks.
            assert verify_shard_block_message(beacon_state, shard_state, block.message, slot, shard)
            if validate_signature:
                assert verify_shard_block_signature(beacon_state, block)

            shard_state = get_post_shard_state(beacon_state, shard_state, block.message)
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
                         shard_blocks: Sequence[SignedShardBlock],
                         validate_signature: bool=True) -> Tuple[SignedShardBlock, ShardState]:
    """
    Return ``proposal``, ``shard_state`` of the given ``slot``.
    Note that this function doesn't change the state.
    """
    choices = get_proposal_choices_at_slot(
        beacon_state=beacon_state,
        shard_state=shard_state,
        slot=slot,
        shard=shard,
        shard_blocks=shard_blocks,
        validate_signature=validate_signature,
    )
    if len(choices) == 0:
        block = ShardBlock(slot=slot)
        proposal = SignedShardBlock(message=block)
    elif len(choices) == 1:
        proposal = choices[0]
    else:
        proposal = get_winning_proposal(beacon_state, choices)

    # Apply state transition
    shard_state = get_post_shard_state(beacon_state, shard_state, proposal.message)

    return proposal, shard_state
```

```python
def get_shard_state_transition_result(
    beacon_state: BeaconState,
    shard: Shard,
    shard_blocks: Sequence[SignedShardBlock],
    validate_signature: bool=True,
) -> Tuple[Sequence[SignedShardBlock], Sequence[ShardState], Sequence[Root]]:
    proposals = []
    shard_states = []
    shard_state = beacon_state.shard_states[shard]
    for slot in get_offset_slots(beacon_state, shard):
        proposal, shard_state = get_proposal_at_slot(
            beacon_state=beacon_state,
            shard_state=shard_state,
            slot=slot,
            shard=shard,
            shard_blocks=shard_blocks,
            validate_signature=validate_signature,
        )
        shard_states.append(shard_state)
        proposals.append(proposal)

    shard_data_roots = compute_shard_body_roots(proposals)

    return proposals, shard_states, shard_data_roots
```

### Make attestations

Suppose you are a committee member on shard `shard` at slot `current_slot` and you have received shard blocks `shard_blocks` since the latest successful crosslink for `shard` into the beacon chain. Let `beacon_state` be the head beacon state you are building on, and let `QUARTER_PERIOD = SECONDS_PER_SLOT // 4`. `2 * QUARTER_PERIOD` seconds into slot `current_slot`, run `get_shard_transition(beacon_state, shard, shard_blocks)` to get `shard_transition`.

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
        if proposal.signature != NO_SIGNATURE:
            proposer_signatures.append(proposal.signature)

    if len(proposer_signatures) > 0:
        proposer_signature_aggregate = bls.Aggregate(proposer_signatures)
    else:
        proposer_signature_aggregate = NO_SIGNATURE

    return ShardTransition(
        start_slot=start_slot,
        shard_block_lengths=shard_block_lengths,
        shard_data_roots=shard_data_roots,
        shard_states=shard_states,
        proposer_signature_aggregate=proposer_signature_aggregate,
    )
```
