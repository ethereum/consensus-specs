# Executable Python Spec (PySpec)

The executable Python spec is built from the consensus specifications,
complemented with the necessary helper functions for hashing, BLS, and more.

With this executable spec, test-generators can easily create test-vectors for
client implementations, and the spec itself can be verified to be consistent and
coherent through sanity tests implemented with pytest.

## Py-tests

These tests are not intended for client-consumption. These tests are testing the
spec itself, to verify consistency and provide feedback on modifications of the
spec. However, most of the tests can be run in generator-mode, to output test
vectors for client-consumption.

### How to run tests

To run all tests:

```shell
make test
```

To run all tests under the minimal preset:

```shell
make test preset=minimal
```

Or, to run a specific test function specify `k=<test-name>`:

```shell
make test k=test_verify_kzg_proof
```

Or, to run all tests under a single fork specify `fork=<name>`:

```shell
make test fork=phase0
```

Note: these options can be used together, like:

```shell
make test preset=minimal k=test_verify_kzg_proof fork=deneb
```

### How to generate coverage reports

Run `make test coverage=true` to enable coverage tracking and generate reports.

Reports are saved at:

- **HTML report**: `tests/core/pyspec/.htmlcov/index.html`
- **JSON report**: `tests/core/pyspec/.htmlcov/coverage.json`

To open the HTML report in a browser:

```shell
xdg-open tests/core/pyspec/.htmlcov/index.html   # Linux
open tests/core/pyspec/.htmlcov/index.html       # macOS
```

## Contributing

Contributions are welcome, but consider implementing your idea as part of the
spec itself first. The pyspec is not a replacement.

## License

Same as the spec itself; see [LICENSE](../../../LICENSE) file in the specs
repository root.
