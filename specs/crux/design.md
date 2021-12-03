# Delegating validators

## Abstract
We allow for validators to delegate their excess earnings to another (possibly new) validator. Thus allowing for beacon-chain issuance to quickly start staking instead of either remaining inactive or impacting the exit churn. This all within the consensus layer, in particular not involving the deposit contract.

## The problem
At the time of writing the beacon chain has 264,676 active validators, the average earning is 1.34 ETH and over 150,000 validators have earned over 1ETH. There are over 100,000 validators accounted for staking pools according to [beaconcha.in](https://beaconcha.in/pools). There is no reason to expect these validators to not withdraw their proceeds as soon as they become available. Disregarding those validators that would want to perform a normal withdraw of all of their funds, there will still be a large number of validators that will simply withdraw their excess earnings, either to keep it off the consensus layer, or to compound their interest rate by staking extra validators, as is expectedly the case of staking pools. Under the current leading proposals these validators will have two paths to withdraw their earnings

- Enter an exit queue. Wait for their turn to become withdrawable. Deposit the principal. Enter an entry queue. Wait for their turn to become active.
- Wait for their turn to propose a block to perform a partial withdrawal.

In average the latter will happen once every 37 days with current numbers. The former incurrs in costs of earnings lost while in queue and gas costs of redepositing. This leads to an equilibrium in which the exit queue becomes at least large enough that the cost is comparable to waiting 37 days to extract funds. This equilibrium is not a one-time run for the exit queue, as validator rotation to compound interest will be a constant exit force, and the wait time for a proposal increases linearly with the number of active validators, so will the exit queue.

This makes for a bad user experience, particularly for a single staker, 20% of which will have to wait for 2 months for a proposal with current numbers (presumably much more as the validator registry increases)

## Delegating validators

The current proposal solves the above problem by providing validators, and in particular staking pools, with a mechanism to continuously transfer their excess earnings to another validator. This new validator can be a new validator. There are several advantages to this mechanism:

- Validators can compound their interest immediately and spin off new validators more quickly, avoiding the partial withdrawal and deposit cycle (but are still subject to activation queue)
- Validators can trustlesly sell their excess earnings, providing liquidity for small stakers without requiring them to either wait possibly months nor withdraw their stake. Thus this could in principle be a decentralizing force.
- It keeps the non-staking capital to a minimum since as soon as the delegate validator reaches `MAX_EFFECTIVE_BALANCE` it enters the activation queue.

## Typical workflow

The typical workflow for an individual that holds validators `A` and `B` will be as follows. He sends a `Delegation` message on the p2p network that contains the validating public key and the withdrawal credentials of a new validator `C`. He signs this message with the withdrawal private key for `A`. Proposers include these messages in a block (they get a fee for doing so) and as soon as the block is included on-chain, the validator `C` is created and the excess balance of `A` is transferred to it. At a later time (or at the same time), `B` can send a similar message signed by its withdrawal key. In this case `C`, already in the validator registry, gets `B`'s excess funds. Each epoch, at epoch processing, `C` will receive the extra earnings from `A` and `B`. When `C`'s balance reaches 32 ETH, it enters the entry queue and becomes active.

## Implementation details

This section contains an annotated description of the changes to the beacon chain.

### Constants

#### Domain types
A new domain to sign the `Delgation` messsages sent by validators.
| Name  | Value |
| - | - |
| `DOMAIN_DELEGATION` | `DomainType('0x0A000000')` |

### Preset

#### Max operations per block
The number of `Delegations` that can be included per block. This works as a churn which is independent of the exit queue churn and `MAX_VOLUNTARY_EXITS`

| Name | Value |
| - | - |
| `MAX_DELEGATIONS` | `2**4` (=16) |

#### Time parameters
The maximum duration a `Delegation` message is valid for. This is to avoid having unbounded caches with seen messages that have never been included.
| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `MAX_DELEGATION_INCLUSION_DELAY` | `uint64(2**7)` (=128) | slots | 25.6 minutes |

### Configuration

#### Gwei values
The fee payed by the delegating validator, to the block proposer that includes the `Delegation` message. This value should be small enough to make it convenient for the staking validator to delegate, rather than exit and deposit. At the same time it has to be large enough to incentivize proposers to include delegations.
| Name | Value |
| - | - |
| `DELEGATION_TRANSACTION_COST` | `Gwei(10**6)` (= 1,000,000) TBD |


## Containers

### Extended containers

#### `Validator`
The `Validator` container gains a new field `delegate` containing the validator index of the delegate validator. This field is initialized at the fork with the same validator index of the current validator. Real life implementations will likely keep a separate map instead as not every validator will choose to delegate. In the naïve implementation were the field is added to all validators, this will currently increase the beacon state by 2Mb.

```python
class Validator(Container):
    pubkey: BLSPubkey
    delegate: ValidatorIndex  # [New in Crux]
    withdrawal_credentials: Bytes32
    effective_balance: Gwei
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch
```

#### `BeaconBlockBody`
The beacon block body contains now a list of `Delegation` messages that are included. Each delegation consists of 240 Bytes and processing it costs one signature verification. This should be taken into account when choosing `MAX_DELEGATIONS`.

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data
    graffiti: Bytes32
    # Operations
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    attestations: List[Attestation, MAX_ATTESTATIONS]
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    delegations: List[Delegation, MAX_DELEGATIONS]  # [New in Crux]
    sync_aggregate: SyncAggregate
    # Execution
    execution_payload: ExecutionPayload
```

### New containers

#### `DelegationMessage`
A `DelegationMessage` contains the validating public key and the withdrawal creedentials of the delegate validator. It also contains the delegate validator withdrawal public key. This latter key is used to verify the signature of the sender. In this current implementation we support only BLS withdrawal credentials postponing the implementation ETH1 withdrawal credentials when the proposal for withdrawals is settled (as the same issue has to be addressed for withdrawals)

```python
class DelegationMessage(Container):
    delegating_index: ValidatorIndex
    delegating_pubkey: BLSPubkey
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32
```

A `Delegation` consists of the signed message, the signature and an `epoch` parameter that determines when the delegation becomes valid. A delegation is then valid only from `epoch` until `epoch + MAX_DELEGATION_INCLUSION_DELAY`

#### `Delegation`

```python
class Delegation(Container):
    message: DelegationMessage
    epoch: Epoch
    signature: BLSSignature
```

## Beacon chain state transition function

### Block processing

#### Operations

The last step of block processing is the delegation processing. Althouh no problem would actually exists if delegating to an exited validator (as a chec is performed on transfers) it is here as an extra measure to prevent delegations to slashed or exited validators. It also prevents the situation where the delegating validator has enough excess to start a new validator, but it is getting slashed in this block, or simply is being penalized.

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
    for_ops(body.delegations, process_delegation)   # [New in Crux]
```

#### Delegation
This helper function returns a new validator with the public key and the withdrawal credentials provided by the `DelegationMessage`

##### `get_validator_from_delegation`

```python
def get_validator_from_delegation_message(message: DelegationMessage, amount: Gwei) -> Validator:
    effective_balance = min(amount - amount % EFFECTIVE_BALANCE_INCREMENT, MAX_EFFECTIVE_BALANCE)
    return Validator(
        pubkey=message.pubkey,
        withdrawal_credentials=message.withdrawal_credentials,
        activation_eligibility_epoch=FAR_FUTURE_EPOCH,
        activation_epoch=FAR_FUTURE_EPOCH,
        exit_epoch=FAR_FUTURE_EPOCH,
        withdrawable_epoch=FAR_FUTURE_EPOCH,
        effective_balance=effective_balance,
    )
```

##### `process_delegation`

The function `process_delegation` contains the core logic changes in the proposal. As such it will be split in this annotated description. We start by asserting that the current epoch falls between the validity window of the delegation:

```python
def process_delegation(state: BeaconState, delegation: Delegation) -> None:
    message = delegation.message
    current_epoch = get_current_epoch(state)
    assert  message.epoch <= current.epoch <= message.epoch + MAX_DELEGATION_INCLUSION_DELAY
```

We then check that the delegating validator has accumulated earnings of at least 1 ETH. This is to prevent creation of lots of validators with no balance in the registry. We require in addition that the delegating validator has enough to pay the fee to the proposer that includes the delegation. The variable `amount`, is what the delegate validator will receive when it is created. It consists of all the excess balance of the delegating validator minus the proposer fee.
```python
    delegating_index = message.delegating_index
    min_delegating_balance = MAX_EFFECTIVE_BALANCE + MIN_DEPOSIT_AMOUNT + DELEGATION_TRANSACTION_COST
    assert state.balances[delegating_index] >= min_delegating_balance
    amount = state.balances[delegating_index] - MAX_EFFECTIVE_BALANCE - DELEGATION_TRANSACTION_COST
```
We perform some basic sanity checks like checking that the delegating validator is active and not slashed.
```python
    delegating_validator = state.validators[delegating_index]
    assert is_active_validator(delegating_validator, current_epoch)
    assert delegating_validator.slashed == false
```

We allow for only one delegation per validator. This may be relaxed. In principle spams and spamming loops are already prevented by the fact that we only allow delegations from validators that have 1 ETH in excess and to delegates that are newer than the delegating validator.
```python
    assert delegating_validator.delegate == delegating_index
```

We check the signature. As this is a withdrawal this has to be secured wih the withdrawal signature of the delegating validator. See the note above regarding ETH1 withdrawal credentials.
```python
    delegating_pubkey = message.delegating_pubkey
    assert hash(delegating_pubkey)[1:] == delegating_validator.withdrawal_credentials[1:]

    domain = compute_domain(DOMAIN_DELEGATION)
    signing_root = compute_signing_root(message, domain)
    assert bls.Verify(delegating_pubkey, signing_root, delegation.signature)
```

We check if the delegate validator exists in the registry. If it does not, we create one. This validator is created with the effective balance corresponding to `amount` above.
```python
    validator_pubkeys = [v.pubkey for v in state.validators]
    if pubkey not in validator_pubkeys:
        index = len(state.validators)
        state.validators.append(get_validator_from_delegation(message, amount))
```
If the delegate already exits, we enforce that it is newer than the delegating validator, to prevent from loops. We also require that the delegate validator is not exiting nor has been slashed.
```python
    else:
        index = ValidatorIndex(validator_pubkeys.index(pubkey))
        assert index > delegating_index
        assert state.validators[index].exit_epoch == FAR_FUTURE_EPOCH
```

We set the `delegate` field of the delegating validator and transfer funds accordingly.
```python
    delegating_validator.delegate = index
    proposer_index = get_beacon_proposer_index(state)
    decrease_balance(state, delegating_validator, amount + DELEGATION_TRANSACTION_COST)
    increase_balance(state, index, amount)
    increase_balance(state, proposer_index, DELEGATION_TRANSACTION_COST)
```


### Epoch processing
On each epoch boundary processing we process delegation transfers. This can be done within `process_rewards_and_penalties` but since the loop is a fairly simple loop that does not contain expensive operations, we decided to separate it here for simplicity:

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_inactivity_updates(state)
    process_rewards_and_penalties(state)
    process_delegation_transfers(state)  # [New in Crux]
    process_registry_updates(state)   # [Modified in Crux]
    process_slashings(state)
    process_eth1_data_reset(state)
    process_effective_balance_updates(state)
    process_slashings_reset(state)
    process_randao_mixes_reset(state)
    process_historical_roots_update(state)
    process_participation_flag_updates(state)
    process_sync_committee_updates(state)
```


#### `process_delegation_transfers`

This function is the main loop where we transfer excess balance. We run over the set of all validators that are actually delegating. And we transfer everything beyond `MAX_EFFECTIVE_BALANCE` to the delegate validator. We only do so if the delegate is not exiting nor has been slashed. We also prevent any slashed validator from transferring funds.

```python
def process_delegation_transfers(state: BeaconState) -> None:
    delegating_validators = [(i, v) for i, v in enumerate(state.validators) if v.delegate > i and not v.slashed]
    for index, validator in delegating_validators:
        if state.balance[index] > MAX_EFFECTIVE_BALANCE:
            delegate_validator = state.validators[validator.delegate]
            if delegate_validator.exit_epoch == FAR_FUTURE_EPOCH:
                amount = state_balance[index] - MAX_EFFECTIVE_BALANCE
                state_balance[index] = MAX_EFFECTIVE_BALANCE
                increase_balance(state, validator.delegate, amount)
```
