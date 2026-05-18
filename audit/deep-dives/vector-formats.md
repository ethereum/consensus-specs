# consensus-specs — vector formats (deep-dive)

The published cross-client test vectors live under thirty-plus
distinct format specifications in `tests/formats/`, each with its own
markdown README, its own field-naming conventions, and its own runner
contract. Looking past surface differences, most of them collapse
into two underlying patterns: a state-transition shape
(`pre.ssz_snappy` + some input + `post.ssz_snappy`) and a
pure-function shape (`data.yaml` with `input:` and `output:` keys).
Roughly thirty-five of the formats are parameterisations of one of
these two patterns; only a handful are genuinely multi-step protocols
that need their own format. The fragmentation isn't malicious — each
format was added when its handler was implemented, and each handler
had a small justification for tweaking the previous shape — but the
end state is N near-identical specs with no shared abstraction.

Adjacent guides:
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md) (the
format READMEs are the same kind of "markdown is the spec" pattern),
[ssz-generic-vectors.md](ssz-generic-vectors.md) (the SSZ generic
format is one of the Category B formats; its tautological-oracle
problem is orthogonal to the format-shape problem),
[compliance-runners.md](compliance-runners.md) (the fork-choice
format is one of the multi-step Category C formats),
[helper-layer.md](helper-layer.md) (the runners that consume these
formats live in `tests/core/pyspec/.../helpers/` and inherit its
shape problems).

## The shape of the problem

Run `find tests/formats -name '*.md'` and the result is forty markdown
files. Read enough of them and you find that almost all are saying
the same two things in slightly different ways.

For a typical Category A format (operations, epoch_processing,
rewards, finality, sanity/blocks, sanity/slots, transition,
genesis/initialization, genesis/validity, forks):

- A `meta.yaml` with a `description` and a few format-specific
  fields.
- A `pre.ssz_snappy` containing a `BeaconState`.
- One or more SSZ-snappy or YAML files containing the *input* — the
  operation, the block list, the slot count, the fork name, the eth1
  data, etc.
- A `post.ssz_snappy` containing the resulting `BeaconState`, or no
  `post.ssz_snappy` at all (= the operation should be rejected).
- A *Condition* paragraph that says "the resulting state should
  match `post`, or if `post` is absent, reject the input".

For a typical Category B format (BLS sign/verify/aggregate, KZG
proofs, networking primitives, shuffling, light_client merkle
proofs):

- A `data.yaml` with two top-level keys: `input:` (a dict of
  function arguments) and `output:` (the expected return value, or
  `null`/`None` if the input should be rejected).
- A *Condition* paragraph that says "the handler should compute
  `f(input)`, and the result should match `output`; if `input` is
  invalid the result should be `null`".

That's two patterns. Each is a textbook input/operation/output
test — the kind of thing a single typed schema captures cleanly. The
codebase has neither the schema nor the unification; instead it has
~35 markdown files describing one of two shapes.

## Proof, by line

### Category A: `pre + input + post` (state-transition family)

| Format | Input naming | Inputs | `post` shape | Distinct `meta.yaml` fields |
|---|---|---|---|---|
| `operations` | `<operation-name>.ssz_snappy` plus optional `execution.yml` | 1 SSZ + 1 YAML | one `post.ssz_snappy` (or absent) | `bls_setting` |
| `epoch_processing` | (none — the sub-transition is named by directory) | 0 | one `post.ssz_snappy` (plus optional `pre_epoch`/`post_epoch`) | `bls_setting` |
| `rewards` | (none — the rewards function is named by handler) | 0 | five SSZ files: `source_deltas`, `target_deltas`, `head_deltas`, `inclusion_delay_deltas`, `inactivity_penalty_deltas` | (none beyond description) |
| `finality` | `blocks_<index>.ssz_snappy` (and `blocks_<index>.yaml`) | N SSZ blocks | one `post.ssz_snappy` | `bls_setting`, `blocks_count` |
| `sanity/blocks` | `blocks_<index>.ssz_snappy` | N SSZ blocks | one `post.ssz_snappy` | `bls_setting`, `reveal_deadlines_setting`, `blocks_count` |
| `sanity/slots` | `slots.yaml` (an integer) | 1 YAML | one `post.ssz_snappy` | `bls_setting` |
| `transition` | `blocks_<index>.ssz_snappy` (with `fork_block` index in meta) | N SSZ blocks | one `post.ssz_snappy` | `post_fork`, `fork_epoch`, `fork_block`, `blocks_count` |
| `genesis/initialization` | `eth1.yaml` + `deposits_<index>.ssz_snappy` + optional `execution_payload_header.ssz_snappy` | 1 YAML + N SSZ + optional SSZ | one `state.ssz_snappy` (named `state`, not `post`) | `deposits_count`, `execution_payload_header` |
| `genesis/validity` | `genesis.ssz_snappy` (named `genesis`, not `pre`) | 1 SSZ (the candidate) | `is_valid.yaml` (a boolean — not a state) | (none beyond description) |
| `forks` | (none — `pre` is enough; the fork name is in `meta.yaml`) | 0 | one `post.ssz_snappy` (different SSZ type than `pre`) | `fork` |
| `random` (delegates to `sanity/blocks`) | — | — | — | — |

