"""Coverage target for the assertion slice of Gloas ``process_operations``.

This target measures only the deposit prohibition and operation-count limits.
The sibling ``operations_dispatch`` provider supplies block-level integration
vectors for the operation-processing loops.
"""

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    aspect,
    assertion,
    assertion_set,
    attribute,
    bind,
    Boolean,
    constant,
    coverage_spec,
    dimension,
    each,
    Integer,
    predicate,
    union,
)

from .observation import observe_attributes

deposits = attribute("deposits", Integer(min=0))
proposer_slashings = attribute("proposer_slashings", Integer(min=0))
attester_slashings = attribute("attester_slashings", Integer(min=0))
attestations = attribute("attestations", Integer(min=0))
voluntary_exits = attribute("voluntary_exits", Integer(min=0))
bls_to_execution_changes = attribute("bls_to_execution_changes", Integer(min=0))
payload_attestations = attribute("payload_attestations", Integer(min=0))
post_present = attribute("post_present", Boolean())

proposer_slashings_limit = constant("proposer_slashings_limit", Integer(min=0))
attester_slashings_limit = constant("attester_slashings_limit", Integer(min=0))
attestations_limit = constant("attestations_limit", Integer(min=0))
voluntary_exits_limit = constant("voluntary_exits_limit", Integer(min=0))
bls_to_execution_changes_limit = constant("bls_to_execution_changes_limit", Integer(min=0))
payload_attestations_limit = constant("payload_attestations_limit", Integer(min=0))

LIMITS = aspect(
    "limits",
    assertion("deposits_empty", deposits == 0),
    assertion(
        "proposer_slashings_within_limit",
        predicate(proposer_slashings, proposer_slashings_limit, op="<="),
    ),
    assertion(
        "attester_slashings_within_limit",
        predicate(attester_slashings, attester_slashings_limit, op="<="),
    ),
    assertion("attestations_within_limit", predicate(attestations, attestations_limit, op="<=")),
    assertion(
        "voluntary_exits_within_limit", predicate(voluntary_exits, voluntary_exits_limit, op="<=")
    ),
    assertion(
        "bls_to_execution_changes_within_limit",
        predicate(bls_to_execution_changes, bls_to_execution_changes_limit, op="<="),
    ),
    assertion(
        "payload_attestations_within_limit",
        predicate(payload_attestations, payload_attestations_limit, op="<="),
    ),
)

OUTCOME = aspect("outcome", dimension("accepted", post_present))
ASPECTS = (LIMITS, OUTCOME)
# Later operation processing can reject a block even if these limits hold.
ASSERTIONS = assertion_set(LIMITS, observed=OUTCOME.ref("accepted"), complete=False)


PROFILES = {
    "smoke": each([*LIMITS.declarations, *OUTCOME.declarations]),
    "normal": ASSERTIONS.normal(LIMITS.exhaustive()),
    "exceptional": ASSERTIONS.exceptional(LIMITS.nwise(2), faults=1),
    "max": union(ASSERTIONS.normal(LIMITS.exhaustive()), ASSERTIONS.exceptional(LIMITS.nwise(2))),
    "standard": union(
        each([*LIMITS.declarations, *OUTCOME.declarations]),
        LIMITS.each() * OUTCOME.each(),
    ),
}

COVERAGE = coverage_spec(
    "process_operations",
    focus="deposit prohibition and operation-count assertions in process_operations; operation-processing loops excluded",
    record="one vector",
    aspects=ASPECTS,
    profiles=PROFILES,
    assertions=ASSERTIONS,
)

TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "proposer_slashings_limit": lambda spec: int(spec.MAX_PROPOSER_SLASHINGS),
        "attester_slashings_limit": lambda spec: int(spec.MAX_ATTESTER_SLASHINGS_ELECTRA),
        "attestations_limit": lambda spec: int(spec.MAX_ATTESTATIONS_ELECTRA),
        "voluntary_exits_limit": lambda spec: int(spec.MAX_VOLUNTARY_EXITS),
        "bls_to_execution_changes_limit": lambda spec: int(spec.MAX_BLS_TO_EXECUTION_CHANGES),
        "payload_attestations_limit": lambda spec: int(spec.MAX_PAYLOAD_ATTESTATIONS),
    },
)
