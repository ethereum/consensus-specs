# Getting Started with Consensus Spec Tests

## The environment

Use an OS that has Python 3.8 or above. For example, Debian 11 (bullseye)


```sh
git clone https://github.com/ethereum/consensus-specs.git
cd consensus-specs
make install
```

After it fails

```sh
. venv/bin/activate
pip install ruamel.yaml==0.16.5
