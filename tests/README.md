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


## Simple Test

The `test_empty_block_transition` test is at 
`~/consensus-specs/tests/core/pyspec/eth2spec/test/phase0/sanity/test_blocks.py`. 
It is implemented by this function:

```python
@with_all_phases
@spec_state_test
def test_empty_block_transition(spec, state):
    pre_slot = state.slot
    pre_eth1_votes = len(state.eth1_data_votes)
    pre_mix = spec.get_randao_mix(state, spec.get_current_epoch(state))

    yield 'pre', state

    block = build_empty_block_for_next_slot(spec, state)

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield 'blocks', [signed_block]
    yield 'post', state

    # One vote for the eth1
    assert len(state.eth1_data_votes) == pre_eth1_votes + 1

    # Check that the new parent root is correct
    assert spec.get_block_root_at_slot(state, pre_slot) == signed_block.message.parent_root


    # Random data changed
    assert spec.get_randao_mix(state, spec.get_current_epoch(state)) != pre_mix
```


https://ethos.dev/beacon-chain/


Beacon chain has operations (such as attestation, deposit). It deals with core consensus


See if I can rename single_phase



so sometimes you uncover issues on the mainnet version of tests (all tests run against each unless flagged not to) that weren't caught in CI
you can force to run against mainnet config locally by doing python3 -m pytest -k {search_str} --preset=mainnet eth2spec/
the --preset flag
and running all the tests against mainnet config takes much longer... like 30+ minutes instead of 4 or 5



