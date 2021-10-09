# Getting Started with Consensus Spec Tests

## Getting Started

### Creating the environment

Use an OS that has Python 3.8 or above. For example, Debian 11 (bullseye)

1. Install the packages you need:
   ```sh
   sudo apt install -y make git wget python3-venv gcc python3-dev
   ```
1. Download the latest [consensus specs](https://github.com/ethereum/consensus-specs)
   ```sh
   git clone https://github.com/ethereum/consensus-specs.git
   cd consensus-specs
   ```
1. Create the specifications and tests:   
   ```sh
   make install_test
   make pyspec
   ```

### Running your first test


1. Enter the virtual Python environment:
   ```sh
   cd ~/consensus-specs
   . venv/bin/activate
   ```
1. Run a sanity check test:
   ```sh 
   cd tests/core/pyspec/
   python -m pytest -k test_empty_block_transition
   ```
1. The output should be similar to:
   ```
   ============================= test session starts ==============================
   platform linux -- Python 3.9.2, pytest-6.2.5, py-1.10.0, pluggy-1.0.0
   rootdir: /home/qbzzt1/consensus-specs
   plugins: cov-2.12.1, forked-1.3.0, xdist-2.3.0
   collected 629 items / 626 deselected / 3 selected

   eth2spec/test/merge/sanity/test_blocks.py .                              [ 33%]
   eth2spec/test/phase0/sanity/test_blocks.py ..                            [100%]

   =============================== warnings summary ===============================
   ../../../venv/lib/python3.9/site-packages/cytoolz/compatibility.py:2
     /home/qbzzt1/consensus-specs/venv/lib/python3.9/site-packages/cytoolz/compatibility.py:2: 
   DeprecationWarning: The toolz.compatibility module is no longer needed in Python 3 and has 
   been deprecated. Please import these utilities directly from the standard library. This 
   module will be removed in a future release.
       warnings.warn("The toolz.compatibility module is no longer "

   -- Docs: https://docs.pytest.org/en/stable/warnings.html
   ================ 3 passed, 626 deselected, 1 warning in 16.81s =================   
   ```


## The "Hello, World" of Consensus Spec Tests

One of the `test_empty_block_transition` tests is implemented by a function with the same
name located in 
[`~/consensus-specs/tests/core/pyspec/eth2spec/test/phase0/sanity/test_blocks.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/phase0/sanity/test_blocks.py).
To learn how consensus spec tests are written, let's go over the code:

```python
@with_all_phases
```

This [decorator](https://book.pythontips.com/en/latest/decorators.html) specifies that this test
is applicable to all the phases of the ETH 2.0 project. These phases are similar to forks (Istanbul,
Berlin, London, etc.) in the execution blockchain. If you are interested, [you can see the definition of
this decorator here](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/context.py#L331-L335).

```python
@spec_state_test
```

[This decorator](https://github.com/qbzzt/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/context.py#L232-L234) specifies
that this test is a state transition test, and that it does not include a transition between different forks.

```python
def test_empty_block_transition(spec, state):
```

This type of test receives two parameters:

* `specs`: The protocol specifications
* `state`: The genesis state before the test

```python
    pre_slot = state.slot
```    

A slot is a unit of time (every 12 seconds in mainnet), for which a specific validator (selected randomly but in a
deterministic manner) is a proposer. The proposer can propose a block during that slot. 

```python
    pre_eth1_votes = len(state.eth1_data_votes)
    pre_mix = spec.get_randao_mix(state, spec.get_current_epoch(state))
```

Store some values to check later that certain updates happened.

```python
    yield 'pre', state
```

In Python `yield` is used by [generators](https://wiki.python.org/moin/Generators). However, for our purposes
we can treat it as a partial return statement that doesn't stop the function's processing, only adds to a list
of return values. Here we add two values, the string `'pre'` and the initial state, to the list of return values.

```python
    block = build_empty_block_for_next_slot(spec, state)
```

The state contains the last block, which is necessary for building up the next block (every block needs to
have the hash of the previous one in a blockchain).

```python
    signed_block = state_transition_and_sign_block(spec, state, block)
```

Create a block signed by the appropriate proposer and advance the state

```python
    yield 'blocks', [signed_block]
    yield 'post', state
```

More `yield` statements. The output of a consensus test is:

1. `'pre'`
2. The state before the test was run
3. `'blocks'`
4. A list of signed blocks
5. `'post'`
6. The state after the test



```python
    # One vote for the eth1
    assert len(state.eth1_data_votes) == pre_eth1_votes + 1

    # Check that the new parent root is correct
    assert spec.get_block_root_at_slot(state, pre_slot) == signed_block.message.parent_root
    
    # Random data changed
    assert spec.get_randao_mix(state, spec.get_current_epoch(state)) != pre_mix
```

Finally we assertions that test the transition was legitimate. In this case we have three assertions:

1. One item was added to `eth1_data_votes`
2. The new block's `parent_root` is the same as the block in the previous location
3. The random data that every block includes was changed. 


## New Tests

The easiest way to write a new test is to copy and modify an existing one. For example,
lets write a test where the first slot of the beacon chain is empty (because the assigned 
proposer is offline, for example), and then there's an empty block in the second slot.

We already know how to accomplish most of what we need for this test, but the only way we know 
to advance the state is `state_transition_and_sign_block`, a function that also puts a block
into the slot. So let's see if the function's definition tells us how to advance the state without
a block.

First, we need to find out where the function is located. Run:

```sh
find . -name '*.py' -exec grep 'def state_transition_and_sign_block' {} \; -print
```

And you'll find that the function is defined in 
[`eth2spec/test/helpers/state.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/state.py). Looking
in that file, we see that the second function is:

```python
def next_slot(spec, state):
    """
    Transition to the next slot.
    """
    spec.process_slots(state, state.slot + 1)
```

This looks like exactly what we need. So we add this call before we create the empty block:


```python
.
.
.
    yield 'pre', state

    next_slot(spec, state)

    block = build_empty_block_for_next_slot(spec, state)
.
.
.
```

That's it. Our new test works (copy `test_empty_block_transition`, rename it, add the `next_slot` call, and then run it to 
verify this).



