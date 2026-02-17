# Consensus test generator helpers

## `gen_base`

A util to quickly write new test suite generators with.

See [Generators documentation](../../../../generators/README.md) for integration
details.

Options:

```
-o OUTPUT_DIR   -- Output directory to write tests to. The directory must exist.
                   This directory will hold the top-level test directories (per-config directories).

[-f]            -- Optional. Force-run the generator: if false, existing test case folder will be detected,
                   and the test generator will not run the function to generate the test case with.
                   If true, all cases will run regardless, and files will be overwritten.
                   Other existing files are not deleted.

-c CONFIGS_PATH   -- The directory to load configs for pyspec from. A config is a simple key-value yaml file.
    Use `../../configs/` when running from the root dir of a generator, and requiring the standard spec configs.

[-l [CONFIG_LIST [CONFIG_LIST ...]]]   -- Optional. Define which configs to run.
    Test providers loading other configs will be ignored. If none are specified, no config will be ignored.
```

## `gen_from_tests`

This is a util to derive tests from a tests source file.

This requires the tests to yield test-case-part outputs. These outputs are then
written to the test case directory. Yielding data is illegal in normal pytests,
so it is only done when in "generator mode". This functionality can be attached
to any function by using the `vector_test()` decorator found in
`ethspec/tests/utils.py`.

## Test-case parts

Test cases consist of parts, which are yielded to the base generator one by one.

The yielding pattern is:

2 value style: `yield <key name> <value>`. The kind of output will be inferred
from the value by the `vector_test()` decorator.

3 value style: `yield <key name> <kind name> <value>`.

Test part output kinds:

- `ssz`: value is expected to be a `bytes`, and the raw data is written to a
  `<key name>.ssz_snappy` file.
- `data`: value is expected to be any Python object that can be dumped as YAML.
  Output is written to `<key name>.yaml`
- `meta`: these key-value pairs are collected into a dict, and then collectively
  written to a metadata file named `meta.yaml`, if anything is yielded with
  `meta` empty.

The `vector_test()` decorator can detect pyspec SSZ types, and output them both
as `data` and `ssz`, for the test consumer to choose.

Note that the yielded outputs are processed before the test continues. It is
safe to yield information that later mutates, as the output will already be
encoded to yaml or ssz bytes. This avoids the need to deep-copy the whole
object.
