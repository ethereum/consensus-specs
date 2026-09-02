# Execution payload envelopes by root tests

The aim of these tests is to provide reference coverage for the Gloas
`ExecutionPayloadEnvelopesByRoot v1` request and response rules. A test case
contains a request, portable fixture premises, and a transport-neutral response
trace. The runner evaluates the trace; it does not open a network connection.
This transport-neutral format evaluates decoded ReqResp results and method
semantics. It does not cover multistream negotiation, the ReqResp length prefix,
or Snappy stream framing; those require separate byte-stream vectors.

A case records assertion constraints instead of prescribing one golden response
sequence. A responder may omit unavailable envelopes and may limit its response,
so any subset and ordering permitted by the specification can be evaluated
without turning a permitted choice into a failure.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Normative source map](#normative-source-map)
- [Test case format](#test-case-format)
  - [`manifest.yaml`](#manifestyaml)
  - [`config.yaml`](#configyaml)
  - [`meta.yaml`](#metayaml)
  - [`request.ssz_snappy`](#requestssz_snappy)
  - [`fixture.yaml`](#fixtureyaml)
  - [`responses.yaml`](#responsesyaml)
  - [`expected.yaml`](#expectedyaml)
- [Conditions](#conditions)
- [Input safety and resource bounds](#input-safety-and-resource-bounds)
- [Minimum cases](#minimum-cases)
- [Determinism](#determinism)
- [Review questions](#review-questions)
- [Implementation follow-up](#implementation-follow-up)

<!-- mdformat-toc end -->

## Normative source map

The format assigns each concern to the following specification sections. The
generator and runner use the assembled PySpec for the source tree that produces
the vectors; they do not copy these semantics into a second implementation:

| Concern                                                              | Normative source                                                                 |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Request type, response type, bounds, availability, and context epoch | `specs/gloas/p2p-interface.md`, `ExecutionPayloadEnvelopesByRoot v1`             |
| Successful response object                                           | `specs/gloas/beacon-chain.md`, `SignedExecutionPayloadEnvelope`                  |
| General result codes, error payload, and result finality             | `specs/phase0/p2p-interface.md`, `Req/Resp interaction`                          |
| Empty error context and four-byte success context                    | `specs/altair/p2p-interface.md`, `Req-Resp interaction` and `ForkDigest-context` |
| Fork-digest helper                                                   | `specs/phase0/p2p-interface.md`, `compute_fork_digest`                           |

Each assertion has one normative owner:

| Assertion ID                 | Normative source and derived constraint                                                                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `request_encoding_bound`     | Gloas request content and `MAX_REQUEST_PAYLOADS`; decode as the official bounded `ExecutionPayloadEnvelopeRoots` type.                                  |
| `successful_chunk_type`      | Gloas response content; decode each code-`0` payload as the official `SignedExecutionPayloadEnvelope` type.                                             |
| `requested_root_membership`  | Gloas request-key sentence; compare the decoded envelope's `message.beacon_block_root` with the decoded request roots.                                  |
| `response_count_bound`       | Gloas response-list constraint; compare observed successful chunks with the decoded request length.                                                     |
| `context_fork_digest`        | Gloas context-epoch rule plus the Phase 0 helper; derive the digest from the referenced block slot and recorded genesis validators root.                |
| `known_available_response`   | Gloas supported-range and known-availability MUST; apply only when decoded available-envelope, block-slot, and range premises establish its antecedent. |
| `response_code_validity`     | Phase 0 result-code ranges; reject reserved codes while preserving the explicit code-`128` ambiguity.                                                   |
| `response_context_length`    | Altair context rules; success has a four-byte `ForkDigest` and standard errors have empty context.                                                      |
| `nonzero_result_finality`    | Phase 0 response termination; every non-zero result is final.                                                                                           |
| `standard_error_payload`     | Phase 0 standard errors; codes `1`, `2`, and `3` carry an `ErrorMessage`.                                                                               |
| `standard_error_eligibility` | Phase 0 and Gloas method rules; code `1` represents an invalid request and code `3` is allowed only for a root before the supported range.              |

## Test case format

Each case has the following layout:

```text
<case_id>/
  manifest.yaml
  config.yaml
  meta.yaml
  request.ssz_snappy
  fixture.yaml
  block_000.ssz_snappy
  available_000.ssz_snappy
  responses.yaml
  response_000.ssz_snappy
  expected.yaml
```

Numbered payload files are present only when referenced by the YAML documents.
Unknown fields and references to absent files are invalid.

Every `bytes`, `bytes4`, and `bytes32` YAML value is a `0x`-prefixed lowercase
hexadecimal string with exactly the declared byte length. Variable-length bytes
use an even number of hexadecimal digits; empty bytes are `0x`. The same rule
applies when a byte value is used as a mapping key.

### `manifest.yaml`

The standard per-case manifest identifies the vector independently of its path:

```yaml
preset: minimal
fork: gloas
runner: networking
handler: reqresp_execution_payload_envelopes_by_root
suite: reqresp
case: string
```

### `config.yaml`

The case includes the full selected runtime configuration with
`GLOAS_FORK_EPOCH` set to an epoch reachable by the generated block slots. For
the minimum suite it is set to `0`. The remaining values match the selected
configuration. This override is required because the default minimal config
keeps unscheduled forks at `FAR_FUTURE_EPOCH`.

### `meta.yaml`

```yaml
format_version: 1
```

The version identifies this specialized format. The standard manifest and
generator tooling provide case identity and source-tree provenance.

### `request.ssz_snappy`

The SSZ-snappy encoded `ExecutionPayloadEnvelopeRoots` request. This is the
standard compressed reference-test representation, not captured ReqResp wire
framing: it contains no length prefix or libp2p state. A request above
`MAX_REQUEST_PAYLOADS` may contain bytes that do not decode as the bounded
request type.

### `fixture.yaml`

```yaml
current_epoch: uint64
genesis_validators_root: bytes32
supported_epoch_range: [uint64, uint64]
referenced_blocks:
  - root: bytes32
    file: string
available_envelopes:
  - beacon_block_root: bytes32
    file: string
```

`available_envelopes` maps block roots to numbered
`SignedExecutionPayloadEnvelope` files. `referenced_blocks` maps roots to
numbered `SignedBeaconBlock` files. The runner decodes every block, recomputes
its hash-tree-root, and obtains its slot from that object. It also decodes every
available envelope and requires its `beacon_block_root` to match the referenced
block. File presence is the fixture's availability premise; there is no separate
canonicality assertion. The generator derives all roots, slots, genesis root,
and serialized objects with the selected PySpec.

The generator derives `supported_epoch_range` as:

```python
[
    max(
        spec.config.GLOAS_FORK_EPOCH,
        current_epoch - spec.compute_min_epochs_for_block_requests(),
    ),
    current_epoch,
]
```

The runner recomputes the range and rejects a mismatch.

### `responses.yaml`

```yaml
chunks:
  - response_code: uint8
    context: bytes  # Exactly bytes4 for success; empty for a standard error.
    payload: string
terminal: completed  # completed | interrupted
```

Each entry represents one fully observed chunk and preserves its response code
and exact context bytes. Code `0` has a four-byte `ForkDigest` context and a
`SignedExecutionPayloadEnvelope` payload. A standard error code has empty
context and an `ErrorMessage` payload for code `1`, `2`, or `3`; reserved codes
`4` through `127`, a wrong context length, and a non-final non-zero result
remain representable negative observations. They produce violated assertions
rather than making the vector structurally invalid. The relaxed BNF includes
code `128`, while prose says request-specific codes are above `128`; format v1
does not resolve that source conflict. Code `128` requires a maintainer
decision. Format v1 preserves it without classifying it as reserved or
request-specific; its `response_code_validity` assertion is `not_applicable`
with reason `response_code_128_ambiguous`. Codes `129` through `255` are the
unambiguous request-specific extension range, but this method defines no payload
schema for them. Their extension-dependent assertions are `not_applicable` with
reason `request_specific_error_unsupported`; the format never converts an opaque
context or payload into a protocol violation. Universal non-zero finality
remains independently evaluable for every code. Assertions already decided from
complete success chunks and the response-count assertion also remain evaluable;
only assertions that require interpreting undefined semantics are not
applicable. The payload references a numbered `response_NNN.ssz_snappy` file
encoded as its corresponding SSZ type; an unsupported extension payload remains
opaque.

For `terminal: interrupted`, `chunks` contains only chunks whose complete
framing and payload were observed before interruption. A partial chunk is wire
evidence outside this offline vector format and must not be promoted into a
complete chunk. This trace does not model peer identity, negotiation, deadlines,
sockets, client logs, or internal peer scoring and validation states.

### `expected.yaml`

```yaml
assertions:
  request_encoding_bound:
    applicability: applicable
    expected_result: satisfied  # satisfied | violated
    request_decodes: bool
  successful_chunk_type:
    applicability: applicable
    expected_result: satisfied
    type: SignedExecutionPayloadEnvelope
  requested_root_membership:
    applicability: applicable
    expected_result: satisfied
    allowed_beacon_block_roots: [bytes32]
  response_count_bound:
    applicability: applicable
    expected_result: satisfied
    maximum_success_chunks: uint64
  context_fork_digest:
    applicability: applicable
    expected_result: satisfied
    by_beacon_block_root:
      <bytes32>: bytes4
  known_available_response:
    applicability: applicable
    expected_result: satisfied
    minimum_matching_success_chunks: uint64
  response_code_validity:
    applicability: applicable
    expected_result: satisfied
  response_context_length:
    applicability: applicable
    expected_result: satisfied
  nonzero_result_finality:
    applicability: applicable
    expected_result: satisfied
  standard_error_payload:
    applicability: applicable
    expected_result: satisfied
  standard_error_eligibility:
    applicability: applicable
    expected_result: satisfied
```

Each assertion has `applicability: applicable` or
`applicability: not_applicable`. An applicable assertion records an
`expected_result` of `satisfied` or `violated`. A non-applicable assertion has
no `expected_result` and instead records a `reason`, for example:

```yaml
assertions:
  response_code_validity:
    applicability: not_applicable
    reason: response_code_128_ambiguous
```

`reason` is one of these codes:

| Reason code                          | Meaning                                                                            |
| ------------------------------------ | ---------------------------------------------------------------------------------- |
| `request_not_decodable`              | The request cannot be decoded as the bounded type.                                 |
| `stream_interrupted`                 | The response trace did not reach normal completion.                                |
| `successful_payload_not_decodable`   | A success payload cannot provide the value required by a dependent assertion.      |
| `request_specific_error_unsupported` | The trace uses an extension code whose payload schema this method does not define. |
| `response_code_128_ambiguous`        | The trace uses code `128`, whose classification conflicts in the normative text.   |
| `premise_not_satisfied`              | A normative fixture premise for the assertion is false.                            |

The generator derives expected constraints and reason codes from official types,
configuration, and helpers. Missing premise data is invalid and is never treated
as an applicable assertion with a default value.

## Conditions

The runner performs these steps:

01. Parse YAML without custom tags, aliases, or duplicate keys. Reject unknown
    fields, absent file references, or a payload that is absent from a fully
    observed chunk. Preserve all byte-valued result codes and context lengths so
    the runner can evaluate reserved codes, context-length errors, and non-final
    non-zero results as conformance observations. Preserve code `128` as an
    explicit source ambiguity. Preserve an unambiguous request-specific
    extension code, including its context and payload, as unsupported rather
    than assigning extension semantics.

02. Decode `request.ssz_snappy` as `ExecutionPayloadEnvelopeRoots` and evaluate
    the request bound.

03. Recompute `supported_epoch_range` from `current_epoch` and the selected
    official configuration.

04. Evaluate result-code validity, context length, and universal non-zero
    finality before method-specific assertions. Decode only standard error codes
    `1`, `2`, and `3` as `ErrorMessage`; require code `1` to accompany a request
    that fails official request decoding and code `3` only when at least one
    decoded requested root refers to a block before the supported range. Code
    `2` has no fixture-derived eligibility assertion because its server-internal
    cause is unobservable. Preserve a request-specific extension context and
    payload as opaque.

    For every successful response chunk, decode the payload as
    `SignedExecutionPayloadEnvelope` and obtain its `beacon_block_root`.

05. Decode every referenced `SignedBeaconBlock`, recompute its root, and obtain
    its slot. Decode every available envelope and verify its recorded root
    against the referenced block before using file presence as availability.

06. Assertions already decided from complete success chunks and the
    response-count assertion remain evaluable. Only assertions that require
    interpreting the extension's undefined semantics become `not_applicable`
    with `request_specific_error_unsupported`.

    If the request does not decode, as in `request_over_bound`, success-payload
    and method-specific response assertions are `not_applicable` with
    `request_not_decodable`. Trace-structure, standard-error-payload, and
    standard-error-eligibility assertions remain applicable. A standard error
    does not erase fully observed earlier success chunks or completion.
    Per-chunk and count assertions remain decidable. The known-available
    assertion is violated by a completed response with no matching success only
    when the decoded fixture objects make that MUST applicable; the response
    code alone never supplies a premise.

07. For every decoded successful envelope, require its block root to occur in
    the request.

08. If the observed number of successful chunks exceeds the number of requested
    roots, report the count assertion as violated immediately. Otherwise report
    it as satisfied only for a completed stream and as `not_applicable` with
    reason `stream_interrupted` for an interrupted stream.

09. For every decoded successful envelope, find the referenced block slot and
    derive its required context with
    `spec.compute_fork_digest(genesis_validators_root, spec.compute_epoch_at_slot(referenced_block.slot))`.

10. When every requested root has a referenced block slot in
    `supported_epoch_range` and at least one requested decoded envelope is
    available, require a completed response to contain at least one matching
    successful chunk. This rule applies equally to standard-error completion. If
    any requested root is earlier than the range, the Gloas code-`3` exception
    makes the assertion `not_applicable` with reason `premise_not_satisfied`.
    For an interrupted stream it is `not_applicable` with reason
    `stream_interrupted`.

11. When a malformed success payload prevents membership or context evaluation,
    report those dependent assertions as `not_applicable` with reason
    `successful_payload_not_decodable`; do not infer their result.

12. Compare every applicable assertion with its generated expectation.

## Input safety and resource bounds

The runner reads metadata files only after their byte length is at most 1 MiB.
It rejects YAML nesting deeper than 16 levels, more than 1024 mapping/sequence
entries in one document, scalar values over 4096 bytes, duplicate keys, aliases,
custom tags, and any list whose length exceeds its declared bound.
`referenced_blocks` and `available_envelopes` each contain at most
`MAX_REQUEST_PAYLOADS` entries. `chunks` contains at most
`MAX_REQUEST_PAYLOADS + 1` entries so that one deliberately excessive success
chunk or a final error remains representable.

A payload reference must be a simple basename matching
`^(block|available|response)_[0-9]{3}\.ssz_snappy$`. It must resolve to a
regular, non-symlink file directly inside the case directory; absolute paths,
separators, traversal, and canonical paths outside that directory are invalid.
The runner checks the request and every typed payload's compressed byte length
before allocation against `max_compressed_len(min(type_max, MAX_PAYLOAD_SIZE))`,
where `type_max` is the official SSZ maximum serialized length of the decoded
type. It then bounds decompression by that exact type maximum and the global 10
MiB `MAX_PAYLOAD_SIZE`. The `ErrorMessage` uncompressed limit remains its
official 256-byte SSZ bound. An opaque extension payload is independently
limited to `max_compressed_len(MAX_PAYLOAD_SIZE)` compressed and 10 MiB
uncompressed, without assigning it an SSZ type. A reserved-code or code-`128`
payload uses the same opaque compressed and uncompressed caps.

The normative source map above is fixed by this format. Every path resolved from
a payload reference must be normalized, relative, root-confined, unique,
regular, and non-symlink.

A runner reports an applicable assertion as `satisfied` or `violated`, and a
non-applicable assertion as `not_applicable`. These are vector-evaluation
states, not client-internal `Accept`, `Ignore`, or `Reject` verdicts.

## Minimum cases

A generator invocation for `fork=gloas` and `preset=minimal` emits at least:

| Case ID                        | Kind       | Assertion IDs                                                                                                                                                    | Required property                                                                                                                                         |
| ------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `empty_request`                | positive   | `request_encoding_bound`, `response_count_bound`                                                                                                                 | An empty bounded request and completed empty response satisfy their bounds.                                                                               |
| `request_at_bound`             | positive   | `request_encoding_bound`                                                                                                                                         | Exactly `MAX_REQUEST_PAYLOADS` roots decode.                                                                                                              |
| `request_over_bound`           | negative   | `request_encoding_bound`, `response_code_validity`, `response_context_length`, `nonzero_result_finality`, `standard_error_payload`, `standard_error_eligibility` | One root above the bound does not decode; the trace contains a terminal `InvalidRequest` chunk with empty context and an `ErrorMessage`.                  |
| `one_available_requested_root` | positive   | all assertions                                                                                                                                                   | One matching success chunk satisfies every applicable method and trace assertion.                                                                         |
| `mixed_available_unavailable`  | positive   | `successful_chunk_type`, `requested_root_membership`, `response_count_bound`, `context_fork_digest`, `known_available_response`                                  | A permitted available subset is returned.                                                                                                                 |
| `unrequested_envelope`         | negative   | `requested_root_membership`                                                                                                                                      | A successful envelope names an unrequested root.                                                                                                          |
| `too_many_success_chunks`      | negative   | `response_count_bound`                                                                                                                                           | A completed trace exceeds the request count.                                                                                                              |
| `wrong_context`                | negative   | `context_fork_digest`                                                                                                                                            | A valid envelope has mutated context bytes.                                                                                                               |
| `malformed_success_payload`    | negative   | `successful_chunk_type`                                                                                                                                          | A success chunk does not decode as the required type.                                                                                                     |
| `available_but_empty`          | negative   | `known_available_response`                                                                                                                                       | Applicable availability premises have a completed empty trace.                                                                                            |
| `interrupted_stream`           | incomplete | `successful_chunk_type`, `requested_root_membership`, `context_fork_digest`; conditional `response_count_bound`, `known_available_response`                      | Per-chunk assertions remain evaluable; count is violated if already over its maximum, otherwise count and minimum-response assertions are not applicable. |
| `reserved_response_code`       | negative   | `response_code_validity`                                                                                                                                         | A final code in `[4, 127]` violates the reserved-code assertion.                                                                                          |
| `wrong_standard_error_context` | negative   | `response_context_length`                                                                                                                                        | A standard error with non-empty context violates the standard-error context assertion.                                                                    |
| `wrong_success_context_length` | negative   | `response_context_length`                                                                                                                                        | A success result whose context is not exactly four bytes violates the success-context assertion.                                                          |
| `nonfinal_error`               | negative   | `nonzero_result_finality`                                                                                                                                        | Any non-zero result followed by another chunk violates universal finality.                                                                                |
| `malformed_error_payload`      | negative   | `standard_error_payload`                                                                                                                                         | A code-`1`, code-`2`, or code-`3` payload does not decode as `ErrorMessage`.                                                                              |
| `unexpected_invalid_request`   | negative   | `standard_error_eligibility`                                                                                                                                     | Code `1` violates eligibility when the request decodes successfully.                                                                                      |
| `server_error`                 | positive   | `response_code_validity`, `response_context_length`, `nonzero_result_finality`, `standard_error_payload`                                                         | A final code-`2` trace preserves prior decidable facts without claiming its internal cause.                                                               |
| `earlier_root_unavailable`     | positive   | `standard_error_eligibility`                                                                                                                                     | Code `3` is accepted when a decoded requested block is earlier than the supported range.                                                                  |
| `unexpected_resource_error`    | negative   | `standard_error_eligibility`                                                                                                                                     | Code `3` is violated when every decoded requested block is inside the supported range.                                                                    |
| `request_specific_error`       | incomplete | `response_code_validity`, `nonzero_result_finality`; dependent assertions                                                                                        | A final code above `128` preserves prior decidable facts while extension-dependent assertions are not applicable.                                         |
| `response_code_128`            | incomplete | `nonzero_result_finality`; ambiguous assertions                                                                                                                  | A final code `128` preserves prior decidable facts while `response_code_validity` is not applicable with `response_code_128_ambiguous`.                   |

Negative mutations and expected assertion results are produced by official code.
Every generated case records its expected per-assertion runner result so
consumers can verify integration without deriving protocol semantics.

## Determinism

The generator writes only the declared files with stable case IDs and ordering.
Two isolated runs from the same source tree and generator configuration must
produce byte-identical case trees.

Timestamps, absolute paths, random seeds, host versions, and unordered-map
iteration must not enter generated files. Generator tests delete one referenced
payload, add one unknown field, and alter one byte to prove that structural and
digest failures are detected.

## Review questions

The specification permits a responder to omit unavailable envelopes and limit
its response. Before a generator or runner constrains either behavior,
maintainers must decide whether the order of successful chunks or the handling
of duplicate requested roots has an additional normative requirement. Until
then, neither property affects an assertion.

The specification text also requires a maintainer decision on whether response
code `128` belongs to the request-specific extension range, because its relaxed
BNF and prose disagree. That decision cannot change evidence already decidable
from complete successful chunks or independently established fixture premises.

Maintainers must also decide the generator and runner module names, the command
that publishes the generated target, and whether this response-trace format
belongs under `tests/formats/networking` or another upstream-owned hierarchy.
Those ownership choices do not change the fields or normative source mapping
proposed here.

## Implementation follow-up

This format can be implemented after maintainers confirm the open decisions
above and review the source map. The generator and runner follow-up is complete
when all of the following hold:

1. One command generates all minimum cases from the selected PySpec and runner
   configuration, then the runner evaluates every case.
2. Two isolated invocations produce byte-identical case trees.
3. Structural tests reject unknown fields, missing references, a changed payload
   byte, unsafe paths or symlinks, duplicate keys or YAML expansion features,
   and resource-limit overruns. Conformance tests preserve reserved response
   codes, wrong context lengths, and non-final non-zero result chunks (including
   request-specific extensions) and evaluate their assertions as violated.
4. License review confirms that generated fixtures and implementation can be
   distributed under this repository's `CC0-1.0` terms.
