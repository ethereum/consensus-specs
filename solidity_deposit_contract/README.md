# Deposit Contract

## History

This is a rewrite of the
[Vyper Eth 2.0 deposit contract](https://github.com/ethereum/eth2.0-specs/blob/v0.12.2/deposit_contract/contracts/validator_registration.vy)
to Solidity.

The original motivation was to run the SMTChecker and the new Yul IR generator
option (`--ir`) in the compiler.

As of June 2020, version `r1` of the Solidity deposit contract has been verified
and is considered for adoption. See this
[blog post](https://blog.ethereum.org/2020/06/23/eth2-quick-update-no-12/) for
more information.

In August 2020, version `r2` was released with metadata modifications and
relicensed to CC0-1.0. Afterward, this contract has been ported back to from
[`axic/eth2-deposit-contract`](https://github.com/axic/eth2-deposit-contract) to
this repository and replaced the Vyper deposit contract.

## Compiling solidity deposit contract

In this directory run:

```sh
make compile_deposit_contract
```

The following parameters were used to generate the bytecode for the
`DepositContract` available in this repository:

- Contract Name: `DepositContract`
- Compiler Version: Solidity `v0.6.11+commit.5ef660b1`
- Optimization Enabled: `Yes` with `5000000` runs
- Metadata Options: `--metadata-literal` (to verify metadata hash)

```sh
solc --optimize --optimize-runs 5000000 --metadata-literal --bin deposit_contract.sol
```

## Running web3 tests

1. In this directory run `make install_deposit_contract_web3_tester` to install
   the tools needed (make sure to have Python 3 and pip installed).
2. In this directory run `make test_deposit_contract_web3_tests` to execute the
   tests.

## Running randomized `dapp` tests:

Install the latest version of `dapp` by following the instructions at
[dapp.tools](https://dapp.tools/). Then in the `eth2.0-specs` directory run:

```sh
make test_deposit_contract
```
