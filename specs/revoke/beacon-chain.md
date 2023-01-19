# Revoke-pubkey-change -- The Beacon Chain

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Domain types](#domain-types)
- [Preset](#preset)
  - [Max operations per block](#max-operations-per-block)
  - [Execution](#execution)
- [Containers](#containers)
    - [`Withdrawal`](#withdrawal)
    - [`BLSToExecutionChange`](#blstoexecutionchange)
    - [`SignedBLSToExecutionChange`](#signedblstoexecutionchange)
  - [New containers](#new-containers)
    - [`PubKeyChange`](#PubKeyChange)
  - [Extended Containers](#extended-containers)
    - [`ExecutionPayload`](#executionpayload)
    - [`ExecutionPayloadHeader`](#executionpayloadheader)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
- [Helpers](#helpers)
  - [Predicates](#predicates)
    - 
    - [`has_eth1_withdrawal_credential`](#has_eth1_withdrawal_credential)
    - [`is_fully_withdrawable_validator`](#is_fully_withdrawable_validator)
    - [`is_partially_withdrawable_validator`](#is_partially_withdrawable_validator)
- [Beacon chain state transition function](#beacon-chain-state-transition-function)
  - [Block processing](#block-processing)
    - [`get_expected_withdrawals`](#new-get_expected_withdrawals)
    - [`process_withdrawals`](#new-process_withdrawals)
    - [Modified `process_execution_payload`](#modified-process_execution_payload)
    - [Modified `process_operations`](#modified-process_operations)
    - [`process_bls_to_execution_change`](#new-process_bls_to_execution_change)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction
Revoke-pubkey-change (aka REVOKE) is a proposed consensus-layer upgrade containing a new feature allowing validators to change their signing key (pubkey).

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `PubKeyChangeIndex` | `uint64` | an index of a `PubKeyChange` |

## Constants

### Domain types

## Preset

### Max operations per block

### Execution

## Containers

### New containers

#### `PubKeyChange`
```python

class PubKeyChange(Container):
    index: PubKeyChangeIndex
    validator_index: ValidatorIndex
    address: BLSPubkey 
```

<!--Since the REVOKE will be building upon the CAPELLA, the BLS_TO_EXECUTION_CHANGE message (used for changing the PoS PREFIX WITHDRAWAL credential to ETH1 Address - execution address) can be used to initiate PubKey Change-->
<!--We can assume all the validators will be using ETH1 withdrawal credentials -->

<!--The BLS_TO_EXECUTION_CHANGE can already enable changing the withdrawal credentials from using the POS withdrawal key to using the ETH1 address destination. Therefore creating a new xxToExecutionChange message is not required -->

<!--BLS_TO_EXECUTION_CHANGE is the message for changing the old POS PREFIX WITHDRAWAL credential to ETH1 withdrawal credentials-->

<!--For REVOKE we can assume using ETH1 withdrawal credentials - ETH1 address is what we need to use to initate the PubKey-Change -->

### Extended Containers

#### `ExecutionPayload`

```python
class ExecutionPayload(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress  # 'beneficiary' in the yellow paper
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32  # 'difficulty' in the yellow paper
    block_number: uint64  # 'number' in the yellow paper
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions: List[Transaction, MAX_TRANSACTIONS_PER_PAYLOAD]
    withdrawals: List[Withdrawal, MAX_WITHDRAWALS_PER_PAYLOAD]  # [New in Capella]
    #pubkeychanges: List[PubKeyChange, MAX_PUBKEY_CHANGE_PER_PAYLOAD] # [New in Revoke] Note: Not required as PubKey-change will not need to make change in the Execution Layer (EL) state change in the execution payload.
```

#### `ExecutionPayloadHeader`

```python
class ExecutionPayloadHeader(Container):
    # Execution block header fields
    parent_hash: Hash32
    fee_recipient: ExecutionAddress
    state_root: Bytes32
    receipts_root: Bytes32
    logs_bloom: ByteVector[BYTES_PER_LOGS_BLOOM]
    prev_randao: Bytes32
    block_number: uint64
    gas_limit: uint64
    gas_used: uint64
    timestamp: uint64
    extra_data: ByteList[MAX_EXTRA_DATA_BYTES]
    base_fee_per_gas: uint256
    # Extra payload fields
    block_hash: Hash32  # Hash of execution block
    transactions_root: Root
    withdrawals_root: Root  # [New in Capella]
    #pubkeychanges_root: Root # [New in Revoke] Note: Also don't need the root here
```

#### `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload
    # Capella operations
    bls_to_execution_changes: List[SignedBLSToExecutionChange, MAX_BLS_TO_EXECUTION_CHANGES]  # [New in Capella]
```

#### `BeaconState`
```python

class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Bytes32, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Participation
    previous_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    current_epoch_participation: List[ParticipationFlags, VALIDATOR_REGISTRY_LIMIT]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Inactivity
    inactivity_scores: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    # Sync
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Execution
    latest_execution_payload_header: ExecutionPayloadHeader
    # Withdrawals
    next_withdrawal_index: WithdrawalIndex  # [New in Capella]
    next_withdrawal_validator_index: ValidatorIndex  # [New in Capella]
    #Pubkey-change
    next_pubkeychange_index: PubKeyChangeIndex # [New in Revoke]
    next_pubkeychange_validator_index: ValidatorIndex  # [New in Revoke]
```

## Helpers

### Predicates

#### `is_pubkey_changable`

```python
def is_pubkey_changable(validator: Validator, epoch: Epoch, newpubkey: BLSPubkey) -> bool: # [New in Revoke]
    """
    Check if ``validator`` signing key can be changed.
    """

    return (
        has_eth1_withdrawal_credential(validator)
        and validator.pubkey_change_epoch <= epoch
        and validator.pubkey != validator.newpubkey ) #Define a newpubkey object

        #TODO: Review with mentors if additional checks are required.

        ## 1. Created validator with pubkey = newpubkey
        ## 2. Revocation request, set newpubkey to revocation.newpubkey
        ## 3. We have reached the revocation epoch, set pubkey = newpubkey
```

#### `has_eth1_withdrawal_credential`

```python
def has_eth1_withdrawal_credential(validator: Validator) -> bool:
    """
    Check if ``validator`` has an 0x01 prefixed "eth1" withdrawal credential.
    """
    return validator.withdrawal_credentials[:1] == ETH1_ADDRESS_WITHDRAWAL_PREFIX
```

#### `is_fully_withdrawable_validator`

```python
def is_fully_withdrawable_validator(validator: Validator, balance: Gwei, epoch: Epoch) -> bool:
    """
    Check if ``validator`` is fully withdrawable.
    """
    return (
        has_eth1_withdrawal_credential(validator)
        and validator.withdrawable_epoch <= epoch
        and balance > 0
    )
```

#### `is_partially_withdrawable_validator`

```python
def is_partially_withdrawable_validator(validator: Validator, balance: Gwei) -> bool:
    """
    Check if ``validator`` is partially withdrawable.
    """
    has_max_effective_balance = validator.effective_balance == MAX_EFFECTIVE_BALANCE
    has_excess_balance = balance > MAX_EFFECTIVE_BALANCE
    return has_eth1_withdrawal_credential(validator) and has_max_effective_balance and has_excess_balance
```

## Beacon chain state transition function

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    if is_execution_enabled(state, block.body):
        process_withdrawals(state, block.body.execution_payload)  # [New in Capella]
        process_pubkeychanges(state, block.body.execution_payload) # [New in Revoke]
        process_execution_payload(state, block.body.execution_payload, EXECUTION_ENGINE) # [Modified in Capella]
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)  # [Modified in Capella]
    process_sync_aggregate(state, block.body.sync_aggregate)
```

#### New `get_expected_pubkeychange`
```python
def get_expected_pubkeychange(state: BeaconState) -> Sequence[PubKeyChange]:
    epoch = get_current_epoch(state)
    pubkeychange_index = state.next_pubkeychange_index
    validator_index = state.next_pubkeychange_validator_index
    pubkeychanges: List[PubKeyChange] = []
    for _ in range(len(state.validators)):
        validator = state.validators[validator_index]
        #balance = state.balances[validator_index]
        if is_pubkey_changable(validator, epoch):
            pubkeychanges.append(PubKeyChange(
                index=pubkeychange_index,
                validator_index=validator_index,
                #address=?
            ))
            pubkeychange_index += PubKeyChangeIndex(1)
            
        if len(pubkeychanges) == MAX_PUBKEY_CHANGE_PER_PAYLOAD:
            break
        validator_index = ValidatorIndex((validator_index + 1) % len(state.validators))
    return pubkeychanges
```

#### New `process_pubkeychanges`
```python

def process_pubkeychanges(state: BeaconState, payload: ExecutedPayLoad) -> None:
    expected_pubkeychanges = get_expected_pubkeychanges(state)
    assert len(payload.pubkeychanges) == len(expected_pubkeychanges)

    # Verify the validator is active
    assert is_active_validator(validator, get_current_epoch(state))
    # Verify exit has not been initiated
    assert validator.exit_epoch == FAR_FUTURE_EPOCH
    # Pubkeychange must specify an epoch when they become valid; they are not valid before then
    assert get_current_epoch(state) >= pubkeychange.epoch
    # Verify signature - Check with mentor
    # Whether the formating is different?
    domain = get_domain(state, DOMAIN_PUBKEYCHANGE, pubkeychange.epoch)
    signing_root = compute_signing_root(pubkeychange.domain)
    assert bls.Verify(validator.pubkey, signing_root, signed_pubkeychange.signature)

    # might need a different function.
    # Question for Mentor - can we use existing withdrawal credentials
    # with bls.Verify?

    #initiate pubkeychange
    initiate_pubkeychange(state, pubkeychange.validator_index, pubkeychange.newpubkey) # Need to check this - implement this function???s

```

#### New `initiate_pubkeychanges`
```python

def initiate_pubkeychange(state: BeaconState, index: ValidatorIndex, newpubkey: BLSPubkey) -> None: # [New in Revoke]
    """
    TODO: Do we need to queue revocations? Decided not to queue the 
    """
    # set revocation epoch to current epoch + X.
    # set newpubkey to  
    # pubkey != newpubkey (we have an outstanding queued revocation)
    # pubkey == pubkey (no outstanding revocations)

    # Return if validator already initiated revocation
    validator = state.validators[index]

    # Set validator key revocation epoch
    validator.newpubkey = newpubkey
    validator.revocation_epoch = get_current_epoch(state) + Epoch(1)
```


#### Modified `process_execution_payload`

*Note*: The function `process_execution_payload` is modified to use the new `ExecutionPayloadHeader` type.
## Testing
```python
def process_execution_payload(state: BeaconState, payload: ExecutionPayload, execution_engine: ExecutionEngine) -> None:
    # Verify consistency of the parent hash with respect to the previous execution payload header
    if is_merge_transition_complete(state):
        assert payload.parent_hash == state.latest_execution_payload_header.block_hash
    # Verify prev_randao
    assert payload.prev_randao == get_randao_mix(state, get_current_epoch(state))
    # Verify timestamp
    assert payload.timestamp == compute_timestamp_at_slot(state, state.slot)
    # Verify the execution payload is valid
    assert execution_engine.notify_new_payload(payload)
    # Cache execution payload header
    state.latest_execution_payload_header = ExecutionPayloadHeader(
        parent_hash=payload.parent_hash,
        fee_recipient=payload.fee_recipient,
        state_root=payload.state_root,
        receipts_root=payload.receipts_root,
        logs_bloom=payload.logs_bloom,
        prev_randao=payload.prev_randao,
        block_number=payload.block_number,
        gas_limit=payload.gas_limit,
        gas_used=payload.gas_used,
        timestamp=payload.timestamp,
        extra_data=payload.extra_data,
        base_fee_per_gas=payload.base_fee_per_gas,
        block_hash=payload.block_hash,
        transactions_root=hash_tree_root(payload.transactions),
        #withdrawals_root=hash_tree_root(payload.withdrawals),  # [New in Capella]
        pubkeychanges_root=hash_tree_root(payload.pubkeychanges) # TODO: Verify if we require this for key change
    )
```
    # Process PubKeyChange
    

#### Modified `process_operations`

*Note*: The function `process_operations` is modified to process `BLSToExecutionChange` operations included in the block.

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index)

    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)

    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)
    for_ops(body.attestations, process_attestation)
    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)
    for_ops(body.bls_to_execution_changes, process_bls_to_execution_change)  # [New in Capella]
    for_ops(body.prvkey_to_execution_changes, process_prvkey_to_execution_change) # [New in Revoke]
```

#### New `process_bls_to_execution_change`

```python
def process_bls_to_execution_change(state: BeaconState,
                                    signed_address_change: SignedBLSToExecutionChange) -> None:
    address_change = signed_address_change.message

    assert address_change.validator_index < len(state.validators)

    validator = state.validators[address_change.validator_index]

    assert validator.withdrawal_credentials[:1] == BLS_WITHDRAWAL_PREFIX
    assert validator.withdrawal_credentials[1:] == hash(address_change.from_bls_pubkey)[1:]

    domain = get_domain(state, DOMAIN_BLS_TO_EXECUTION_CHANGE)
    signing_root = compute_signing_root(address_change, domain)
    assert bls.Verify(address_change.from_bls_pubkey, signing_root, signed_address_change.signature)

    validator.withdrawal_credentials = (
        ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11
        + address_change.to_execution_address
    )
```

## Testing

Note*: The function `initialize_beacon_state_from_eth1` is modified for pure Capella testing only.
Modifications include:
1. Use `CAPELLA_FORK_VERSION` as the previous and current fork version.
2. Utilize the Capella `BeaconBlockBody` when constructing the initial `latest_block_header`.

```python
def initialize_beacon_state_from_eth1(eth1_block_hash: Hash32,
                                      eth1_timestamp: uint64,
                                      deposits: Sequence[Deposit],
                                      execution_payload_header: ExecutionPayloadHeader=ExecutionPayloadHeader()
                                      ) -> BeaconState:
    fork = Fork(
        previous_version=CAPELLA_FORK_VERSION,  # [Modified in Capella] for testing only
        current_version=CAPELLA_FORK_VERSION,  # [Modified in Capella]
        epoch=GENESIS_EPOCH,
    )
    state = BeaconState(
        genesis_time=eth1_timestamp + GENESIS_DELAY,
        fork=fork,
        eth1_data=Eth1Data(block_hash=eth1_block_hash, deposit_count=uint64(len(deposits))),
        latest_block_header=BeaconBlockHeader(body_root=hash_tree_root(BeaconBlockBody())),
        randao_mixes=[eth1_block_hash] * EPOCHS_PER_HISTORICAL_VECTOR,  # Seed RANDAO with Eth1 entropy
    )


    # Process PubKeyChange
    

    # Process deposits
    leaves = list(map(lambda deposit: deposit.data, deposits))
    for index, deposit in enumerate(deposits):
        deposit_data_list = List[DepositData, 2**DEPOSIT_CONTRACT_TREE_DEPTH](*leaves[:index + 1])
        state.eth1_data.deposit_root = hash_tree_root(deposit_data_list)
        process_deposit(state, deposit)


    # Process activations
    for index, validator in enumerate(state.validators):
        balance = state.balances[index]
        validator.effective_balance = min(balance - balance % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
        if validator.effective_balance == MAX_EFFECTIVE_BALANCE:
            validator.activation_eligibility_epoch = GENESIS_EPOCH
            validator.activation_epoch = GENESIS_EPOCH

    # Set genesis validators root for domain separation and chain versioning
    state.genesis_validators_root = hash_tree_root(state.validators)

    # Fill in sync committees
    # Note: A duplicate committee is assigned for the current and next committee at genesis
    state.current_sync_committee = get_next_sync_committee(state)
    state.next_sync_committee = get_next_sync_committee(state)

    # Initialize the execution payload header
    state.latest_execution_payload_header = execution_payload_header

    return state
