<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Genesis tests](#genesis-tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Genesis tests

The aim of the genesis tests is to provide a baseline to test genesis-state initialization and test
 if the proposed genesis-validity conditions are working.

There are two handlers, documented individually:
- [`validity`](./validity.md): Tests if a genesis state is valid, i.e. if it counts as trigger to launch.
- [`initialization`](./initialization.md): Tests the initialization of a genesis state based on Eth1 data.
