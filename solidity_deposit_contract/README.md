# eth2-deposit-contract

This is a port of the [Vyper Eth 2.0 deposit contract](https://github.com/ethereum/eth2.0-specs/blob/dev/deposit_contract/contracts/validator_registration.vy) to Solidity.

The original motivation was to run the SMTChecker and the new Yul IR generator option (`--ir`) in the compiler.

As of June 2020, this contract (the version tagged as `r1`) has been verified and is considered for adoption.
See this [blog post](https://blog.ethereum.org/2020/06/23/eth2-quick-update-no-12/) for more information.

## Using this with the tests

1. Create the `deposit_contract.json` by running `make` (this requires `solc` to be in the path)
2. Download [eth2.0-specs](https://github.com/ethereum/eth2.0-specs)
3. Replace `eth2.0-specs/deposit_contract/contracts/validator_registration.json` with `deposit_contract.json`
4. In the `eth2.0-specs` directory run `make install_deposit_contract_tester` to install the tools needed (make sure to have Python 3.7 and pip installed)
5. Finally in the `eth2.0-specs` directory run `make test_deposit_contract` to execute the tests

The Makefile currently compiles the code without optimisations. To enable optimisations add `--optimize` to the `solc` line.


## Running randomized `dapp` tests:

Install the latest version of `dapp` by following the instructions at [dapp.tools](https://dapp.tools/). Then run
```sh
make test
```
