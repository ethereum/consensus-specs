# Getting Started with Consensus Spec Tests

## The environment

Use an OS that has Python 3.8 or above. For example, Debian 11 (bullseye)


```sh
sudo apt install -y make git wget python3-venv gcc python3-dev
git clone https://github.com/ethereum/consensus-specs.git
cd consensus-specs
. venv/bin/activate
pip install ruamel.yaml==0.16.5
make install_test

make test
```

. venv/bin/activate
cd tests/core/pyspec/
python3 -m pytest -k {search_str} eth2spec/



so sometimes you uncover issues on the mainnet version of tests (all tests run against each unless flagged not to) that weren't caught in CI
you can force to run against mainnet config locally by doing python3 -m pytest -k {search_str} --preset=mainnet eth2spec/
the --preset flag
and running all the tests against mainnet config takes much longer... like 30+ minutes instead of 4 or 5



