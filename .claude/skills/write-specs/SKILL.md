---
name: write-specs
description: >-
  Write specifications. Always load this skill before writing to `specs`.
compatibility: Requires make and uv
---

# Writing specifications

## Building

The markdown files are automatically compiled into executable Python files when
using the project's `make` rules. Run `make help verbose=true` for documentation
on available rules. Generally, only the linting and testing rules are used.

## Work-in-progress banners

Unstable specifications must include a work-in-progress banner at the top of the
document, directly below the title. Remove the banner once the specification is
promoted to the stable section of the project's README.

## Table of contents

Do not manually edit the table of contents. Running `make lint` regenerates it
automatically.

## Code style

Simplicity is a guiding principle of the specs. Code should be concise and
readable, and performant only where that does not sacrifice those qualities.
Implementations will apply optimizations that the specs deliberately omit.

Strive to write code in a generic way that other languages can translate without
difficulty. Avoid Python-specific functional helpers like `map` and `filter`. A
list comprehension or an explicit loop expresses the same logic and maps more
cleanly onto other languages.

Avoid single-letter variable names, except where a single letter is the
conventional notation in a mathematical expression.

Add a comment only when the code alone would leave something important unclear
to the reader. Do not restate what the code already does.

Docstrings and comments must be wrapped at 80 characters. In docstrings, inline
code must use double backticks so it renders correctly in mkdocs. The linter
does not enforce this, so it must be done manually. Only apply these rules to
the docstrings and comments you add or change. Leave those outside the scope of
your change untouched.

The specs make heavy use of SSZ types. Functions that operate on chain data
should accept and return SSZ types, since the chain itself is stored entirely as
SSZ types. Objects that are not part of the consensus data have no such
requirement and may use ordinary Python types and dataclasses instead.

Asserts signal an impossible situation or something that is not allowed.
Implementations are expected to handle these cases with proper error handling.
Do not use assert messages.

## Documenting changes

Changes in functionality between upgrades must be properly documented. Only
document changes made directly to an item, not changes that ripple in from its
dependencies. For example, if `foo()` calls `bar()` and `bar()` changes, `foo()`
should not annotate that `bar()` changed.

### Section prefixes

When an item such as a container or function has its own section, prefix the
section name with "New" or "Modified" accordingly. Phase0 specifications do not
use "New" prefixes, since everything there is considered new.

### Annotations

Annotations such as `# [New in Deneb]` and `# [Modified in Deneb]` indicate that
a line or block of code has changed, where the name is the upgrade that
introduced the change. If a change is associated with a particular EIP, the
comment must include its number, as in `# [New in Deneb:EIP4844]`. For multiple
EIPs, list them like `# [New in Deneb:EIP4844:EIP4788]`. These must be
standalone comments on their own line. Only "New" and "Modified" are allowed
keywords. `# [Removed in Deneb]` is not allowed. Removed code within functions
is not typically documented, but removed structure fields or function parameters
are, as shown below:

```python
# [Modified in Deneb]
# Removed `parameter`
```

If a function is refactored so heavily that annotations within the function body
would be impractical, omit them and add a note instead.

### Notes

Notes are paragraphs placed above a code block to give the reader insight that
comments cannot. A note should not simply restate how the item now behaves,
since that is clear from reading the item itself. Use a note only to call out a
subtle change the reader might otherwise miss.

### Deprecations

If an existing spec item is no longer needed in a newer spec, mark it as
deprecated by adding its name to the deprecation list for that item's type in
that spec's `SpecBuilder` class. Define a deprecation only in the spec where the
item is first dropped. Later specs inherit it automatically.
