# ETH 2.0 py-tests

These tests are not intended for client-consumption.
These tests are sanity tests, to verify if the spec itself is consistent.

There are ideas to port these tests to the YAML test suite,
 but we are still looking for inputs on how this should work.

## How to run tests

From within the py_tests folder:

Install dependencies:
```bash
python3 -m venv venv
. py_tests/venv/bin/activate
pip3 install -r requirements.txt
```

Run the tests:
```
pytest -m minimal_config .
```
