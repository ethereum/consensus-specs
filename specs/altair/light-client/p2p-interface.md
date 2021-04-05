# Ethereum Altair Light Client P2P Interface

**Notice**: This document is a work-in-progress for researchers and implementers.

This document contains the networking specification for [minimal light client](./sync-protocol.md).
This document should be viewed as a patch to the [Altair networking specification](./../p2p-interface.md).

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [The Req/Resp domain](#the-reqresp-domain)
  - [Messages](#messages)
    - [GetLightClientSnapshot](#getlightclientsnapshot)
    - [LightClientUpdate](#lightclientupdate)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## The Req/Resp domain

### Messages

#### GetLightClientSnapshot

**Protocol ID:** `/eth2/beacon_chain/req/get_light_client_snapshot/1/`

No Request Content.

Response Content:

```
(
  LightClientSnapshot
)
```

The `LightClientSnapshot` SSZ container defined in [light client sync protocol](./sync-protocol.md#lightclientsnapshot).

#### LightClientUpdate

**Protocol ID:** `/eth2/beacon_chain/req/light_client_update/1/`

Request Content:

```
(
  LightClientUpdate
)
```

No Response Content.

The `LightClientUpdate` SSZ container defined in [light client sync protocol](./sync-protocol.md#lightclientupdate).
