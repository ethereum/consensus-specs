# Operations

Operations (or "transactions" in previous spec iterations),
 are atomic changes to the state, introduced by embedding in blocks.

This generator provides a series of test suites, divided into handler, for each operation type.
An operation test-runner can consume these operation test-suites,
 and handle different kinds of operations by processing the cases using the specified test handler.

Information on the format of the tests can be found in the [operations test formats documentation](../../specs/test_formats/operations/README.md).

 

