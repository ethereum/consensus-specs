# Building pyspecs from specs.md

The benefit of the particular spec design is that the given Markdown files can be converted to a `spec.py` file for the purposes of testing and linting. As a result, bugs are discovered and patched more quickly.

Specs can be built from either a single Markdown document or multiple files that must be combined in a given order. Given 2 spec objects, `build_spec.combine_spec_objects` will combine them into a single spec object which, subsequently, can be converted into a `specs.py`.

## Usage

For usage of the spec builder, run `python3 -m build_spec --help`.

## `@Labels` and inserts

The functioning of the spec combiner is largely automatic in that given `spec0.md` and `spec1.md`, SSZ Objects will be extended and old functions will be overwritten. Extra functionality is provided for more granular control over how files are combined. In the event that only a small portion of code is to be added to an existing function, insert functionality is provided. This saves having to completely redefine the old function from `spec0.md` in `spec1.md`. This is done by marking where the change is to occur in the old file and marking which code is to be inserted in the new file. This is done as follows:

* In the old file, a label is added as a Python comment marking where the code is to be inserted. This would appear as follows in `spec0.md`:

```python
def foo(x):
    x << 1
    # @YourLabelHere
    return x
```

* In spec1, the new code can then be inserted by having a code-block that looks as follows:

```python
#begin insert @YourLabelHere
    x += x
#end insert @YourLabelHere
```

*Note*: The code to be inserted has the **same level of indentation** as the surrounding code of its destination insert point.
