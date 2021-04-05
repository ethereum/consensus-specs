<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Ethereum 2.0 Altair - Beacon chain light client](#ethereum-20-altair---beacon-chain-light-client)
  - [Specs](#specs)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Ethereum 2.0 Altair - Beacon chain light client

The beacon chain light client protocol is an extra protocol for light clients and servers to communicate.
We expect the beacon nodes that fully sync and verify the latest beacon state to serve as the servers while the light clients only have to download a partial of the beacon state from the servers.

In the current simple design, the light client only sync to the latest finalized beacon chain head so there should be no reorganization.
The reorganizable light client design is still in active R&D.

## Specs

- [P2P Networking](./p2p-interface.md): the Req/Resp message formats for light client communications
- [Sync Protocol](./sync-protocol.md): the detailed sync protocol
