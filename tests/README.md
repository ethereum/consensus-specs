# Getting Started with Consensus Spec Tests

## Getting Started

### Creating the environment

Use an OS that has Python 3.8 or above. For example, Debian 11 (bullseye)

1. Install the packages you need:

```sh
sudo apt install -y make git wget python3-venv gcc python3-dev
```

2. Download the latest
   [consensus specs](https://github.com/ethereum/consensus-specs)

```sh
git clone https://github.com/ethereum/consensus-specs.git
cd consensus-specs
```

3. Create the specifications and tests:

```sh
make
```

To read more about creating the environment, [see here](core/pyspec/README.md).

### Running your first test

Use `make` to run the `test_empty_block_transition` tests against the Altair
fork like so:

```
$ make test k=test_empty_block_transition fork=altair
Building all pyspecs
...
================================= test session starts ==================================
platform darwin -- Python 3.10.3, pytest-8.3.3, pluggy-1.5.0
rootdir: /Users/jtraglia/Projects/jtraglia/consensus-specs
plugins: cov-5.0.0, xdist-3.6.1
20 workers [3 items]
s..                                                                              [100%]
=================================== warnings summary ===================================
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
====================== 2 passed, 1 skipped, 42 warnings in 7.97s =======================
```

## The "Hello, World" of Consensus Spec Tests

One of the `test_empty_block_transition` tests is implemented by a function with
the same name located in
[`~/consensus-specs/tests/core/pyspec/eth_consensus_specs/test/phase0/sanity/test_blocks.py`](https://github.com/ethereum/consensus-specs/blob/master/tests/core/pyspec/eth_consensus_specs/test/phase0/sanity/test_blocks.py).
To learn how consensus spec tests are written, let's go over the code:

```
@with_all_phases
```

This [decorator](https://book.pythontips.com/en/latest/decorators.html)
specifies that this test is applicable to all the phases of consensus layer
development. These phases are similar to forks (Istanbul, Berlin, London, etc.)
in the execution blockchain.

```
@spec_state_test
```

This decorator specifies that this test is a state transition test, and that it
does not include a transition between different forks.

```
def test_empty_block_transition(spec, state):
```

This type of test receives two parameters:

- `specs`: The protocol specifications
- `state`: The genesis state before the test

```python
pre_slot = state.slot
```

A slot is a unit of time (every 12 seconds in mainnet), for which a specific
validator (selected randomly but in a deterministic manner) is a proposer. The
proposer can propose a block during that slot.

```python
pre_eth1_votes = len(state.eth1_data_votes)
pre_mix = spec.get_randao_mix(state, spec.get_current_epoch(state))
```

Store some values to check later that certain updates happened.

```python
yield "pre", state
```

In Python `yield` is used by
[generators](https://wiki.python.org/moin/Generators). However, for our purposes
we can treat it as a partial return statement that doesn't stop the function's
processing, only adds to a list of return values. Here we add two values, the
string `'pre'` and the initial state, to the list of return values.

[You can read more about test generators and how they are used here](generators).

```python
block = build_empty_block_for_next_slot(spec, state)
```

The state contains the last block, which is necessary for building up the next
block (every block needs to have the root of the previous one in a blockchain).

```python
signed_block = state_transition_and_sign_block(spec, state, block)
```

Create a block signed by the appropriate proposer and advance the state.

```python
yield "blocks", [signed_block]
yield "post", state
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

Finally we assertions that test the transition was legitimate. In this case we
have three assertions:

1. One item was added to `eth1_data_votes`
2. The new block's `parent_root` is the same as the block in the previous
   location
3. The random data that every block includes was changed.

## New Tests

The easiest way to write a new test is to copy and modify an existing one. For
example, lets write a test where the first slot of the beacon chain is empty
(because the assigned proposer is offline, for example), and then there's an
empty block in the second slot.

We already know how to accomplish most of what we need for this test, but the
only way we know to advance the state is `state_transition_and_sign_block`, a
function that also puts a block into the slot. So let's see if the function's
definition tells us how to advance the state without a block.

First, we need to find out where the function is located. Run:

```sh
find . -name '*.py' -exec grep 'def state_transition_and_sign_block' {} \; -print
```

And you'll find that the function is defined in
`eth_consensus_specs/test/helpers/state.py`. Looking in that file, we see that
the second function is:

```python
def next_slot(spec, state):
    """
    Transition to the next slot.
    """
    spec.process_slots(state, state.slot + 1)
```

This looks like exactly what we need. So we add this call before we create the
empty block:

```python
yield "pre", state
next_slot(spec, state)
block = build_empty_block_for_next_slot(spec, state)
```

That's it. Our new test works (copy `test_empty_block_transition`, rename it,
add the `next_slot` call, and then run it to verify this).

## Tests Designed to Fail

It is important to make sure that the system rejects invalid input, so our next
step is to deal with cases where the protocol is supposed to reject something.
To see such a test, look at `test_invalid_prev_slot_block_transition` (in the same file
we used previously,
`~/consensus-specs/tests/core/pyspec/eth_consensus_specs/test/phase0/sanity/test_blocks.py`).

```python
@with_all_phases
@spec_state_test
def test_invalid_prev_slot_block_transition(spec, state):
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
yield "pre", state
expect_assertion_error(lambda: transition_unsigned_block(spec, state, block))
```

Specify that the function `transition_unsigned_block` will cause an assertion
error. You can see this function in
`~/consensus-specs/tests/core/pyspec/eth_consensus_specs/test/helpers/block.py`,
and one of the tests is that the block must be for this slot:

> ```python
> assert state.slot == block.slot
> ```

Because we use
[lambda notation](https://www.w3schools.com/python/python_lambda.asp), the test
does not call `transition_unsigned_block` here. Instead, this is a function
parameter that can be called later.

```python
block.state_root = state.hash_tree_root()
```

Set the block's state root to the current state hash tree root, which identifies
this block as belonging to this slot (even though it was created for the
previous slot).

```python
signed_block = sign_block(spec, state, block, proposer_index=proposer_index)
```

Notice that `proposer_index` is the variable we set earlier, *before* we
advanced the slot with `spec.process_slots(state, state.slot + 1)`. It is not
the proposer for the current state.

```python
yield "blocks", [signed_block]
yield "post", None  # No post state, signifying it errors out
```

This is the way we specify that a test is designed to fail - failed tests have
no post state, because the processing mechanism errors out before creating it.

## Attestation Tests

The consensus layer doesn't provide any direct functionality to end users. It
does not execute EVM programs or store user data. It exists to provide a secure
source of information about the latest verified block hash of the execution
layer.

For every slot a validator is randomly selected as the proposer. The proposer
proposes a block for the current head of the consensus-layer chain (built on the
previous block). That block includes the block hash of the proposed new head of
the execution layer.

For every slot there is also a randomly selected committee of validators that
needs to vote whether the new consensus-layer block is valid, which requires the
proposed head of the execution chain to also be a valid block. These votes are
called
[attestations](https://notes.ethereum.org/@hww/aggregation#112-Attestation), and
they are sent as independent messages. The proposer for a block is able to
include attestations from previous slots, which is how they get on chain to form
consensus, reward honest validators, etc.

[You can see a simple successful attestation test here](https://github.com/ethereum/consensus-specs/blob/926e5a3d722df973b9a12f12c015783de35cafa9/tests/core/pyspec/eth_consensus_specs/test/phase0/block_processing/test_process_attestation.py#L26-L30):
Lets go over it line by line.

```python
@with_all_phases
@spec_state_test
def test_success(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
```

[This function](https://github.com/ethereum/consensus-specs/blob/30fe7ba1107d976100eb0c3252ca7637b791e43a/tests/core/pyspec/eth_consensus_specs/test/helpers/attestations.py#L88-L120)
creates a valid attestation (which can then be modified to make it invalid if
needed). To see an attestation "from the inside" we need to follow it.

```python
def get_valid_attestation(
    spec, state, slot=None, index=None, filter_participant_set=None, signed=False
): ...
```

Only two parameters, `spec` and `state` are required. However, there are four
other parameters that can affect the attestation created by this function.

```python
# If filter_participant_set filters everything, the attestation has 0 participants, and cannot be signed.
# Thus strictly speaking invalid when no participant is added later.
if slot is None:
    slot = state.slot
if index is None:
    index = 0
```

Default values. Normally we want to choose the current slot, and out of the
proposers and committees that it can have, we want the first one.

```python
attestation_data = build_attestation_data(spec, state, slot=slot, index=index)
```

Build the actual attestation. You can see this function
[here](https://github.com/ethereum/consensus-specs/blob/30fe7ba1107d976100eb0c3252ca7637b791e43a/tests/core/pyspec/eth_consensus_specs/test/helpers/attestations.py#L53-L85)
to see the exact data in an attestation.

```python
beacon_committee = spec.get_beacon_committee(
    state,
    attestation_data.slot,
    attestation_data.index,
)
```

This is the committee that is supposed to approve or reject the proposed block.

```python
committee_size = len(beacon_committee)
aggregation_bits = Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*([0] * committee_size))
```

There's a bit for every committee member to see if it approves or not.

```python
attestation = spec.Attestation(
    aggregation_bits=aggregation_bits,
    data=attestation_data,
)
# fill the attestation with (optionally filtered) participants, and optionally sign it
fill_aggregate_attestation(
    spec, state, attestation, signed=signed, filter_participant_set=filter_participant_set
)

return attestation
```

```python
next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)
```

Attestations have to appear after the block they attest for, so we advance
`spec.MIN_ATTESTATION_INCLUSION_DELAY` slots before creating the block that
includes the attestation. Currently a single block is sufficient, but that may
change in the future.

```python
yield from run_attestation_processing(spec, state, attestation)
```

[This function](https://github.com/ethereum/consensus-specs/blob/30fe7ba1107d976100eb0c3252ca7637b791e43a/tests/core/pyspec/eth_consensus_specs/test/helpers/attestations.py#L13-L50)
processes the attestation and returns the result.

### Adding an Attestation Test

Attestations can't happen in the same block as the one about which they are
attesting, or in a block that is after the block is finalized. This is specified
as part of the specs, in the `process_attestation` function. Here is the
relevant code fragment:

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.target.epoch == compute_epoch_at_slot(data.slot)
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot <= data.slot + SLOTS_PER_EPOCH
    ...
```

In the last line you can see two conditions being asserted:

1. `data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot` which verifies
   that the attestation doesn't arrive too early.
2. `state.slot <= data.slot + SLOTS_PER_EPOCH` which verifies that the
   attestation doesn't arrive too late.

This is how the consensus-layer tests deal with edge cases, by asserting the
conditions required for the values to be legitimate. In the case of these
particular conditions, they are tested
[here](https://github.com/ethereum/consensus-specs/blob/926e5a3d722df973b9a12f12c015783de35cafa9/tests/core/pyspec/eth_consensus_specs/test/phase0/block_processing/test_process_attestation.py#L87-L104).
One test checks what happens if the attestation is too early, and another if it
is too late.

However, it is not enough to ensure we reject invalid blocks. It is also
necessary to ensure we accept all valid blocks. You saw earlier a test
(`test_success`) that tested that being `MIN_ATTESTATION_INCLUSION_DELAY` after
the data for which we attest is enough. Now we'll write a similar test that
verifies that being `SLOTS_PER_EPOCH` away is still valid. To do this, we modify
the `test_after_epoch_slots` function. We need two changes:

1. Call `transition_to_slot_via_block` with one less slot to advance
2. Don't tell `run_attestation_processing` to return an empty post state.

The modified function is:

```python
@with_all_phases
@spec_state_test
def test_almost_after_epoch_slots(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)

    # increment to latest inclusion slot (not beyond it)
    transition_to_slot_via_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)

    yield from run_attestation_processing(spec, state, attestation)
```

Add this function to the file
`consensus-specs/tests/core/pyspec/eth_consensus_specs/test/phase0/block_processing/test_process_attestation.py`,
and run the test against Altair fork:

```sh
make test k=almost_after fork=altair
```

You should see it ran successfully (although you might get a warning, you can
ignore it)

## How are These Tests Used?

So far we've ran tests against the formal specifications. This is a way to check
the specifications are what we expect, but it doesn't actually check the beacon
chain clients. Consensus-layer clients implement test-runners that
consume/execute these reference tests to ensure they have implemented the
specifications properly.

______________________________________________________________________

Original version by [Ori Pomerantz](mailto:qbzzt1@gmail.com)
