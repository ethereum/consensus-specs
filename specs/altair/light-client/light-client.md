# Altair Light Client -- Light Client

## Table of contents

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Light client sync process](#light-client-sync-process)

<!-- mdformat-toc end -->

## Introduction

This document explains how light clients MAY obtain light client data to sync with the network.

## Light client sync process

1. The light client MUST be configured out-of-band with a spec/preset (including fork schedule), with `genesis_state` (including `genesis_time` and `genesis_validators_root`), and with a trusted block root. The trusted block SHOULD be within the weak subjectivity period, and its root SHOULD be from a finalized `Checkpoint`.
2. The local clock is initialized based on the configured `genesis_time`, and the current fork digest is determined to browse for and connect to relevant light client data providers.
3. The light client fetches a [`LightClientBootstrap`](./sync-protocol.md#lightclientbootstrap) object for the configured trusted block root. The `bootstrap` object is passed to [`initialize_light_client_store`](./sync-protocol.md#initialize_light_client_store) to obtain a local [`LightClientStore`](./sync-protocol.md#lightclientstore).
4. The light client tracks the sync committee periods `finalized_period` from `store.finalized_header.beacon.slot`, `optimistic_period` from `store.optimistic_header.beacon.slot`, and `current_period` from `current_slot` based on the local clock.
   1. When `finalized_period == optimistic_period` and [`is_next_sync_committee_known`](./sync-protocol.md#is_next_sync_committee_known) indicates `False`, the light client fetches a [`LightClientUpdate`](./sync-protocol.md#lightclientupdate) for `finalized_period`. If `finalized_period == current_period`, this fetch SHOULD be scheduled at a random time before `current_period` advances.
   2. When `finalized_period + 1 < current_period`, the light client fetches a `LightClientUpdate` for each sync committee period in range `[finalized_period + 1, current_period)` (current period excluded)
   3. When `finalized_period + 1 >= current_period`, the light client keeps observing [`LightClientFinalityUpdate`](./sync-protocol.md#lightclientfinalityupdate) and [`LightClientOptimisticUpdate`](./sync-protocol.md#lightclientoptimisticupdate). Received objects are passed to [`process_light_client_finality_update`](./sync-protocol.md#process_light_client_finality_update) and [`process_light_client_optimistic_update`](./sync-protocol.md#process_light_client_optimistic_update). This ensures that `finalized_header` and `optimistic_header` reflect the latest blocks.
5. [`process_light_client_store_force_update`](./sync-protocol.md#process_light_client_store_force_update) MAY be called based on use case dependent heuristics if light client sync appears stuck. If available, falling back to an alternative syncing mechanism to cover the affected sync committee period is preferred.
