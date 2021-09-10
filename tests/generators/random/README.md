# Randomized tests

Randomized tests in the format of `sanity` blocks tests, with randomized operations.

Information on the format of the tests can be found in the [sanity test formats documentation](../../formats/sanity/README.md).

# To generate test sources

```bash
$ make
```

The necessary commands are in the `Makefile`, as the only target.

The generated files are committed to the repo so you should not need to do this.

# To run tests

Each of the generated test does produce a `pytest` test instance but by default is
currently skipped. Running the test via the generator (see next) will trigger any errors
that would arise during the running of `pytest`.

# To generate spec tests (from the generated files)

Run the test generator in the usual way.

E.g. from the root of this repo, you can run:

```bash
$ make gen_random
```
