# `beacon-chain.md` Template

# <FORK_NAME> -- The Beacon Chain

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->



## Introduction

## Notation

## Custom types

## Constants

### [CATEGORY OF CONSTANTS]

| Name | Value |
| - | - |
| `<CONSTANT_NAME>` | `<VALUE>`` |

## Preset


### [CATEGORY OF PRESETS]

| Name | Value |
| - | - |
| `<PRESET_FIELD_NAME>` | `<VALUE>` |

## Configuration

### [CATEGORY OF CONFIGURATIONS]

| Name | Value |
| - | - |
| `<CONFIGURATION_FIELD_NAME>` | `<VALUE>` |

## Containers

### [CATEGORY OF CONTAINERS]

#### `CONTAINER_NAME`

```python
class CONTAINER_NAME(Container):
    FILED_NAME: SSZ_TYPE
```

## Helper functions

### [CATEGORY OF HELPERS]

```python
<PYTHON HELPER FUNCTION>
```

### Epoch processing


### Block processing

    

    
## Testing

*Note*: The function `initialize_beacon_state_from_eth1` is modified for pure <FORK_NAME> testing only.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    ...
```