## Tests Designed to Fail

It is important to make sure that the system rejects invalid input, so our next step is to deal with cases where the protocol
is supposed to reject something. To see such a test, look at `test_prev_slot_block_transition` (in the same
file we used previously, 
[`~/consensus-specs/tests/core/pyspec/eth2spec/test/phase0/sanity/test_blocks.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/phase0/sanity/test_blocks.py)).

```python
@with_all_phases
@spec_state_test
def test_prev_slot_block_transition(spec, state):
    spec.process_slots(state, state.slot + 1)
    block = build_empty_block(spec, state, slot=state.slot)
```

Build an empty block for the current slot.

```python
    proposer_index = spec.get_beacon_proposer_index(state)
```

Get the identity of the current proposer, the one for *this* slot.

```python
    spec.process_slots(state, state.slot + 1)
```

Transition to the new slot, which naturally has a different proposer.

```python
    yield 'pre', state
    expect_assertion_error(lambda: transition_unsigned_block(spec, state, block))
```

Specify that the function `transition_unsigned_block` will cause an assertion error.
You can see this function in 
[`~/consensus-specs/tests/core/pyspec/eth2spec/test/helpers/block.py`](https://github.com/ethereum/consensus-specs/blob/dev/tests/core/pyspec/eth2spec/test/helpers/block.py),
and one of the tests is that the block must be for this slot:
> ```python
> assert state.slot == block.slot
>  ```

Because we use [lambda notation](https://www.w3schools.com/python/python_lambda.asp), the test
does not call `transition_unsigned_block` here. Instead, this is a function parameter that can
be called later.

```python
    block.state_root = state.hash_tree_root()
```

Set the block's state root to the current state hash tree root, which identifies this block as
belonging to this slot (even though it was created for the previous slot). 

```python    
    signed_block = sign_block(spec, state, block, proposer_index=proposer_index)
```

Notice that `proposer_index` is the variable we set earlier, *before* we advanced
the slot with `spec.process_slots(state, state.slot + 1)`. It is not the proposer 
for hte current state.

```python
    yield 'blocks', [signed_block]
    yield 'post', None   # No post state, signifying it errors out
```

This is the way we specify that a test is designed to fail - failed tests have no post state,
because the processing mechanism errors out before creating it.


## Attestation Tests

The [beacon chain](https://ethereum.org/en/eth2/beacon-chain/) doesn't provide any direct value. It does
not execute EVM programs or store user data. The reason it exists at all is to provide a trusted source of
information about the latest verified block hash of the [shard blockchains](https://ethereum.org/en/eth2/shard-chains/)
which do provide storage, and possibly execution, services.

The block proposed by the proposer includes the hash for the latest block in the shard for which the proposer is
responsible. Then there's a randomly selected committee of validators that needs to vote whether that is really
a valid hash for that shard at that point in time. 2/3's of the validators on the committee need to vote to 
approve the proposal for that hash to be accepted for that shard. The result of this vote is called an 
[attestation](https://notes.ethereum.org/@hww/aggregation#112-Attestation).

[You can see a simple successful attestation test here](https://github.com/ethereum/consensus-specs/blob/926e5a3d722df973b9a12f12c015783de35cafa9/tests/core/pyspec/eth2spec/test/phase0/block_processing/test_process_attestation.py#L26-L30):
Lets go over it line by line.


```python
@with_all_phases
@spec_state_test
def test_success(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
```

This function creates a valid attestation (which can then be modified to make it invalid if needed).
[You can see this function here](https://github.com/ethereum/consensus-specs/blob/30fe7ba1107d976100eb0c3252ca7637b791e43a/tests/core/pyspec/eth2spec/test/helpers/attestations.py#L88-L120).
To see an attestion "from the inside" we need to follow this function.


> ```python
>  def get_valid_attestation(spec,
>                           state,
>                           slot=None,
>                           index=None,
>                           filter_participant_set=None,
>                           signed=False):
> ```
>
> Only two parameters, `spec` and `state` are required. However, there are four other parameters that can affect
> the attestation created by this function. 
> 
>
> ```python
>     # If filter_participant_set filters everything, the attestation has 0 participants, and cannot be signed.
>     # Thus strictly speaking invalid when no participant is added later.
>     if slot is None:
>         slot = state.slot
>     if index is None:
>         index = 0
> ```
>
> Default values. Normally we want to choose the current slot, and out of the proposers and committees that it can have,
> we want the first one.
>
> ```python
>     attestation_data = build_attestation_data(
>         spec, state, slot=slot, index=index
>     )
> ```   
>
> Build the actual attestation. You can see this function 
> [here](https://github.com/ethereum/consensus-specs/blob/30fe7ba1107d976100eb0c3252ca7637b791e43a/tests/core/pyspec/eth2spec/test/helpers/attestations.py#L53-L85) 
> to see the exact data in an attestation.
>
>  ```python
>     beacon_committee = spec.get_beacon_committee(
>         state,
>         attestation_data.slot,
>         attestation_data.index,
>     )
> ```
> 
> This is the committee that is supposed to approve or reject the proposed block.
> 
> ```python    
> 
>     committee_size = len(beacon_committee)
>     aggregation_bits = Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*([0] * committee_size))
> ```
> 
> There's a bit for every committee member to see if it approves or not.
> 
> ```python
>     attestation = spec.Attestation(
>         aggregation_bits=aggregation_bits,
>         data=attestation_data,
>     )
>     # fill the attestation with (optionally filtered) participants, and optionally sign it
>     fill_aggregate_attestation(spec, state, attestation, signed=signed, filter_participant_set=filter_participant_set)
> 
>    return attestation  
>  ```

```python
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)
```

Attestations have to appear after the block they attest for. The current value
of `MIN_ATTESTATION_INCLUSION_DELAY` is one, but 

```
    yield from run_attestation_processing(spec, state, attestation)
```




<!--


Attestation:

Success: https://github.com/ethereum/consensus-specs/blob/926e5a3d722df973b9a12f12c015783de35cafa9/tests/core/pyspec/eth2spec/test/phase0/block_processing/test_process_attestation.py#L26

Failure: https://github.com/ethereum/consensus-specs/blob/926e5a3d722df973b9a12f12c015783de35cafa9/tests/core/pyspec/eth2spec/test/phase0/block_processing/test_process_attestation.py#L98

And the conditions in process_attestation for these cases are pretty clear to reference and reason about for a new contributor
And obviously, one of our goals to directly test all of these boundaries so can be a good just general testing approach discussion there too

https://ethos.dev/beacon-chain/

-->

## How are These Tests Used?

<!--

Beacon chain has operations (such as attestation, deposit). It deals with core consensus


See if I can rename single_phase



so sometimes you uncover issues on the mainnet version of tests (all tests run against each unless flagged not to) that weren't caught in CI
you can force to run against mainnet config locally by doing python3 -m pytest -k {search_str} --preset=mainnet eth2spec/
the --preset flag
and running all the tests against mainnet config takes much longer... like 30+ minutes instead of 4 or 5


-->
