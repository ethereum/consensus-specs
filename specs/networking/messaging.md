ETH 2.0 Networking Spec - Messaging
===

# Abstract

This specification describes how individual Ethereum 2.0 messages are represented on the wire.

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL”, NOT", “SHOULD”, “SHOULD NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as described in RFC 2119.

# Motivation

This specification seeks to define a messaging protocol that is flexible enough to be changed easily as the ETH 2.0 specification evolves.

# Specification

## Message Structure

An ETH 2.0 message consists of an envelope that defines the message's compression, encoding, and length followed by the body itself.

Visually, a message looks like this:

```
+--------------------------+
|    compression nibble    |
+--------------------------+
|    encoding nibble       |
+--------------------------+
|  body length (uint64)    |
+--------------------------+
|                          |
|           body           |
|                          |
+--------------------------+
```

Clients MUST ignore messages with mal-formed bodies. The compression/encoding nibbles MUST be one of the following values:

## Compression Nibble Values

- `0x0`: no compression

## Encoding Nibble Values

- `0x1`: SSZ
