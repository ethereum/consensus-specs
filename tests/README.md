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
