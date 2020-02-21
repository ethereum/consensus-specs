# Ethereum 2.0 Phase 2 -- Execution in Shard Transitions

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [Introduction](#introduction)
- [Proposals](#proposals)
- [Shard state transition function](#shard-state-transition-function)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->


## Introduction

This document describes the shard transition function as part of Phase 2 of Ethereum 2.0.


## Proposals

```python
def make_empty_proposal(shard: Shard,
                        slot: Slot,
                        shard_state: ShardState,
                        previous_beacon_root: Root,
                        proposer_pubkey: BLSPubkey):
    # We will add something more substantive in phase 2
    return ByteList[MAX_SHARD_BLOCK_SIZE]()  # empty byte list
```

```python
def get_shard_transactions(shard: Shard,
                           slot: Slot,
                           shard_state: ShardState,
                           previous_beacon_root: Root,
                           proposer_pubkey: BLSPubkey) -> Sequence[EETransaction]:
    # Up to the proposer to collect transactions as it likes (based on EE preference, abstracted fee payments, etc.)
    return []  # Placeholder
```

```python
class ExecutionEnvironment(Protocol):
    def init_witness(self,
                     shard: Shard,
                     slot: Slot,
                     shard_state: ShardState,
                     previous_beacon_root: Root,
                     proposer_pubkey: BLSPubkey) -> ByteList[MAX_EE_WITNESS_SIZE]:
        ...

    # Add witness data to the state. Do not overwrite any branches, items, etc. in the witness if the first EE call has priority.
    def merge_witness(self, prev:  ByteList[MAX_EE_WITNESS_SIZE], addition: ByteList[MAX_TRANSACTION_WITNESS_SIZE]):
        ...

    # False if witness_data is invalid for given ee_state_root.
    # (i.e. witness verification bubbles up an exception / error return)
    def verify_witness(self, ee_state_root: Root, witness_data: ByteList[MAX_TRANSACTION_WITNESS_SIZE]) -> bool:
        ...

    # Prepare an EE runner that is loaded with the given EE state witness. 
    def prepare_runner(self, witness_data: ByteList[MAX_TRANSACTION_WITNESS_SIZE]) -> EnvironmentRunner:
        ...
```

```python
class EnvironmentHost(Protocol):
    def cross_ee_call(self, EECall) -> bool:
        ...
    def slot(self) -> Slot:
        ...
    # TODO: other EE host functions
```

```python
class EnvironmentRunner(Protocol):
    # Make a call. If failing, return false and rollback state to its contents from before this call. 
    def make_call(self, call_data: ByteList[MAX_TRANSACTION_CALL_SIZE], host: EnvironmentHost) -> bool:
        ...
    # Return the latest state root
    def ee_state_root(self) -> Root:
        ...
```

```python
EXECUTION_ENVIRONMENTS = {
    0: ETH_1_ENVIRONMENT,
    1: CORE_ENV,
    # And future environments for (ZK) rollup, UTXO, and more.
}
```

```python
def make_shard_data_proposal(shard: Shard,
                             slot: Slot,
                             shard_state: ShardState,
                             previous_beacon_root: Root,
                             proposer_pubkey: BLSPubkey) -> ByteList[MAX_SHARD_BLOCK_SIZE]:
    block_contents = ShardBlockContents()
    for tx in get_shard_transactions(shard, slot, shard_state, previous_beacon_root, proposer_pubkey):
        assert tx.shard == shard
    
        for ee_witness in tx.witnesses:
            # Init a witness for the EE if it does not exist yet.
            ee = EXECUTION_ENVIRONMENTS[ee_witness.ee_index]
            if ee_index not in block_contents.ee_witnesses:
                block_contents.ee_witnesses[ee_witness.ee_index] = ee.init_witness(shard, slot, shard_state, previous_beacon_root, proposer_pubkey)

            # Merge the witness (EEs can choose to anything between pure aggregation and simple enumeration)        
            block_contents.ee_witnesses[ee_witness.ee_index] = ee.merge_witness(block_contents.ee_witnesses[ee_witness.ee_index], ee_witness.witness)

        # Add Call
        block_contents.ee_calls.append(EECall(ee_index=tx.ee_index, call_data=tx.call_data))

    # TODO: serialization is not ideal for transparent merkle-proofs into data per shard block.
    # Maybe change custody game to construct bits from a list of bytelists instead?
    return serialize(block_contents)
```

## Shard state transition function

```python
def shard_state_transition(shard: Shard,
                           slot: Slot,
                           shard_state: ShardState,
                           previous_beacon_root: Root,
                           proposer_pubkey: BLSPubkey,
                           block_data: ByteList[MAX_SHARD_BLOCK_SIZE]):    
    # We will add something more substantive in phase 2
    shard_state.shard_parent_root = hash_tree_root(shard_state)

    block_contents = ShardBlockContents.deserialize(bytes(block_data))
    
    # Verify witnesses against EE state roots
    for ee_index, ee_witness in block_contents.ee_witnesses.items():
        # Witnesses must be aggregated, do not run a call on an EE with multiple different witnesses
        assert ee_index not in environment_runners

        ee_root = shard_state.shard_state_contents.ee_roots[ee_index]
        assert EXECUTION_ENVIRONMENTS[ee_index].verify_witness(ee_root, ee_witness)

    # Collect EE runners: prepared witness state to run EE with
    environment_runners = {}
    for ee_index, ee_witness in block_contents.ee_witnesses.items():
        # Runner preparation aborts the state-transition if the witness data is invalid for the given state root.
        environment_runners[ee_index] = EXECUTION_ENVIRONMENTS[ee_index].prepare_runner(ee_witness)
    
    # Create and initialize a host for the execution.
    class TransitionHost(EnvironmentHost):
        def cross_ee_call(self, ee_call: EECall) -> bool:
                return environment_runners[ee_call.ee_index].make_call(ee_call.call_data, self)

        def slot(self) -> Slot:
            return shard_state.slot
    
    host = TransitionHost()

    # Run all EE calls, using the host
    for ee_call in block_contents.ee_calls:
        host.run_ee_call(ee_call)

    # Update EE roots
    for ee_index in block_contents.ee_witnesses.keys():
        shard_state.shard_state_contents.ee_roots[ee_index] = environment_runners[ee_index].ee_state_root()
    
    # Update shard slot
    shard_state.slot += 1
```
