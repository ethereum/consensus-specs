# EIP-9999 -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Table of contents](#table-of-contents)
- [Introduction](#introduction)
- [Modifications in EIP-9999](#modifications-in-eip-9999)
  - [Containers](#containers)
    - [Modified `SignedExecutionPayloadEnvelopes`](#modified-signedexecutionpayloadenvelopes)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [Removed `ExecutionPayloadEnvelopesByRange v1`](#removed-executionpayloadenvelopesbyrange-v1)

<!-- mdformat-toc end -->

## Introduction

This document contains the consensus-layer networking specifications for
EIP-9999.

`ExecutionPayloadEnvelopesByRange v1` exists to serve historical execution
payload envelopes for backfill. EIP-9999 removes the reason to fetch them: a
consensus client verifies a synced range against the payload request chain
rather than against the payloads themselves, so it never needs the envelopes it
would have requested.

Leaving the method in place while removing its purpose would put the network in
the worst of both positions. Clients could skip the download, but would still be
expected to serve it, and a client that skipped could not. The method is
therefore removed rather than left as an obligation no one can meet.

`ExecutionPayloadEnvelopesByRoot v1` is unaffected. It serves the range
`[max(GLOAS_FORK_EPOCH, current_epoch - compute_min_epochs_for_block_requests()), current_epoch]`,
so every envelope it returns arrived on gossip and is held locally. It also
answers a question this EIP does not address — whether a payload was revealed at
all — which drives payload attestation processing and fork choice.

## Modifications in EIP-9999

### Containers

#### Modified `SignedExecutionPayloadEnvelopes`

Unchanged except that its documentation no longer refers to the removed method.

```python
class SignedExecutionPayloadEnvelopes(List[SignedExecutionPayloadEnvelope]):
    """
    Signed execution payload envelopes returned in an
    ``ExecutionPayloadEnvelopesByRoot`` response.
    """

    LIMIT = MAX_REQUEST_PAYLOADS
```

### The Req/Resp domain

#### Messages

##### Removed `ExecutionPayloadEnvelopesByRange v1`

The protocol ID `/eth2/beacon_chain/req/execution_payload_envelopes_by_range/1/`
is removed.

Client software MUST NOT send this request, and MAY respond to it with error
code `1: InvalidRequest`.

Historical execution payloads remain available from the execution layer, which
holds them as blocks and serves them over its own protocols. Consumers that need
a historical payload obtain it there rather than from the beacon network, which
retains only the commitments.

*Note*: `MAX_REQUEST_PAYLOADS` and `SignedExecutionPayloadEnvelopes` are both
retained, as `ExecutionPayloadEnvelopesByRoot v1` continues to use them.

*Note*: the beacon API's `getSignedExecutionPayloadEnvelope` accepts any
`block_id`, so it can be asked for historical envelopes. With this method
removed it becomes best-effort: a node answers from what it holds locally, and
returns not-found for blocks whose envelopes it never downloaded. Consumers
needing historical execution data should query an execution client, which holds
the payload as a block.
