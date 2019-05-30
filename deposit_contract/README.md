# Deposit contract

## How to compile the contract?

Under the `eth2.0-specs` directory, execute:

```sh
make compile_deposit_contract
```

The ABI and bytecode will be updated at [`contracts/validator_registration.json`](./contracts/validator_registration.json).

## How to set up the testing environment?

```sh
make install_deposit_contract_test
```

## How to run tests?

```sh
make test_deposit_contract
```
