# EIP-8334 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Containers](#containers)
  - [New `AttestationBundle`](#new-attestationbundle)
  - [New `CommitteeAttestationPartsMetadata`](#new-committeeattestationpartsmetadata)
- [Bundled attestation protocol](#bundled-attestation-protocol)
  - [Partial message group ID](#partial-message-group-id)
  - [Parts metadata](#parts-metadata)
  - [Encoding and decoding responses](#encoding-and-decoding-responses)
- [Receiving and forwarding attestations](#receiving-and-forwarding-attestations)
- [Partial message gossip](#partial-message-gossip)
- [Interaction with `SingleAttestation` gossipsub](#interaction-with-singleattestation-gossipsub)
- [Scoring](#scoring)

<!-- mdformat-toc end -->

## Introduction

This document specifies how attestations are disseminated in a batch, using
gossipsub's
[Partial Message Extension](https://github.com/libp2p/specs/pull/685).

The specification of these changes continues in the same format as the network
specifications of previous upgrades, and assumes them as pre-requisite. In
particular, this document builds on the
[Heze networking specification](../../heze/p2p-interface.md).

## Constants

| Name                               | Value | Description                                                                                             |
| ---------------------------------- | ----- | ------------------------------------------------------------------------------------------------------- |
| `ATTESTATION_BUNDLE_TICK_DURATION` | `20`  | Recommended interval, in milliseconds, at which a client flushes pending attestations to its mesh peers |
| `MAX_ATTESTATIONS_PER_BUNDLE`      | `50`  | Maximum number of attestations in a single `AttestationBundle`                                          |

## Containers

### New `AttestationBundle`

The `AttestationBundle` is a batch of `SingleAttestation`s with their
`attestation_data` field deduplicated.

```python
class AttestationBundle(Container):
    committee_index: CommitteeIndex
    attestation_data: AttestationData
    attester_indices: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]
    signatures: List[BLSSignature, MAX_VALIDATORS_PER_COMMITTEE]
```

`attester_indices` lists the global validator indices of the included
attestations; `signatures[i]` is the signature of validator
`attester_indices[i]`. A bundle MUST NOT list the same validator twice.

### New `CommitteeAttestationPartsMetadata`

Peers inform other peers of the attestations that they already have by sharing
the validator indices of the attestations in the `available` field. Peers can
request attestations by specific validators by using the `requests` field.

```python
class CommitteeAttestationPartsMetadata(Container):
    committee_index: CommitteeIndex
    available: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]
    requests: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]
```

The metadata carries no attestation data: the slot is the partial message group
ID and a validator attests at most once per slot, so `(slot, validator_index)`
fully identifies an attestation.

## Bundled attestation protocol

Gossipsub's
[Partial Message Extension](https://github.com/libp2p/specs/pull/685) can be
used to exchange multiple messages in a batch. The specification here describes
how consensus-layer clients use the Partial Message Extension for broadcasting
attestations as a batch by deduplicating the `attestation_data`.

### Partial message group ID

When sending a partial message, the gossipsub group ID MUST be the SSZ encoded
`Slot` of the attestations (8 bytes, little-endian). All `AttestationBundle` and
`CommitteeAttestationPartsMetadata` entries exchanged within a group MUST be for
attestations of that slot. Clients SHOULD ignore groups whose slot is outside
the attestation propagation window.

### Parts metadata

The parts metadata is encoded with the `CommitteeAttestationPartsMetadata`
container.

### Encoding and decoding responses

All partial messages MUST be encoded and decoded with the `AttestationBundle`
container.

## Receiving and forwarding attestations

On receiving an `AttestationBundle` from a peer, the client SHOULD reconstruct
the `SingleAttestation`s from the `AttestationBundle` and validate the messages
using the `beacon_attestation_{subnet_id}` gossip validation conditions. This is
a reference method to reconstruct `SingleAttestation`s from the
`AttestationBundle`:

```python
def reconstruct_single_attestations(bundle: AttestationBundle) -> Sequence[SingleAttestation]:
    return [
        SingleAttestation(
            committee_index=bundle.committee_index,
            attester_index=bundle.attester_indices[i],
            data=bundle.attestation_data,
            signature=bundle.signatures[i],
        )
        for i in range(len(bundle.attester_indices))
    ]
```

Every `ATTESTATION_BUNDLE_TICK_DURATION`, clients SHOULD publish all the
unforwarded attestations to their mesh peers as `AttestationBundle`s, grouping
them by `(committee_index, attestation_data)`. Clients SHOULD limit an
`AttestationBundle` to a maximum of `MAX_ATTESTATIONS_PER_BUNDLE` attestations.
Clients MAY reject bundles containing more than `MAX_ATTESTATIONS_PER_BUNDLE`
attestations.

Clients MUST retain the attestations for at least 6 seconds after validating
them, so that the advertise, request and serve round trip can complete.

## Partial message gossip

When gossipsub emits gossip for a group (once per gossipsub heartbeat, to its
gossip-selected non-mesh peers), clients SHOULD send those peers the list of
validators they hold attestations from, as one
`CommitteeAttestationPartsMetadata` per committee with the validators in
`available`. As attestations are eagerly pushed in the mesh, clients SHOULD NOT
send metadata to mesh peers.

On receiving a `CommitteeAttestationPartsMetadata`, clients SHOULD send the peer
`AttestationBundle`s with the attestations of the validators requested in
`requests`. Requests are not persistent. They are satisfied immediately or
discarded like gossipsub `IWANT` requests.

On receiving a `CommitteeAttestationPartsMetadata` with an `available` list
which contains validator indices different from the ones the client already
possesses, clients SHOULD request the missing attestations using a
`CommitteeAttestationPartsMetadata` with the `requests` field set to the missing
validator indices. Clients MAY eagerly reply to the peer with the attestations
that the client has and the peer is missing.

## Interaction with `SingleAttestation` gossipsub

Clients MUST treat the partial message path and `SingleAttestation` gossipsub as
one dissemination. An attestation validated from an `AttestationBundle` SHOULD
be forwarded as a `SingleAttestation` to peers that have not negotiated partial
messages. An attestation received as a `SingleAttestation`, or locally produced,
SHOULD be made available on the partial message path.

## Scoring

Clients SHOULD report first messages, valid messages, and invalid messages to
gossipsub for scoring.
