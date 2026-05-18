# consensus-specs — markdown as source of truth (deep-dive)

The canonical spec is authored as Python embedded in markdown, not
as Python in `.py` files. `state_transition`, `process_block`, and
the entire executable spec live inside fenced ```python blocks under
markdown headings in `specs/<fork>/*.md`. `pysetup/` extracts them
into gitignored `.py` files at build time. Default static-analysis
tools cannot see the spec.

## A note on framing — this is a contested choice

Of the four topics in Theme 1, this is the only one whose *direction*
is not obvious. The other three (self-referential package layout,
package export boundary, directory structure) are recognisable as
unintended accumulation; very few engineers, looking at them, would
say "yes, that is what we wanted". This one is different.

The team chose markdown-as-source deliberately, and there are real
arguments for it:

- **Readability for non-implementer audiences.** Researchers,
  client-implementer reviewers, and EIP authors often read the spec
  as prose, not as code. The current arrangement lets them read
  `specs/phase0/beacon-chain.md` end-to-end as a coherent document
  with code shown in context, rendered on GitHub or on the docs
  site without a build step.
- **Diff narrative.** A pull request that changes one line of code
  in a markdown file can also update the surrounding paragraph in
  the same diff. Reviewers see the *why* alongside the *what*.
- **Literate-programming heritage** (Knuth, 1984). The premise of
  literate programming is that prose and code are co-equal
  deliverables; this codebase realises that premise more
  thoroughly than most.
- **Stable consumption pattern.** The audience that needs the spec
  most often (other client teams) consumes it as a published
  document, not as an importable package. Making the human-readable
  document the canonical artefact reflects that.

These arguments are not strawmen. A reasonable person can hold them
and conclude that the trade-off is worth it.

What this deep-dive enumerates, then, is **the cost side of that
trade-off**: the failure modes that arise specifically because the
canonical artefact is markdown rather than Python, and the chain of
downstream complexity that exists to compensate. The reader should
weigh these against the readability benefits, not as a refutation of
them. There is also a middle path the deep-dive returns to in the
fix sketch — author the spec as `.py` and *generate* the narrative
`.md` rather than the other way around — that captures most of the
literate-programming benefit while letting the toolbelt see the code.

Several other guides in this audit — the helper layer's
`is_post_<fork>` chains, the gitignored generated package, the
self-referential install, the `cache_this` shadow — exist because
the spec is invisible to static analysis at parse time. Each is
real cost-side evidence; none, on its own, settles the trade-off.

Adjacent guides:
[self-referential-package-layout.md](self-referential-package-layout.md)
(the generated output lives inside the test tree because of this
decision),
[ad-hoc-caching.md](ad-hoc-caching.md) (mechanism #8 — the
`cache_this` shadow — is invisible to static analysis for the same
root cause),
[directory-structure.md](directory-structure.md) (the layout fix
doesn't strictly require changing this, but changing this makes the
layout fix easier),
[helper-layer.md](helper-layer.md) (explains *why* the helpers must
use `is_post_<fork>` chains).

## The shape of the problem

`state_transition`, `process_block`, `process_slot`,
`get_beacon_committee` — the entire executable spec — live inside
fenced ```python blocks under markdown headings in
`specs/<fork>/*.md`. `state_transition` is at
`specs/phase0/beacon-chain.md:1370`, after the heading
`### Beacon chain state transition function`. There is no `.py`
file in the repository that defines `state_transition`.

A custom build step (`pysetup/`) walks the markdown, parses each
`python` fenced block as Python AST, matches each block to its
governing markdown heading, and emits per-fork Python modules under
`tests/core/pyspec/eth_consensus_specs/<fork>/{minimal,mainnet}.py`.
Those output files are listed in `.gitignore`. They are the files
the test suite actually imports — but neither the repo's git
history nor any IDE that opens the project has them on disk until
`make _pyspec` has run.

Default static analysis indexes `.py` files. Pyright, mypy, ruff,
IDE jump-to-definition, coverage, tree-sitter-based code indexers
— every tool in the standard Python toolbelt assumes the truth
is in `.py`. For `consensus-specs` the truth is in `.md`, with a
build step in between. The gap between the two is the source of a
class of problems that the comparable repos simply do not have,
because they write the spec as Python.

A concrete demonstration: a code-graph indexer pass over the repo
(5 432 functions) resolves `find_callers` on
`state_transition_and_sign_block` to 20 concrete callers — that
helper lives in a `.py` file. The same query for the canonical
`state_transition` returns **0 callers**. `grep -rn '^def
state_transition\b' --include='*.py'` finds nothing;
`--include='*.md'` finds it at `specs/phase0/beacon-chain.md:1370`.
Any indexer that walks `.py` only misses *the central function of
the entire spec* because it lives in a file extension the indexer
doesn't parse.

## Proof, by line

### The extraction pipeline

`pysetup/md_to_spec.py` is the markdown→Python extractor.
`MarkdownToSpec.__init__` (`md_to_spec.py:20–50`) holds a `spec`
dict with eleven slots — eleven distinct kinds-of-thing
reconstructed from prose, headings, fenced code, and tables.
`_process_child` (`:86–102`) dispatches on element type:
`Heading`, `FencedCode`, `Table`, `HTMLBlock`. Each element type
populates a different subset of the eleven dicts.

The heading-vs-class contract is at `_process_code_class`
(`:171–187`):

```python
if class_name != self.current_heading_name:
    raise Exception(
        f"class_name {class_name} != current_name {self.current_heading_name}"
    )
```

The contract between markdown and Python is enforced by string
equality between an `ast.ClassDef.name` and a markdown heading's
trailing `CodeSpan` text. `_get_name_from_heading` (`:462–467`)
returns `None` if the heading's last child isn't a `CodeSpan`,
silently giving up rather than warning.

`_process_table` (`:189–267`) reconstructs constants, preset
variables, config variables, custom types, and "func-dep presets"
from table cells via a chain of string-prefix tests: starts with
`"uint"` / `"Bitlist"` / `"Vector"` → custom type; starts with
`"get_generalized_index"` → SSZ-dep constant; description starts
with `"<!-- predefined -->"` → func-dep preset; name in
`self.preset` → preset variable. None of these is a typed schema —
each is a string-prefix-or-comment match embedded in the parser.

`_process_html_block` (`:410–431`) handles two HTML-comment escape
hatches: `<!-- eth_consensus_specs: skip -->` and
`<!-- list-of-records:<name> -->`. Behaviour is keyed on literal
comment text.

The output is assembled by `objects_to_spec` (`helpers.py:47–258`):
sixteen `reduce(lambda txt, builder: ...)` /
`reduce(lambda obj, builder: ...)` calls (`:86–204`), each
concatenating fork-builder string fragments —`imports()`,
`classes()`, `preparations()`, `sundry_functions()`, plus per-fork
deprecation/optimisation/hardcoded-constant overrides — into one
large string. That string is written to disk as
`<fork>/{minimal,mainnet}.py` (`generate_specs.py:230–242`).

### The build-time gating

`setup.py:3–8` documents the architecture in its own header
comment: *"The spec generation logic has been moved to
pysetup/generate_specs.py and is now called explicitly by the
Makefile before package installation. To generate specs, run: make
_pyspec."* All 28 lines of `setup.py` are package-configuration —
none run the generator. `pip install .` does not produce a working
install. `Makefile:186–188` defines `_pyspec` as `python -m
pysetup.generate_specs --all-forks`; every higher-level target
(`test:221`, `lint:276`, `serve_docs:261`, `comptests:312`) lists
`_pyspec` as a prerequisite. PEP 517 / PEP 660 / `pip install -e`
all leave the package half-initialised. `generate_specs.py:339`
writes output to `Path("tests/core/pyspec/eth_consensus_specs") /
fork`; two `@cache`-decorated I/O loaders (`load_preset:66`,
`load_config:85`) memoise YAML reads for the process lifetime.

### The gitignored output

`.gitignore:18–27` enumerates ten generated fork directories under
`tests/core/pyspec/eth_consensus_specs/{phase0,altair,...,eip*}/`,
one per fork. Each directory's contents are the *actual* runtime
(`phase0/minimal.py`, `phase0/mainnet.py`, `phase0/__init__.py`).
The repo therefore *ships* the markdown source and *runs* a
generated artefact that exists only after a build step that is not
part of the install.

### Fork-genealogy duplication

`pysetup/md_doc_paths.py:16–27` is the canonical fork chain — the
`PREVIOUS_FORK_OF` dict mapping each fork to its predecessor
(`PHASE0: None`, `ALTAIR: PHASE0`, …, `HEZE: GLOAS`).

`AGENTS.md:360–420` is the prose version of how to add a fork. Step
"**3. Spec generation (`pysetup/`):**" lists "Add to
`PREVIOUS_FORK_OF`", "Create SpecBuilder", "Import and register",
and step **4** parallels with `helpers/constants.py`'s `ALL_PHASES`,
`PREVIOUS_FORK_OF`, `POST_FORK_OF`. The fork ordering is therefore
in at least four places: `pysetup/md_doc_paths.py`,
`helpers/constants.py`, `Makefile`'s `ALL_EXECUTABLE_SPEC_NAMES`,
and the `AGENTS.md` prose checklist — five if you count the
`.gitignore` enumeration. Adding a fork is the canonical Shotgun
Surgery example.

## Critique / inventory

### Heading-name matching fragility

The class-vs-heading equality check at `md_to_spec.py:177–179` makes
the markdown heading load-bearing for the build. `### \`BeaconState\``
is a valid Python identifier; `### BeaconState` (without backticks)
returns `None` from `_get_name_from_heading` and the build fails
with a mis-attributed `class_name X != current_name None`. The rule
"last child must be a `CodeSpan`" is implicit in the parser, with
no schema spelling it out. A function defined under the wrong
heading or under no heading at all — the heading scrolled off
because the last `_process_heading` call was a section heading
rather than a function-name heading — silently records the wrong
owner. The contract "the most recent heading you saw is the name
of the next class you parse" has no encoding outside the parser
state machine.

### The `@cache` zoo on AST nodes and I/O

`md_to_spec.py` decorates eight functions with `functools.cache`
(lines 462, 470, 475, 487, 504, 514, 538, 575). Six key on objects
whose `__hash__` is identity-based — `Heading`, `FencedCode`,
`ast.FunctionDef`, `ast.ClassDef`. Two parses of the same markdown
produce two different sets of AST nodes that hash to two different
keys; the cache rarely hits across parses, and within one parse the
same node is unlikely to be queried twice. The decorators are
decorative.

`@cache parse_markdown(content: str)` (`md_to_spec.py:575`) is
unbounded and keyed on whole-file content. `@cache _load_kzg_trusted_setups`
plus eager `ALL_KZG_SETUPS` at `:532–535` plus a third lazy cache
in `tests/core/pyspec/eth_consensus_specs/utils/ckzg_utils.py:8` are
three independent caches over the same trusted-setup files — see
[ad-hoc-caching.md](ad-hoc-caching.md) for the full inventory.

These caches are not the worst thing in `md_to_spec.py`. They are
the *most legible symptom* of the worst thing: a parser written
against the AST of an extracted code block, with no test coverage
that demonstrates the AST identity actually changes between calls,
and no clear ownership of when the parser is supposed to reset.

### No tests for the markdown→Python extraction

There is no `pysetup/test_md_to_spec.py`. The extractor that produces
the entire executable spec has no characterisation tests. Feathers
(*Working Effectively with Legacy Code*, 2004) calls characterisation
tests the first move when working with code that has no safety
net; this code has no safety net and is a build-time prerequisite
for every other test in the project. The parser's only validation
is the downstream test suite — which runs *after* the parser has
produced output it accepts. A class of bugs ("the parser silently
produced wrong code that the spec tests happen not to exercise")
is structurally invisible.

### Multi-source-of-truth on the same data

The fork chain lives in five places, none referencing the others as
the source of truth: `pysetup/md_doc_paths.py:16–27` (canonical
`PREVIOUS_FORK_OF`), `helpers/constants.py` (parallel
`PREVIOUS_FORK_OF`, `POST_FORK_OF`, `ALL_PHASES` for the test
layer), `Makefile`'s `ALL_EXECUTABLE_SPEC_NAMES`, `AGENTS.md:360–420`
(prose checklist), and `.gitignore:18–27` (per-fork output paths).
The broader audit §10 listed the AGENTS-vs-pysetup pair; the
fuller picture is five-place. Hunt & Thomas Tip 11 ("DRY") catches
the code duplication; Tip 18 ("Don't repeat yourself in
documentation") catches the AGENTS.md instance.

### The static-analysis blind spot (the load-bearing one)

A tree-sitter-based code-graph indexer over the repo (5 432
functions) resolves `find_callers` on
`state_transition_and_sign_block` to 20 concrete call-sites with
file paths and arguments — that helper is in a `.py` file. The
same query for the canonical `state_transition` returns 0 callers.
The indexer's tree-sitter pass parses `.py` only; the canonical
function lives in `specs/phase0/beacon-chain.md:1370`, so it is
not a node in the graph at all. Test code that calls it produces
`full_call_name = "state_transition"` edges with no resolved
target — edges pointing at a function that, from the graph's
perspective, does not exist.

This is not specific to any one tool. Pyright behaves the same
way (the canonical definition is invisible until `make _pyspec`
regenerates the per-fork `.py` modules; those files are
gitignored and many IDE configurations skip gitignored content).
VSCode's "go to definition" either fails or jumps to the
generated copy. Coverage tools attribute hits to generated files
whose paths move between builds.

The downstream effect is foundational: the helper layer
([helper-layer.md](helper-layer.md)) cannot introspect the spec
the way `leanSpec`'s helpers can introspect their Pydantic types,
because at the time the helper is being written *the spec does not
exist as Python*. The helper has no choice but to fall back on
`is_post_<fork>(spec)` runtime branching. The shape of the helper
layer is downstream of this.

### The test-vector format problem

`tests/formats/` contains markdown files describing the YAML/SSZ
test-vector formats consumed by every other client. The
test-vector formats are themselves a spec, and that spec is not
machine-readable: no JSON-Schema export, no OpenAPI/Pydantic
model. A client team writing a YAML loader for
`tests/formats/operations/attestation.md` reads the prose and
writes parsing code by hand. Same disease as the spec proper, at
the test-vector layer.

### `setup.py` defers everything to Make

`setup.py` cannot be a normal Python `setup.py` because the package
source it would point at *does not exist on disk* until `pysetup`
has run. The minimal-defer-to-Make pattern is downstream of "spec
lives in markdown".

## Named anti-patterns

- **Comments-as-Deodorant** (Fowler, *Refactoring*, 1999, p. 87) —
  in literate-spec form the prose *is* the comment for the code
  below it; every Python construct must be surrounded by enough
  prose to make it a publishable specification.
- **Stringly-Built Code** (Fowler, sub-form of Stringly Typed) —
  `objects_to_spec` (`helpers.py:47–258`) builds the runtime spec
  via string concatenation across sixteen `reduce` passes. Compiler
  errors, type errors, and lint errors only manifest when the
  concatenated output is finally re-parsed by Python.
- **Shotgun Surgery** (Fowler, p. 79) — the fork chain in five
  places; adding a function to the markdown requires re-running
  Make and regenerating the gitignored per-fork output.
- **Divergent Change** (Fowler, p. 77) — `md_to_spec.py` changes
  for new constant kinds in tables, new HTML-comment escape
  hatches, new fork-builder string-injection points, new SSZ
  encodings. One module, four orthogonal reasons to change.
- **Inappropriate Intimacy at the boundary** (Fowler, p. 85) — the
  parser knows that the next class definition belongs to the most
  recent heading; the heading and the class are coupled by
  *temporal proximity in markdown*, an artefact of authoring order
  rather than a typed contract.
- **Module-level DIP violation** (Martin, *Clean Architecture*,
  ch. 5) — `tests/`, `pysetup/`, and `setup.py` depend on
  `specs/<fork>/*.md` by file path and heading text. The dependency
  is on a string match in a file with no schema.
- **Missing-boundary check at a system seam** (Martin) — the
  boundary between markdown and Python is unguarded: no schema for
  what a `### \`X\`` heading promises, no test for "every fenced
  Python block has a parent heading", no validation between
  extraction and emission.
- **Self-validating tests violation** (Beck, *TDD*, 2002 — FIRST) —
  the parser has no self-validating tests; its only validation is
  the integration test suite that runs *after* it produces output
  the suite accepts.
- **Literate-programming half-step** (Knuth, *Literate Programming*,
  1984) — Knuth's WEB tangles a single source into both
  documentation and runnable code, with the runnable code as a
  build product. `consensus-specs` has the tangle (`pysetup`) and
  the weave (publishing markdown), but the tangle's output is
  gitignored, untooled, and second-class. The project has
  literate-programming's costs (custom extractor, string-template
  assembly, build-time gating) without literate-programming's
  benefit (a single source from which *both* deliverables are
  first-class).

## Comparable contrast

This is the section where the comparables most clearly outclass the
project. Both write the spec as Python directly. Every piece of
default tooling Just Works.

### `leanSpec`

`leanSpec/src/lean_spec/forks/lstar/spec.py` is the spec — a
hand-edited Python file. State-transition functions have type
annotations resolving to Pydantic models in
`leanSpec/src/lean_spec/types/` (`ValidatorIndex`, `Slot`, `Bytes32`,
`Checkpoint`). Every standard tool works on it:

- mypy / Pyright type-check it; jump-to-type-definition works.
- IDE jump-to-definition resolves every function, type, and
  method. `find_callers` (or "find all references") for a
  state-transition function returns concrete call sites.
- Coverage hits attribute to the spec source itself, not a
  generated artefact whose path moves between builds.
- IDE rename works.
- **Helpers introspect typed spec objects.** There is no
  `is_post_<fork>` chain because helpers use `isinstance`,
  `issubclass`, and typed dispatch on the spec types directly.

The spec doubles as API documentation: docstrings, annotations as
contracts, runnable examples in tests. One source of truth.

### `execution-specs`

`execution-specs/src/ethereum/forks/<fork>/` is the spec. WET per
fork — each fork directory is a complete Python module that copies
the previous fork's contents and edits in place. A different
trade-off than `leanSpec` (more duplication, easier per-fork
reasoning), but the core property is the same: **the spec is Python,
not markdown**. Every fork's `state_transition` is a `def` in a
`.py` file.

The WET-per-fork model is one `consensus-specs` could not adopt
without first authoring the spec as Python — there is nothing to
copy.

### What both comparables avoid

No `pysetup/` equivalent. No gitignored runtime. No build-time-gated
install — `pip install -e .` works. No heading-vs-class consistency
check (there are no headings). No five-place fork-chain duplication.
No `cache_this`-via-string-template (performance shims are real
Python decorators). No `is_post_<fork>` chain in helpers.

The comparables are not better because they wrote a better
markdown→Python extractor. They are better because **they didn't
write one**.

## Why this is load-bearing

This finding sits underneath every other finding in the audit.

- **The helper layer's `is_post_<fork>` chains**
  ([helper-layer.md](helper-layer.md)) exist because helpers cannot
  introspect a spec that does not yet exist as Python. Authoring
  the spec as Python would let helpers use type-driven dispatch
  instead. The chain pattern is not a cleanup target — it is the
  only viable design given that the spec is markdown.
- **The self-referential package layout**
  ([self-referential-package-layout.md](self-referential-package-layout.md))
  exists because the build target needs *somewhere* to write the
  generated `.py` files; the path of least resistance was "next to
  the tests that import them".
- **The directory structure**
  ([directory-structure.md](directory-structure.md)) — six of the
  top-level content directories are kinds of markdown. They exist
  because the spec is markdown. Consolidation is possible
  regardless; eliminating the markdown bucket entirely is only
  possible by authoring the spec as Python.
- **`cache_this` shadow** ([ad-hoc-caching.md](ad-hoc-caching.md),
  mechanism #8) lives inside a Python *string template* in
  `pysetup/spec_builders/phase0.py:47–104`. The string is invisible
  to ruff, mypy, and Pyright for the same root cause:
  code that lives inside a string until `make _pyspec` runs is not
  code as far as static analysis is concerned. The same applies to
  every `imports()`, `classes()`, `preparations()`, and
  `sundry_functions()` fragment across the ten fork builders.
- **`setup.py`'s minimal-defer-to-Make** is the visible shape of
  "the package source isn't on disk at install time".
- **`.gitignore`'s ten generated-fork lines** are the visible shape
  of "the runtime is a build artefact". The count grows with every
  fork.
- **Test-vector formats in markdown** is the same disease at the
  test-vector layer: a structured wire format encoded in prose.

That's the test of a foundational issue: the local fixes do help,
but they are working around the same upstream cause.

## What fixing it would entail

This is the biggest fix in the audit; there are three families, in
increasing ambition.

**(a) Author the spec as Python.** Rewrite `specs/<fork>/*.md` as
`src/eth_consensus_specs/<fork>/*.py`, with the prose either deleted
in favour of docstrings or moved to a sibling `.md` whose
relationship to code is one-of-reference rather than embedded. This
is what both comparable repos do. The cost is coordination — the
markdown form has a decade of client-team and EIP-process buy-in,
and rendered-prose expectations on the github.com surface. The
code-change problem is the smaller half.

**(b) Keep markdown, ship the build at install time.** Write a PEP
517 build backend so `pip install .` produces a working install
without `make _pyspec`. The generated package lands at
`src/eth_consensus_specs/`. `.gitignore`'s ten lines collapse to one.
The self-referential-layout problem dissolves. Static analysis still
sees only the output, but at least the output is reliably present
and at a sane path. This does not address the helper-layer
`is_post_<fork>` problem or the `cache_this`-in-string-template
problem — the spec is still invisible to tools that only walk
authored sources.

**(c) Hybrid — author Python, generate markdown.** Invert the
pipeline: spec is Python with rich docstrings, the markdown is the
build artefact (for publication). Costs a new build tool that walks
Python AST and emits markdown. Benefits: every standard tool sees
the spec as Python; publishable-prose consumers still get markdown.

The strongest claim in this report: only (a) and (c) make most of
the audit findings go away. (b) is a real improvement but leaves the
load-bearing static-analysis blind spot intact, because the source
the developer authors is still markdown.

**Pytest-plugin angle.** The `@vector_test` decorator and yield-
collection machinery at `tests/infra/yield_generator.py` is
essentially a hand-rolled pytest plugin without the
`pytest_plugins` declaration — the dual-mode flags (`is_pytest`,
`is_generator`) exist precisely because the same code is invoked
from two different harnesses. Splitting into a real pytest plugin
(for the test-runner path) plus a generator CLI (for vector
synthesis) is mentioned in
[decorator-stack.md](decorator-stack.md)'s fix sketch; the
relevance to *this* deep-dive is that a typed-yield plugin can
also validate yields against a schema, replacing the duck-typed
SSZ inference at `tests/infra/yield_generator.py:26–45` (Stringly
Typed) with explicit per-yield-type marker semantics
(`@pytest.mark.yields("ssz")`, `@pytest.mark.yields("meta")`) and
a Pydantic model per fixture variant. This is independent of the
markdown→Python question and is doable today; it's an incremental
quality improvement to the plugin layer that already exists.

## References

Related guides:
- [self-referential-package-layout.md](self-referential-package-layout.md)
  — the generated output lives inside the test tree because of
  this; dissolved by (a) or (c), partly by (b).
- [ad-hoc-caching.md](ad-hoc-caching.md) — mechanism #8
  (`cache_this` shadow) is invisible to static analysis for the
  same root cause.
- [directory-structure.md](directory-structure.md) — the layout
  fix doesn't strictly require changing this, but changing this
  makes the layout fix much easier.
- [helper-layer.md](helper-layer.md) — explains *why* the helpers
  must use `is_post_<fork>` chains.
- [package-export-boundary.md](package-export-boundary.md) — the
  reason the runtime spec is bundled into the same wheel as the
  test suite is partly that it has no canonical `.py` home; once
  the spec is authored as code, splitting the distribution into a
  runtime wheel and a testing wheel becomes the obvious shape.

The static-analysis blind spot section above is the demonstration:
any tree-sitter-based code indexer finds 0 callers for
`state_transition` because the canonical function is at
`specs/phase0/beacon-chain.md:1370`, not in any `.py` file.

External references:

- Fowler, *Refactoring* (1999) — Comments-as-Deodorant (p. 87);
  Stringly Typed (sub-form); Shotgun Surgery (p. 79); Divergent
  Change (p. 77); Inappropriate Intimacy (p. 85).
- Martin, *Clean Architecture* — module-level DIP; missing-
  boundary-check at a system seam.
- Feathers, *Working Effectively with Legacy Code* (2004) —
  characterisation tests; hidden test seams when spec-as-defined
  and spec-as-tested diverge.
- Hunt & Thomas, *The Pragmatic Programmer* — Tip 11 (DRY); Tip 18
  (don't repeat yourself in documentation); Tip 38 ("Configure,
  don't integrate") on the string-prefix-driven table parser.
- Beck, *Test-Driven Development* (2002) — FIRST, the
  Self-validating property absent in `pysetup/`.
- Knuth, *Literate Programming* (1984) — context for what literate
  programming was supposed to be (single source, both deliverables
  first-class) versus what's here (markdown source, Python
  deliverable second-class and gitignored).
