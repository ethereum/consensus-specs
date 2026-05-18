# Genesis tests

The aim of the genesis tests is to provide a baseline to test genesis-state
initialization and test if the proposed genesis-validity conditions are working.

There are two handlers, documented individually:

- [`validity`](./validity.md): Tests if a genesis state is valid, i.e. if it
  counts as trigger to launch.
- [`initialization`](./initialization.md): Tests the initialization of a genesis
  state based on Eth1 data.
