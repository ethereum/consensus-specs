<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Randomized tests](#randomized-tests)
- [To generate test sources](#to-generate-test-sources)
- [To run tests](#to-run-tests)
- [To generate spec tests (from the generated files)](#to-generate-spec-tests-from-the-generated-files)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

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
