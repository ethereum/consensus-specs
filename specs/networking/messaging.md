ETH 2.0 Networking Spec - Messaging
===

# Abstract

This specification describes how individual Ethereum 2.0 messages are represented on the wire.

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL”, NOT", “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in RFC 2119.

# Motivation

This specification seeks to define a messaging protocol that is flexible enough to be changed easily as the ETH 2.0 specification evolves.

# Specification

## Message Structure

An ETH 2.0 message consists of a single byte representing the message version followed by the encoded, potentially compressed body. We separate the message's version from the version included in the `libp2p` protocol path in order to allow encoding and compression schemes to be updated independently of the `libp2p` protocols themselves.

It is unlikely that more than 255 message versions will need to be supported, so a single byte should suffice.

Visually, a message looks like this:

```
+--------------------------+
|    version byte          |
+--------------------------+
|                          |
|           body           |
|                          |
+--------------------------+
```

Clients MUST ignore messages with mal-formed bodies. The `version` byte MUST be one of the below values:

## Version Byte Values

### `0x01`

- **Encoding Scheme:** SSZ
- **Compression Scheme:** Snappy
