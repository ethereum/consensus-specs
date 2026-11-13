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

`ExecutionPayloadEnvelopesByRange v1` serves historical execution payload
envelopes for backfill. EIP-9999 removes the reason to fetch them, so the method
is removed rather than left as an obligation a client that skipped the download
cannot meet.

`ExecutionPayloadEnvelopesByRoot v1` is unaffected. It is bounded to recent
epochs, so every envelope it returns arrived on gossip, and it answers a
question this EIP does not address: whether a payload was revealed.

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
