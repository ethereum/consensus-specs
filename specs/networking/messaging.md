# Eth 2.0 Networking Spec - Minimal Messaging

## Abstract

This specification describes how individual Ethereum 2.0 messages are represented on the
wire.

The key words “MUST”, “MUST NOT”, “REQUIRED”, “SHALL”, “SHALL”, NOT", “SHOULD”, “SHOULD
NOT”, “RECOMMENDED”, “MAY”, and “OPTIONAL” in this document are to be interpreted as
described in [RFC 2119](https://tools.ietf.org/html/rfc2119).

## Motivation

This specification defines a minimal transport protocol which can be used for client
interoperability testing.

The Ethereum 2.0 networking stack uses two modes of communication: a broadcast protocol
that gossips information to interested parties, and an RPC protocol that retrieves
information from specific clients. This specification defines the carrier for both
application protocols.

## Specification

### Message structure

An Eth 2.0 message consists of an envelope that defines the message's command by name, and
a body which is specific to the message. Visually, a message looks like this:

```text
+--------------------------+
|  command length (uint16) |
+--------------------------+
|  command                 |
+--------------------------+
|  body length (uint64)    |
+--------------------------+
|  body                    |
+--------------------------+
```

### Gossip

Implementations should include a simple boadcast facility. If a message with the "GOSSIP"
command is received, the message must be passed on to all connected peers. Implementations
should track recently sent messages (e.g. by keeping a set of message hashes) to avoid
sending the same message more than once.
