# ePBS -- Honest Validator

**Notice**: This document is a work-in-progress for researchers and implementers.


## Introduction

This document represents the changes to be made in the code of an "honest validator" to implement ePBS.

## Prerequisites

This document is an extension of the Deneb -- Honest Validator guide.
All behaviors and definitions defined in this document, and documents it extends, carry over unless explicitly noted or overridden.

All terminology, constants, functions, and protocol mechanics defined in the updated Beacon Chain doc of ePBS. are requisite for this document and used throughout.
Please see related Beacon Chain doc before continuing and use them as a reference throughout.

## Beacon chain responsibilities

All validator responsibilities remain unchanged other than those noted below. Namely, proposer normal block production switched to using `SignedBeaconBlockWithBid` and attester with an additional duty to submit `ExecutionAttestation`

### Block proposal

#### Constructing the `BeaconBlockBody`

To obtain an signed builder bid, a block proposer building a block on top of a `state` must take the following actions:
* Listen to the `builder_bid` gossip subnet
* Filter the bids where where `bid.header.parent_hash` matches `head.payload.block_hash`
* Select the best bid (the one with the highest value) and set `body.bid = signed_builder_bid`


### Consensus attesting reminds unchanged

### Consensus attestation aggregation reminds unchanged

### Payload timeliness attestation

Some validators are selected to submit payload timeliness attestation. The `committee`, assigned `index`, and assigned `slot` for which the validator performs this role during an epoch are defined by `get_execution_committee(state, slot)`.

A validator should create and broadcast the `execution_attestation` to the global execution attestation subnet at `SECONDS_PER_SLOT * 3 / INTERVALS_PER_SLOT` seconds after the start of `slot`

#### Construct payload timeliness attestation

Next, the validator creates `signed_execution_attestation`
* Set `execution_attestation.slot = slot` where `slot` is the assigned slot.
* Set `execution_attestation.block_hash = block_hash` where `block_hash` is the block hash seen from the block builder reveal at `SECONDS_PER_SLOT * 2 / INTERVALS_PER_SLOT`
* Set `execution_attestation.validator_index = validator_index` where `validator_index` is the validator chosen to submit. The private key mapping to `state.validators[validator_index].pubkey` is used to sign the payload timeliness attestation.
* Set `signed_execution_attestation = SignedExecution(message=execution_attestation, signature=execution_attestation_signature)`, where `execution_attestation_signature` is obtained from:

```python
def get_execution_attestation_signature(state: BeaconState, attestation: ExecutionAttestation, privkey: int) -> BLSSignature:
    domain = get_domain(state, DOMAIN_PAYLOAD_TIMELINESS_COMMITTEE, compute_epoch_at_slot(attestation.slot))
    signing_root = compute_signing_root(attestation, domain)
    return bls.Sign(privkey, signing_root)
```

#### Broadcast execution attestation

Finally, the validator broadcasts `signed_execution_attestation` to the global `execution_attestation` pubsub topic.
