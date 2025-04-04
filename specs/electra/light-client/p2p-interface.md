# Electra Light Client -- Networking

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Networking](#networking)
  - [The gossip domain: gossipsub](#the-gossip-domain-gossipsub)
    - [Topics and messages](#topics-and-messages)
      - [Global topics](#global-topics)
        - [`light_client_finality_update`](#light_client_finality_update)
        - [`light_client_optimistic_update`](#light_client_optimistic_update)
  - [The Req/Resp domain](#the-reqresp-domain)
    - [Messages](#messages)
      - [GetLightClientBootstrap](#getlightclientbootstrap)
      - [LightClientUpdatesByRange](#lightclientupdatesbyrange)
      - [GetLightClientFinalityUpdate](#getlightclientfinalityupdate)
      - [GetLightClientOptimisticUpdate](#getlightclientoptimisticupdate)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Networking

The [Deneb light client networking specification](../../deneb/light-client/p2p-interface.md) is extended to exchange [Electra light client data](./sync-protocol.md).

### The gossip domain: gossipsub

#### Topics and messages

##### Global topics

###### `light_client_finality_update`

[0]: # (eth2spec: skip)

| `fork_version`                                         | Message SSZ type                    |
|--------------------------------------------------------|-------------------------------------|
| `GENESIS_FORK_VERSION`                                 | n/a                                 |
| `ALTAIR_FORK_VERSION` through `BELLATRIX_FORK_VERSION` | `altair.LightClientFinalityUpdate`  |
| `CAPELLA_FORK_VERSION`                                 | `capella.LightClientFinalityUpdate` |
| `DENEB_FORK_VERSION`                                   | `deneb.LightClientFinalityUpdate`   |
| `ELECTRA_FORK_VERSION` and later                       | `electra.LightClientFinalityUpdate` |

###### `light_client_optimistic_update`

[0]: # (eth2spec: skip)

| `fork_version`                                         | Message SSZ type                      |
|--------------------------------------------------------|---------------------------------------|
| `GENESIS_FORK_VERSION`                                 | n/a                                   |
| `ALTAIR_FORK_VERSION` through `BELLATRIX_FORK_VERSION` | `altair.LightClientOptimisticUpdate`  |
| `CAPELLA_FORK_VERSION`                                 | `capella.LightClientOptimisticUpdate` |
| `DENEB_FORK_VERSION`                                   | `deneb.LightClientOptimisticUpdate`   |
| `ELECTRA_FORK_VERSION` and later                       | `electra.LightClientOptimisticUpdate` |

### The Req/Resp domain

#### Messages

##### GetLightClientBootstrap

[0]: # (eth2spec: skip)

| `fork_version`                                         | Response SSZ type                  |
|--------------------------------------------------------|------------------------------------|
| `GENESIS_FORK_VERSION`                                 | n/a                                |
| `ALTAIR_FORK_VERSION` through `BELLATRIX_FORK_VERSION` | `altair.LightClientBootstrap`      |
| `CAPELLA_FORK_VERSION`                                 | `capella.LightClientBootstrap`     |
| `DENEB_FORK_VERSION`                                   | `deneb.LightClientBootstrap`       |
| `ELECTRA_FORK_VERSION` and later                       | `electra.LightClientBootstrap`     |

##### LightClientUpdatesByRange

[0]: # (eth2spec: skip)

| `fork_version`                                         | Response chunk SSZ type          |
|--------------------------------------------------------|----------------------------------|
| `GENESIS_FORK_VERSION`                                 | n/a                              |
| `ALTAIR_FORK_VERSION` through `BELLATRIX_FORK_VERSION` | `altair.LightClientUpdate`       |
| `CAPELLA_FORK_VERSION`                                 | `capella.LightClientUpdate`      |
| `DENEB_FORK_VERSION`                                   | `deneb.LightClientUpdate`        |
| `ELECTRA_FORK_VERSION` and later                       | `electra.LightClientUpdate`      |

##### GetLightClientFinalityUpdate

[0]: # (eth2spec: skip)

| `fork_version`                                         | Response SSZ type                   |
|--------------------------------------------------------|-------------------------------------|
| `GENESIS_FORK_VERSION`                                 | n/a                                 |
| `ALTAIR_FORK_VERSION` through `BELLATRIX_FORK_VERSION` | `altair.LightClientFinalityUpdate`  |
| `CAPELLA_FORK_VERSION`                                 | `capella.LightClientFinalityUpdate` |
| `DENEB_FORK_VERSION`                                   | `deneb.LightClientFinalityUpdate`   |
| `ELECTRA_FORK_VERSION` and later                       | `electra.LightClientFinalityUpdate` |

##### GetLightClientOptimisticUpdate

[0]: # (eth2spec: skip)

| `fork_version`                                         | Response SSZ type                     |
|--------------------------------------------------------|---------------------------------------|
| `GENESIS_FORK_VERSION`                                 | n/a                                   |
| `ALTAIR_FORK_VERSION` through `BELLATRIX_FORK_VERSION` | `altair.LightClientOptimisticUpdate`  |
| `CAPELLA_FORK_VERSION`                                 | `capella.LightClientOptimisticUpdate` |
| `DENEB_FORK_VERSION`                                   | `deneb.LightClientOptimisticUpdate`   |
| `ELECTRA_FORK_VERSION` and later                       | `electra.LightClientOptimisticUpdate` |