Eleven entries; nine of them are `pre + input(s) + post`. Two
(`genesis/initialization`, `genesis/validity`) rename `pre` → `genesis`
or rename `post` → `state`/`is_valid` but the underlying shape is the
same.

### Category B: `data.yaml { input, output }` (pure-function family)

| Format | `input:` keys | `output:` shape |
|---|---|---|
| `bls/sign` | `privkey: bytes32`, `message: bytes32` | `BLS Signature` (or `null`) |
| `bls/verify` | `pubkey: bytes48`, `message: bytes32`, `signature: bytes96` | `bool` |
| `bls/aggregate` | `List[BLS Signature]` | `BLS Signature` |
| `bls/aggregate_verify` | `pubkeys: List[bytes48]`, `messages: List[bytes32]`, `signature: bytes96` | `bool` |
| `bls/eth_aggregate_pubkeys` | `List[bytes48]` | `bytes48` |
| `bls/eth_fast_aggregate_verify` | `pubkeys`, `message`, `signature` | `bool` |
| `bls/fast_aggregate_verify` | `pubkeys`, `message`, `signature` | `bool` |
| `kzg_4844/blob_to_kzg_commitment` | `blob: Blob` | `KZGCommitment` |
| `kzg_4844/compute_blob_kzg_proof` | `blob`, `commitment` | `KZGProof` |
| `kzg_4844/compute_challenge` | `blob`, `commitment` | `BLSFieldElement` |
| `kzg_4844/compute_kzg_proof` | `blob`, `z` | `(KZGProof, BLSFieldElement)` |
| `kzg_4844/verify_blob_kzg_proof` | `blob`, `commitment`, `proof` | `bool` |
| `kzg_4844/verify_blob_kzg_proof_batch` | three lists | `bool` |
| `kzg_4844/verify_kzg_proof` | `commitment`, `z`, `y`, `proof` | `bool` |
| `kzg_7594/compute_cells` | `blob` | `List[Cell]` |
| `kzg_7594/compute_cells_and_kzg_proofs` | `blob` | `(List[Cell], List[KZGProof])` |
| `kzg_7594/compute_verify_cell_kzg_proof_batch_challenge` | (variants) | `bool` |
| `kzg_7594/recover_cells_and_kzg_proofs` | `cell_indices`, `cells` | `(List[Cell], List[KZGProof])` |
| `kzg_7594/verify_cell_kzg_proof_batch` | lists | `bool` |
| `networking/compute_columns_for_custody_group` | `custody_group` | `List[uint64]` |
| `networking/get_custody_groups` | (a few uints) | `List[uint64]` |
| `shuffling/core` | `seed: bytes32`, `count: int` (in `mapping.yaml` rather than `data.yaml`) | `mapping: List[int]` |
| `light_client/single_merkle_proof` | `object.ssz_snappy` (the SUT input) | `proof.yaml` with `leaf`, `leaf_index`, `branch` |
| `ssz_static/core` | `value` (an SSZ object) | `serialized` + `root` (round-trip) |

