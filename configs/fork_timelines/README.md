# Fork timelines

This directory contains a set of fork timelines used for testing, testnets, and mainnet.

A timeline file contains all the forks known for its target.
Later forks can be ignored, e.g. ignore fork `phase1` as a client that only supports phase 0 currently.

## Format

Each preset is a key-value mapping.

**Key**: an `lower_snake_case` (a.k.a. "python case") formatted string, name of the fork.
**Value**: an unsigned integer number, epoch number of activation of the fork

Timelines may contain comments to describe the values.

See `mainnet.yaml` for a complete example.

