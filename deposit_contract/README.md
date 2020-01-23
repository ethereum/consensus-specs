# Deposit contract

## How to set up the testing environment?

Under the `eth2.0-specs` directory, execute:

```sh
make install_deposit_contract_tester
```

## How to compile the contract?

```sh
make compile_deposit_contract
```

The compiler dependencies can be installed with:

```sh
make install_deposit_contract_compiler
```

Note that this requires python 3.7 to be installed. The pinned vyper version will not work on 3.8.

The ABI and bytecode will be updated at [`contracts/validator_registration.json`](./contracts/validator_registration.json).


## How to run tests?

For running the contract tests:
```sh
make test_deposit_contract
```

For testing the compiler output against the expected formally-verified bytecode:
```sh
make test_compile_deposit_contract
```
