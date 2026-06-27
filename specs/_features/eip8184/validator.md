# EIP-8184 -- Honest Validator

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [New `get_sealed_mempool_entries`](#new-get_sealed_mempool_entries)
    - [New `is_st_commitment_satisfied`](#new-is_st_commitment_satisfied)
- [Beacon chain responsibilities](#beacon-chain-responsibilities)
  - [Inclusion list proposal](#inclusion-list-proposal)
    - [Modified construction of the `SignedInclusionList`](#modified-construction-of-the-signedinclusionlist)
  - [PTC key timeliness vote](#ptc-key-timeliness-vote)
    - [New `get_lucid_key_timeliness_vote_signature`](#new-get_lucid_key_timeliness_vote_signature)
    - [Constructing the `SignedLucidKeyTimelinessVote`](#constructing-the-signedlucidkeytimelinessvote)
  - [Block and sidecar proposal](#block-and-sidecar-proposal)
    - [Modified `prepare_execution_payload`](#modified-prepare_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This document represents the changes to be made in the code of an "honest
validator" to implement EIP-8184 (LUCID).

## Protocols

### `ExecutionEngine`

#### New `get_sealed_mempool_entries`

*Note*: `get_sealed_mempool_entries` returns the sealed transactions and
sealed bundles currently observed in the public encrypted mempool that
the IL committee member intends to commit to.

```python
@dataclass
class GetSealedMempoolEntriesResponse:
    sealed_transactions: Sequence[SealedTransaction]
    sealed_bundles: Sequence[SealedBundle]


def get_sealed_mempool_entries(
    self: ExecutionEngine,
) -> GetSealedMempoolEntriesResponse:
    """
    Return sealed transactions and bundles to include in the next
    inclusion list, subject to ``MAX_ST_COMMITS_PER_IL``.
    """
```

#### New `is_st_commitment_satisfied`

```python
def is_st_commitment_satisfied(
    self: ExecutionEngine,
    execution_payload: ExecutionPayload,
    st_commitments: Sequence[STCommitment],
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload`` satisfies the
    ST-commitment constraints of LUCID with respect to
    ``st_commitments``.
    """
```

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted
below.

### Inclusion list proposal

A validator that is a member of the inclusion list committee for the
current slot proposes a `SignedInclusionList` as described in
[Heze](../../heze/validator.md#inclusion-list-proposal), extended to
carry sealed transactions and bundles.

#### Modified construction of the `SignedInclusionList`

The validator creates the `signed_inclusion_list` as follows. Steps
unchanged from Heze are abbreviated; new steps are marked.

- Set `inclusion_list.slot`, `inclusion_list.validator_index`,
  `inclusion_list.inclusion_list_committee_root`, and
  `inclusion_list.transactions` as in Heze.
- *[New in EIP8184]* Obtain a
  [`GetSealedMempoolEntriesResponse`](#new-get_sealed_mempool_entries)
  from the execution engine.
- *[New in EIP8184]* Set `inclusion_list.sealed_transactions` and
  `inclusion_list.sealed_bundles` from the response, subject to
  `len(sealed_transactions) + len(sealed_bundles) <= MAX_ST_COMMITS_PER_IL`.

The signing and broadcast follow Heze unchanged.

### PTC key timeliness vote

A validator that is a member of the PTC for the current slot MUST cast a
`SignedLucidKeyTimelinessVote` covering the keys for ST-commitments
scheduled in the previous slot, in addition to the existing payload
timeliness attestation.

The vote is broadcast on the `lucid_key_timeliness_vote` gossip topic
by `get_lucid_key_vote_due_ms()` milliseconds into the slot.

#### New `get_lucid_key_timeliness_vote_signature`

```python
def get_lucid_key_timeliness_vote_signature(
    state: BeaconState,
    vote: LucidKeyTimelinessVote,
    privkey: int,
) -> BLSSignature:
    domain = get_domain(
        state,
        DOMAIN_LUCID_KEY_TIMELINESS,
        compute_epoch_at_slot(Slot(vote.voting_slot)),
    )
    signing_root = compute_signing_root(vote, domain)
    return bls.Sign(privkey, signing_root)
```

#### Constructing the `SignedLucidKeyTimelinessVote`

The PTC member constructs the vote as follows. Let `scheduling_block` be
the beacon block of the previous slot.

- Set `message.chain_id` to the local chain identifier.
- Set `message.voting_slot` to the current slot.
- Set `message.validator_index` to the validator's index.
- Set `message.scheduling_beacon_block_root` to
  `hash_tree_root(scheduling_block)`.
- Set `message.scheduling_slot` to `scheduling_block.slot`.
- Set `message.keys_observed` to a `Bitlist[MAX_ST_COMMITS]` of length
  equal to the number of ST-commitments in the scheduling block's
  `ExecutionPayloadBid.st_commitments`, with bit `j` set to `1` if and
  only if the validator observed a valid `LucidKeyMessage` for
  `(scheduling_beacon_block_root, scheduling_slot, commit_index=j)` by
  `get_lucid_key_message_due_ms()`.

The validator obtains the signature via
[`get_lucid_key_timeliness_vote_signature`](#new-get_lucid_key_timeliness_vote_signature),
assembles `signed_vote = SignedLucidKeyTimelinessVote(message=vote,
signature=signature)`, and broadcasts it on the
`lucid_key_timeliness_vote` global gossip topic.

### Block and sidecar proposal

#### Modified `prepare_execution_payload`

*Note*: Extends the Heze definition by passing the ST-commitments
adhered to in the previous slot and the set of observed key messages
into `PayloadAttributes`.

```python
def prepare_execution_payload(
    store: Store,
    head: ForkChoiceNode,
    state: BeaconState,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    suggested_fee_recipient: ExecutionAddress,
    target_gas_limit: uint64,
    execution_engine: ExecutionEngine,
) -> Optional[PayloadId]:
    parent_bid = state.latest_execution_payload_bid
    if should_build_on_full(store, head):
        envelope = store.payloads[head.root]
        state = copy(state)
        apply_parent_execution_payload(state, envelope.execution_requests)
        withdrawals = get_expected_withdrawals(state).withdrawals
        head_block_hash = parent_bid.block_hash
    else:
        withdrawals = state.payload_expected_withdrawals
        head_block_hash = parent_bid.parent_block_hash

    payload_attributes = PayloadAttributes(
        timestamp=compute_time_at_slot(state, state.slot),
        prev_randao=get_randao_mix(state, get_current_epoch(state)),
        suggested_fee_recipient=suggested_fee_recipient,
        withdrawals=withdrawals,
        parent_beacon_block_root=hash_tree_root(state.latest_block_header),
        slot_number=state.slot,
        target_gas_limit=target_gas_limit,
        inclusion_list_transactions=get_inclusion_list_transactions(
            get_inclusion_list_store(), state, Slot(state.slot - 1), only_timely=False
        ),
        # [New in EIP8184]
        scheduled_st_commitments=parent_bid.st_commitments,
        # [New in EIP8184]
        observed_key_messages=get_observed_key_messages_for(
            get_lucid_key_timeliness_store(),
            scheduling_beacon_block_root=hash_tree_root(state.latest_block_header),
        ),
    )
    return execution_engine.notify_forkchoice_updated(
        head_block_hash=head_block_hash,
        safe_block_hash=safe_block_hash,
        finalized_block_hash=finalized_block_hash,
        payload_attributes=payload_attributes,
    )
```
