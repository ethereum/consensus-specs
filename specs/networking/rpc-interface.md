ETH 2.0 Networking Spec - RPC Interface
===

# Abstract

The Ethereum 2.0 networking stack uses two modes of communication: a broadcast protocol that gossips information to interested parties via GossipSub, and an RPC protocol that retrieves information from specific clients. This specification defines the RPC protocol.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL", NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED",  "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

# Dependencies

This specification assumes familiarity with the [Messaging](./messaging.md), [Node Identification](./node-identification.md), and [Beacon Chain](../core/0_beacon-chain.md) specifications.

# Specification

## Message Schemas

Message body schemas are notated like this:

```
(
    field_name_1: type
    field_name_2: type
)
```

Embedded types are serialized as SSZ Containers unless otherwise noted.

All referenced data structures can be found in the [0-beacon-chain](../core/0_beacon-chain.md#data-structures) specification.

## `libp2p` Protocol Names

A "Protocol ID" in `libp2p` parlance refers to a human-readable identifier `libp2p` uses in order to identify sub-protocols and stream messages of different types over the same connection. Peers exchange supported protocol IDs via the `Identify` protocol upon connection. When opening a new stream, peers pin a particular protocol ID to it, and the stream remains contextualised thereafter. Since messages are sent inside a stream, they do not need to bear the protocol ID.

## RPC-Over-`libp2p`

To facilitate RPC-over-`libp2p`, a single protocol name is used: `/eth/serenity/beacon/rpc/1`. The version number in the protocol name is neither backwards or forwards compatible, and will be incremented whenever changes to the below structures are required.

Remote method calls are wrapped in a "request" structure:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                          id (uint64)                          +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       method_id (uint16)      |       body_len (uint32)       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                               |     body (body_len bytes)     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

and their corresponding responses are wrapped in a "response" structure:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                          id (uint64)                          +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|     response_code (uint16)    |      result_len (uint32)      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                               |   result (result_len bytes)   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

Note that the above structures are NOT encoded as SSZ but rather as sequences of bytes according to the packet diagrams above. This is because SSZ does not support structures without an explicit schema. Since the `body` and `result` fields depend on the value of `method_id` and `response_code`, a schema for the above structure cannot be known beforehand.

The details of the RPC-Over-`libp2p` protocol are similar to [JSON-RPC 2.0](https://www.jsonrpc.org/specification). Specifically:

1. The `id` member is REQUIRED.
2. The `id` member in the response MUST be the same as the value of the `id` in the request.
3. The `id` member MUST be unique within the context of a single connection. Monotonically increasing `id`s are RECOMMENDED.
4. The `method_id` member is REQUIRED.
5. The `result` member is REQUIRED on success.
6. The `result` member is OPTIONAL on errors, and MAY contain additional information about the error.
7. `response_code` MUST be `0` on success.

Structuring RPC requests in this manner allows multiple calls and responses to be multiplexed over the same stream without switching. Note that this implies that responses MAY arrive in a different order than requests.

The "method ID" fields in the below messages refer to the `method` field in the request structure above.

The first 1,000 values in `response_code` are reserved for system use. The following response codes are predefined:

1. `0`: No error.
2. `10`: Parse error.
2. `20`: Invalid request.
3. `30`: Method not found.
4. `40`: Server error.

### Alternative for Non-`libp2p` Clients

Since some clients are waiting for `libp2p` implementations in their respective languages. As such, they MAY listen for raw TCP messages on port `9000`. To distinguish RPC messages from other messages on that port, a byte prefix of `ETH` (`0x455448`) MUST be prepended to all messages. This option will be removed once `libp2p` is ready in all supported languages.

## Messages

### Hello

**Method ID:** `0`

**Body**:

```
(
    network_id: uint8
    chain_id: uint64
    latest_finalized_root: bytes32
    latest_finalized_epoch: uint64
    best_root: bytes32
    best_slot: uint64
)
```

Clients exchange `hello` messages upon connection, forming a two-phase handshake. The first message the initiating client sends MUST be the `hello` message. In response, the receiving client MUST respond with its own `hello` message.

Clients SHOULD immediately disconnect from one another following the handshake above under the following conditions:

1. If `network_id` belongs to a different chain, since the client definitionally cannot sync with this client.
2. If the `latest_finalized_root` shared by the peer is not in the client's chain at the expected epoch. For example, if Peer 1 in the diagram below has `(root, epoch)` of `(A, 5)` and Peer 2 has `(B, 3)`, Peer 1 would disconnect because it knows that `B` is not the root in their chain at epoch 3:

```
              Root A

              +---+
              |xxx|  +----+ Epoch 5
              +-+-+
                ^
                |
              +-+-+
              |   |  +----+ Epoch 4
              +-+-+
Root B          ^
                |
+---+         +-+-+
|xxx+<---+--->+   |  +----+ Epoch 3
+---+    |    +---+
         |
       +-+-+
       |   |  +-----------+ Epoch 2
       +-+-+
         ^
         |
       +-+-+
       |   |  +-----------+ Epoch 1
       +---+
```

Once the handshake completes, the client with the higher `latest_finalized_epoch` or `best_slot` (if the clients have equal `latest_finalized_epoch`s) SHOULD request beacon block roots from its counterparty via `beacon_block_roots` (i.e., RPC method `10`).

### Goodbye

**Method ID:** `1`

**Body:**

```
(
    reason: uint64
)
```

Client MAY send `goodbye` messages upon disconnection. The reason field MAY be one of the following values:

- `1`: Client shut down.
- `2`: Irrelevant network.
- `3`: Fault/error.

Clients MAY define custom goodbye reasons as long as the value is larger than `1000`.

### Get Status

**Method ID:** `2`

**Request Body:**

```
(
	sha: bytes32
	user_agent: bytes
	timestamp: uint64
)
```

**Response Body:**

```
(
	sha: bytes32
	user_agent: bytes
	timestamp: uint64
)
```

Returns metadata about the remote node.

### Request Beacon Block Roots

**Method ID:** `10`

**Request Body**

```
(
	start_slot: uint64
	count: uint64
)
```

**Response Body:**

```
# BlockRootSlot
(
    block_root: bytes32
    slot: uint64
)

(
    roots: []BlockRootSlot
)
```

Requests a list of block roots and slots from the peer. The `count` parameter MUST be less than or equal to `32768`. The slots MUST be returned in ascending slot order.

### Beacon Block Headers

**Method ID:** `11`

**Request Body**

```
(
    start_root: HashTreeRoot
    start_slot: uint64
    max_headers: uint64
    skip_slots: uint64
)
```

**Response Body:**

```
(
    headers: []BeaconBlockHeader
)
```

Requests beacon block headers from the peer starting from `(start_root, start_slot)`. The response MUST contain no more than `max_headers` headers. `skip_slots` defines the maximum number of slots to skip between blocks. For example, requesting blocks starting at slots `2` a `skip_slots` value of `1` would return the blocks at `[2, 4, 6, 8, 10]`. In cases where a slot is empty for a given slot number, the closest previous block MUST be returned. For example, if slot `4` were empty in the previous example, the returned array would contain `[2, 3, 6, 8, 10]`. If slot three were further empty, the array would contain `[2, 6, 8, 10]` - i.e., duplicate blocks MUST be collapsed. A `skip_slots` value of `0` returns all blocks.

The function of the `skip_slots` parameter helps facilitate light client sync - for example, in [#459](https://github.com/ethereum/eth2.0-specs/issues/459) - and allows clients to balance the peers from whom they request headers. Clients could, for instance, request every 10th block from a set of peers where each per has a different starting block in order to populate block data.

### Beacon Block Bodies

**Method ID:** `12`

**Request Body:**

```
(
    block_roots: []HashTreeRoot
)
```

**Response Body:**

```
(
    block_bodies: []BeaconBlockBody
)
```

Requests the `block_bodies` associated with the provided `block_roots` from the peer. Responses MUST return `block_roots` in the order provided in the request. If the receiver does not have a particular `block_root`, it must return a zero-value `block_body` (i.e., a `block_body` container with all zero fields).

### Beacon Chain State

**Note:** This section is preliminary, pending the definition of the data structures to be transferred over the wire during fast sync operations.

**Method ID:** `13`

**Request Body:**

```
(
    hashes: []HashTreeRoot
)
```

**Response Body:** TBD

Requests contain the hashes of Merkle tree nodes that when merkelized yield the block's `state_root`.

The response will contain the values that, when hashed, yield the hashes inside the request body.