Twenty-five entries. All have an input, all have an output, all have
a "the result should match the expected output, or `null`/`None` if
input is invalid" condition. Two (`shuffling`, `light_client/
single_merkle_proof`) use a non-`data.yaml` filename for the same
shape; one (`ssz_static`) flattens `output` into multiple top-level
files; otherwise the schema is uniform under the names.

### Category C: genuinely multi-step protocols

| Format | Why it doesn't fit |
|---|---|
| `fork_choice` | Multi-step replay (tick / block / attestation / checks) with intermediate state observations. Stateful protocol. |
| `light_client/sync` | Multi-step sync with stateful update ranking and timeouts. |
| `light_client/data_collection` | Streaming data-collection protocol. |
| `light_client/update_ranking` | Pairwise comparison of `LightClientUpdate`s. |
| `networking/gossip_validation` | Multi-message validation with timing offsets and per-message expected verdicts. |
| `fast_confirmation` | Multi-step protocol involving votes and confirmation states. |
| `sync` (delegates to `fork_choice`) | — |

Seven entries (with one delegate). These are genuinely different
shapes — they don't reduce to a single input/output pair.

## Critique

### One pattern, ten READMEs (Category A)

Reading the operations, epoch_processing, finality, sanity/blocks,
sanity/slots, transition, and forks READMEs side by side is a
strange experience. Each says the same things in slightly different
words: "Here is `meta.yaml`. Here is `pre.ssz_snappy`, an SSZ-snappy
encoded `BeaconState`. Here are some inputs. Here is
`post.ssz_snappy`, the state after applying the operation. The
runner should call the corresponding processing function. The
resulting state should match `post`, or if `post` is absent, the
runner should reject the operation as invalid." The same condition
in eight or nine paraphrases.

The differences between formats are mostly cosmetic:

- **Input naming.** `<operation-name>.ssz_snappy` for operations,
  `slots.yaml` for sanity/slots, `eth1.yaml` for genesis/initialization.
  Could be a single `input.yaml` or a typed input model with
  named fields.
- **`pre`/`post` renaming.** `genesis/validity` calls them `genesis`
  and `is_valid`; `genesis/initialization` calls the post `state`.
  Could be `pre`/`post` everywhere with an optional alias in the
  schema.
- **Per-format `meta.yaml` fields.** `bls_setting`, `blocks_count`,
  `fork_block`, `post_fork`, `deposits_count`, etc. Most are
  derivable from the input file count or the format's own metadata.
- **Multi-output cases.** `rewards` has five `*_deltas.ssz_snappy`
  files instead of one `post.ssz_snappy`. Could be a single
  `output.yaml` or a typed output model with named fields, with
  multi-file emission as one of the rendering options.

Underneath, every Category A format is "given some pre-state and
some input, run the spec function, the result is a post-state
or a rejection." That is a single schema, not ten.

DRY violation (Hunt & Thomas, *The Pragmatic Programmer*, Tip 11)
at the format-spec level. Divergent Change (Fowler, *Refactoring*,
1999, p. 77) when the test-vector format needs to evolve — a change
to "how do we represent rejection?" or "what's in `meta.yaml` by
default?" is a ten-place edit.

### One pattern, twenty-five READMEs (Category B)

The Category B formats are even more uniform. Twenty-five distinct
markdown READMEs each saying:

> The test data is declared in a `data.yaml` file:
>
> ```yaml
> input:
>   <field>: <type>
>   ...
> output: <type>
> ```
>
> The handler should compute `<function>(input)`, and the result
> should match the expected `output`. If the input is invalid, the
> result should be `null`.

Different inputs, different outputs, same template. The natural
shape is one schema: `{ input: typed-dict, output: typed-value | None }`,
parameterised by the function being tested. The twenty-five READMEs
are twenty-five copies of the same template with different field
names.

### Two outliers worth calling out

- **`shuffling/core`** uses `mapping.yaml` (with `seed`, `count`,
  `mapping` keys) instead of `data.yaml` (with `input`, `output`).
  Same content, different file naming. Either it's a Category B
  format with a stale name, or the project never picked a
  convention.
- **`light_client/single_merkle_proof`** splits the input
  (`object.ssz_snappy`) and output (`proof.yaml`) across two files
  instead of putting them in one `data.yaml`. Same content, different
  packaging. Looks like a Category B format that came in late and
  followed the Category A multi-file pattern by mistake.

### Pre/post naming asymmetry

The `pre` / `post` convention is almost universal in Category A but
not quite:

- `genesis/initialization` calls the output `state.ssz_snappy`, not
  `post.ssz_snappy`.
- `genesis/validity` calls the input `genesis.ssz_snappy`, not
  `pre.ssz_snappy`, and the output `is_valid.yaml`, not
  `post.ssz_snappy`.
- `forks` keeps `pre`/`post` but the SSZ types of the two are
  different — `pre` is a pre-fork `BeaconState`, `post` is a
  post-fork `BeaconState` (a different SSZ type).

These are small inconsistencies and they're load-bearing: a runner
written generically against `pre` and `post` doesn't work for the
genesis tests without a per-format alias. Inappropriate Intimacy
(Fowler, p. 85) between the runner code and the file-naming
convention.

### `null` vs absent-file vs `output: null`

How is "input is invalid, the operation should be rejected"
expressed? Three different ways across the formats:

- **Category A:** the absence of a `post.ssz_snappy` file means the
  runner should expect rejection.
- **Category B:** an explicit `output: null` (or `output: ~` in
  YAML) inside `data.yaml`.
- **`genesis/validity`:** `is_valid.yaml` is a boolean, with `false`
  meaning "the state is not valid as genesis".

Three encodings of the same concept. A typed schema would unify them
on `output: T | None`.

### Multi-output cases broaden the asymmetry further

- **`rewards`** has five separate `*_deltas.ssz_snappy` output files,
  one per rewards-function call. The runner runs five different
  functions and asserts each output matches its file.
- **`epoch_processing`** has both `post.ssz_snappy` (after the
  named sub-transition) and optional `pre_epoch.ssz_snappy` /
  `post_epoch.ssz_snappy` (before / after the full epoch
  transition). Two parallel scopes in one format.

Both could be expressed as a typed multi-output structure (a list of
named outputs) but neither is.

### The READMEs are the spec

There is no schema — no Pydantic model, no JSON Schema, no
`pytest_generate_tests`-driven validator — that captures any of these
formats. The runners (in five-plus client languages) read the
READMEs and implement against them. When the format evolves, every
client's runner has to be updated by re-reading the README. This is
the same pattern covered in
[markdown-as-source-of-truth.md](markdown-as-source-of-truth.md),
applied to the test-vector layer instead of the spec layer.

## Named anti-patterns

- **DRY violation** (Hunt & Thomas, *The Pragmatic Programmer*, Tip
  11) — every Category A format restates the `pre + input + post`
  template; every Category B format restates the `data.yaml { input,
  output }` template. Forty markdown files for two patterns plus a
  handful of genuine variants.
- **Divergent Change** (Fowler, *Refactoring*, 1999, p. 77) — a
  change to the underlying pattern (e.g. "all formats should declare
  their bls_setting") is a ten-or-twenty-place edit because each
  format spec is a separate document.
- **Speculative Generality** (Fowler, p. 109) at the README level —
  every format was specified separately "just in case it needs to
  diverge from its peers"; in practice, ~35 of them are
  parameterisations of one of two underlying shapes.
- **Inappropriate Intimacy** (Fowler, p. 85) between runners and
  file-naming conventions — a generic runner can't consume both
  `pre/post` and `genesis/state` formats without per-format aliasing
  logic. The naming inconsistencies are baked into runner code in
  every client language.
- **Stringly Typed** (Fowler, sub-form) — `output: null`,
  `is_valid: false`, and absent-`post.ssz_snappy` are three string-
  level encodings of the same boolean concept (`should be rejected`).
- **Markdown-as-spec** (cross-cuts
  [markdown-as-source-of-truth.md](markdown-as-source-of-truth.md))
  — the format is what the README says; client implementations
  diverge in the corners the README doesn't pin down.

## Comparable contrast

`leanSpec` and `execution-specs` both express their test fixture
formats as **typed Python models**, not as markdown READMEs. The
fixture is the schema; the format is what the model serialises to.

- `leanSpec/packages/testing/src/consensus_testing/test_fixtures/`
  declares Pydantic-based fixture classes
  (`StateTransitionTestFiller`, `ForkChoiceTestFiller`, etc.). Each
  is a typed model with an `output_dir`, a list of inputs, and a
  declarative output. The fillers serialise to JSON via
  `model_dump(mode="json")`. The "format" of a state-transition
  test vector is the JSON shape the model produces — a single
  Pydantic model, not a markdown document.
- `execution-specs/packages/testing/src/execution_testing/test_fixtures/base.py`
  declares `BaseFixture` with `@field_serializer` annotations
  controlling how each field is serialised. Concrete fixture types
  (`BlockchainFixture`, `StateFixture`, `EOFFixture`) extend
  `BaseFixture`. The serialisation is the format; there's no separate
  markdown spec.

Both projects converge on the same shape: **a typed model is the
format spec**. The format documentation, if any, is generated from
the model (or referenced inline in the model's docstrings). New
fixture types are subclasses of an existing base; they inherit the
metadata fields, the rejection convention, the SSZ encoding rules,
without restating them.

In both projects, "I want to add a new state-transition test format"
is "subclass `StateTransitionTestFiller`" — not "write a new markdown
README and update each client runner". The DRY level at the format
layer is exactly what consensus-specs lacks.

## Why this is load-bearing

The vector formats are the contract between consensus-specs and the
ecosystem. Five-plus client implementations consume them. Every
format change is a coordinated multi-client release. The
fragmentation matters for three reasons:

1. **Format evolution is harder than it should be.** Adding a field
   to the runner contract — say, a `release_setting` flag analogous
   to `bls_setting` — requires editing every Category A README,
   every Category B README, and coordinating with each client
   implementation to update its runner. A single typed model would
   make this one change.

2. **New formats are added by copy-paste.** When a new spec feature
   needs a new test-vector format (recently:
   `progressive_list`, `compatible_union`, the various KZG-7594
   handlers), the easiest path is to copy an existing README and
   tweak. Each new format inherits the conventions plus a chance to
   introduce a new minor inconsistency. The format zoo grows
   monotonically.

3. **Runner authors implement against prose.** A client team writing
   a runner reads the README, infers the schema, and writes parsing
   code. Two clients reading the same README make different
   inferences in the corners — `output: null` vs `output: ~` vs
   `output:` (empty), `bls_setting: 0` vs `bls_setting: 1` vs
   default. Cross-client disagreement on edge cases is a real
   bug-source.

This is *not* a "fix the formats and everything else is easier"
deep-dive — the formats themselves are sound. It's a "the same
patterns are repeated thirty-five times in markdown when one Pydantic
class would do" deep-dive. The benefit is multiplicative on every
future format addition and every cross-client coordination.

## What fixing it would entail

A staged sketch:

1. **Define two base schemas.** A `StateTransitionCase` Pydantic
   model with `meta`, `pre: BeaconState`, `inputs: dict[str,
   FilePath]`, `outputs: dict[str, FilePath | None]`, plus a
   `should_reject: bool` derived field. A `PureFunctionCase` model
   with `meta`, `inputs: dict[str, Value]`, `output: Value | None`.
   Both serialise to a directory-of-files layout that matches the
   current vector convention (so existing client runners still
   work).

2. **Express each Category A format as a `StateTransitionCase`
   subclass.** Operations, epoch_processing, rewards, finality,
   sanity/blocks, sanity/slots, transition, genesis/initialization,
   genesis/validity, forks. Each subclass defines its own
   format-specific metadata fields and its own `inputs`/`outputs`
   shape. The shared schema lives in the base; the divergent shape
   is local to the subclass.

3. **Express each Category B format as a `PureFunctionCase`
   subclass.** All twenty-five — BLS, KZG-4844, KZG-7594, networking,
   shuffling, single_merkle_proof, ssz_static. Same pattern.

4. **Generate the markdown READMEs from the schemas.** A
   `tools/generate_format_specs.py` walks the schema classes and
   emits `tests/formats/<runner>/<handler>.md` from each model's
   docstring + field types. The READMEs become build artefacts; the
   schema is the source.

5. **Normalise the file-naming inconsistencies.** `genesis/validity`
   becomes `pre.ssz_snappy` + `output.yaml { is_valid: bool }`;
   `genesis/initialization` becomes `pre = (eth1, deposits[],
   payload_header?)` with the input model declaring those fields;
   `forks` keeps `pre`/`post` and notes the type-shift in metadata.
   The schema enforces the names; runners handle them generically.

6. **Unify the rejection encoding.** `output: null` (or `outputs:
   {}`) means "should be rejected"; absent-files become invalid.
   Schema-validate at vector-write time so the absent-file
   convention is decided at schema level, not by mistake.

7. **Keep Category C formats as-is.** fork_choice, light_client
   sync, gossip_validation, and the few other multi-step protocols
   are genuinely different shapes and shouldn't be forced into the
   schema. Their READMEs stay; only the ~35 IOO-shaped formats
   unify.

8. **Coordinate the client transition.** The above changes the
   *Python-side authoring* surface, not the *on-disk vector layout*
   — existing runners in client languages keep working as long as
   the output paths and filenames don't change. After the
   schemas land, the format READMEs (now generated) can be
   gradually replaced with schema-derived documentation, and
   downstream runners can opt into a typed parser
   (auto-generated from the same schema).

The full fix is a complex coordination across the consensus-specs
side and the multi-client runner side, but the transition plan
above lets each piece land independently. The Python-side schema
work alone is bounded — the schema classes are small, the
format-document generator is straightforward, and the existing
on-disk vector format can stay frozen during the transition.

**Pytest-plugin / fixture angle.** This is the same shape as
[helper-layer.md](helper-layer.md)'s recommendation for typed
fixture-based test data: the `StateTransitionCase` and
`PureFunctionCase` base classes are exactly what
`@pytest.fixture(scope="session")` factory fixtures consume. A
typed-yield plugin (referenced in
[ssz-generic-vectors.md](ssz-generic-vectors.md) and
[decorator-stack.md](decorator-stack.md)) emits the cases through
the schema layer rather than through the current `(name, kind,
value)` tuple protocol. The yield protocol becomes:
`yield StateTransitionCase(meta=..., pre=..., inputs={...},
outputs={...})` instead of `yield "value", "data", encode(value)`.
The schema layer handles serialisation; the test author writes a
typed Python value.

Concretely, the
[decorator-stack.md](decorator-stack.md) plugin rework, the
[ssz-generic-vectors.md](ssz-generic-vectors.md) typed-yield work,
and this format-unification work all converge on the same
shape: `the test yields a Pydantic model; the framework serialises
it to disk in the canonical vector layout`. Doing them together is
cheaper than doing them sequentially, because they share the
schema-class hierarchy.

## References

Adjacent guides:

- [markdown-as-source-of-truth.md](markdown-as-source-of-truth.md)
  — the format READMEs are the same kind of "markdown as spec"
  problem, applied to test-vector formats; resolving that issue at
  the spec level and at the format level uses the same technique
  (typed Python models replacing markdown documents).
- [ssz-generic-vectors.md](ssz-generic-vectors.md) — the SSZ
  generic format is one of the Category B formats; the typed-yield
  protocol it would ideally use is the same one this guide
  proposes.
- [compliance-runners.md](compliance-runners.md) — the fork-choice
  format is one of the Category C multi-step formats; its
  three-source-of-truth problem (markdown spec, MiniZinc model,
  Python instantiator) is one this format-unification work
  partially addresses by replacing the markdown spec with a typed
  model.
- [helper-layer.md](helper-layer.md) — the runners that consume
  these formats live in the helper layer and inherit its
  primitive-obsession problems; typed cases at the format layer
  flow into typed parsing at the runner layer.
- [decorator-stack.md](decorator-stack.md) — the `@vector_test`
  decorator and the `(name, kind, value)` yield protocol are the
  current substitute for a typed schema; the proposed plugin
  rework supersedes them.

External references:

- Fowler, M. *Refactoring: Improving the Design of Existing Code*
  (1999) — Duplicated Code (p. 76), Divergent Change (p. 77),
  Inappropriate Intimacy (p. 85), Speculative Generality (p. 109),
  Stringly Typed (sub-form).
- Hunt, A. & Thomas, D. *The Pragmatic Programmer* — Tip 11 (DRY),
  Tip 17 (Eliminate effects between unrelated things), Tip 18
  (Don't repeat yourself in documentation), Tip 38 ("Configure,
  don't integrate") on schema-driven config.
- Martin, R. *Clean Architecture* — module-level DIP, missing-
  boundary-check at a system seam (the runner-format boundary).
- Beck, K. *Test-Driven Development* (2002) — FIRST tests; the
  shared-schema design preserves Self-validating because the
  schema is the oracle for both the generator and the runner.
- Hyrum's Law — once the on-disk format is observed by N client
  runners, every observable property becomes part of the contract;
  schema migration is then a coordinated cross-client release.
