# Test format: Deposit operations

A deposit is a form of an operation (or "transaction"), modifying the state.

## Test case format

```yaml
case: string      -- description of test case, purely for debugging purposes
pre: BeaconState  -- state before applying the deposit
deposit: Deposit  -- the deposit
post: BeaconState -- state after applying the deposit. No value if deposit processing is aborted.
```

## Condition

A `deposits` handler of the `operations` should process these cases, 
 calling the implementation of the `process_deposit(state, deposit)` functionality described in the spec.
The resulting state should match the expected `post` state, or no change if the `post` state is left blank.

## Forks

Forks-interpretation: `collective` 

Pre and post state contain slot numbers, and are time sensitive. 
Additional tests will be added for future forks to cover fork-specific behavior based on input data 
 (including suites with deposits on fork transition blocks, covering multiple forks)
