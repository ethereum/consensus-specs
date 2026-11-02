"""Coverage declaration for aggregate Gloas ``process_withdrawals``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    attribute,
    bind,
    Boolean,
    cmp3,
    constant,
    coverage_spec,
    coverage_value,
    dimension,
    exhaustive,
    implies,
    Integer,
    union,
)

from .observation import observe_attributes

parent_input = attribute("observed_parent_hash_matches", Boolean())
builder_pending_input = attribute("observed_builder_pending_count", Integer(min=0))
processed_builder_input = attribute("observed_processed_builder_count", Integer(min=0))
validator_pending_input = attribute("observed_validator_pending_count", Integer(min=0))
eligible_partial_input = attribute("observed_eligible_validator_pending", Boolean())
processed_partial_input = attribute("observed_processed_partial_count", Integer(min=0))
builders_input = attribute("observed_builder_count", Integer(min=0))
eligible_builders_input = attribute("observed_eligible_builder_count", Integer(min=0))
swept_input = attribute("observed_swept_builder_count", Integer(min=0))
next_index_input = attribute("observed_next_builder_index", Integer(min=0))
eligible_validator_input = attribute("observed_eligible_validator_sweep", Boolean())
partial_sweep_input = attribute("observed_partial_validator_sweep", Boolean())
total_input = attribute("observed_total_withdrawals", Integer(min=0))
withdrawal_limit = constant("withdrawals_limit", Integer(min=1))
payload_limit = constant("payload_limit", Integer(min=2))
max_partials = constant("max_partials", Integer(min=1))
max_builders = constant("max_builders", Integer(min=2))
prior_input = processed_builder_input + processed_partial_input

parent = dimension("state_latest_block_hash_match", parent_input)
builder_pending = dimension("builder_pending_withdrawals_exist", builder_pending_input > 0)
builder_hit = dimension(
    "builder_pending_withdrawals_hit_limit", processed_builder_input == withdrawal_limit
)
validator_pending = dimension("validator_pending_withdrawals_exist", validator_pending_input > 0)
eligible_partial = dimension("eligible_validator_pending_withdrawals_exist", eligible_partial_input)
validator_hit = dimension(
    "validator_pending_withdrawals_hit_limit",
    (processed_builder_input < withdrawal_limit)
    & ((prior_input == withdrawal_limit) | (processed_partial_input == max_partials)),
)
builders_limit = dimension(
    "cmp_builder_count_withdrawals_limit", cmp3(builders_input, withdrawal_limit)
)
builders_max = dimension("cmp_builder_count_max_per_sweep", cmp3(builders_input, max_builders))
eligible_builders = dimension("cmp_eligible_builder_count_zero", cmp3(eligible_builders_input, 0))
swept_zero = dimension("cmp_swept_count_zero", cmp3(swept_input, 0))
swept_max = dimension("cmp_swept_count_max_per_sweep", cmp3(swept_input, max_builders))
next_zero = dimension("cmp_next_index_zero", cmp3(next_index_input, 0))
next_last = dimension(
    "cmp_next_index_last_builder_index", cmp3(next_index_input, builders_input - 1)
)
sweep_hit = dimension(
    "swept_builders_hit_withdrawals_limit",
    (prior_input < withdrawal_limit) & (prior_input + swept_input == withdrawal_limit),
)
validators_eligible = dimension("validators_eligible_for_sweep_exist", eligible_validator_input)
partial_sweep = dimension("partial_validator_sweep_withdrawal", partial_sweep_input)
validators_hit = dimension("swept_validators_hit_limit", total_input == payload_limit)

PAYLOAD = aspect("payload", parent)
BUILDER_PENDING = aspect("builder_pending", builder_pending, builder_hit)
VALIDATOR_PENDING = aspect("validator_pending", validator_pending, eligible_partial, validator_hit)
BUILDER_SWEEP = aspect(
    "builder_sweep",
    builders_limit,
    builders_max,
    eligible_builders,
    swept_zero,
    swept_max,
    next_zero,
    next_last,
    sweep_hit,
)
VALIDATOR_SWEEP = aspect("validator_sweep", validators_eligible, partial_sweep, validators_hit)
ASPECTS = (PAYLOAD, BUILDER_PENDING, VALIDATOR_PENDING, BUILDER_SWEEP, VALIDATOR_SWEEP)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)
SMOKE = union(*(a.exhaustive() for a in ASPECTS))
PAIRWISE = union(*(a.exhaustive() * b.exhaustive() for a, b in combinations(ASPECTS, 2)))
COVERAGE = coverage_spec(
    "withdrawal_processing",
    focus="process_withdrawals: pending sources, builder sweep boundaries, validator sweep, and empty-parent no-op",
    record="one withdrawals-processing step",
    aspects=ASPECTS,
    constraints=(
        coverage_value(builders_limit) == "GT",
        coverage_value(eligible_builders) != "LT",
        coverage_value(swept_zero) != "LT",
        coverage_value(swept_max) == "LT",
        coverage_value(next_zero) != "LT",
        coverage_value(next_last) != "GT",
        implies(
            coverage_value(eligible_builders) == "EQ",
            (coverage_value(swept_zero) == "EQ") & ~sweep_hit,
        ),
        implies(coverage_value(swept_zero) == "EQ", ~sweep_hit),
        implies(
            coverage_value(builders_max) != "GT",
            (coverage_value(swept_zero) == "GT") == (coverage_value(eligible_builders) == "GT"),
        ),
        implies(coverage_value(next_last) == "EQ", coverage_value(next_zero) == "GT"),
        implies(builder_hit, builder_pending),
        implies(eligible_partial, validator_pending),
        implies(validator_hit, eligible_partial),
        # Preserve the legacy minimal-preset fixture relationships. Concrete
        # queue sizes scale to each preset; these are not general protocol laws.
        implies(
            builder_pending & eligible_partial & (coverage_value(swept_zero) == "GT"), sweep_hit
        ),
        implies(~builder_pending & validator_hit & (coverage_value(swept_zero) == "GT"), sweep_hit),
        implies(validators_hit, validators_eligible),
        implies(
            partial_sweep,
            all_of(
                parent,
                validators_eligible,
                ~builder_hit,
                ~validator_hit,
                coverage_value(swept_zero) == "EQ",
            ),
        ),
        implies(
            builder_hit | (validator_hit & builder_pending), coverage_value(swept_zero) == "EQ"
        ),
        implies(builder_hit, ~validator_hit),
        implies(
            ~parent,
            all_of(
                builder_pending,
                eligible_partial,
                coverage_value(swept_zero) == "GT",
                validators_hit,
            ),
        ),
    ),
    # The legacy aggregate has no rejecting gate. Its profile names describe
    # grouped interaction strength, including both processing and no-op states.
    profiles={
        "smoke": SMOKE,
        "normal": PAIRWISE,
        "exceptional": SMOKE,
        "standard": PAIRWISE,
        "max": exhaustive(FACTORS),
    },
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "withdrawals_limit": lambda spec: int(spec.MAX_WITHDRAWALS_PER_PAYLOAD) - 1,
        "payload_limit": lambda spec: int(spec.MAX_WITHDRAWALS_PER_PAYLOAD),
        "max_partials": lambda spec: int(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP),
        "max_builders": lambda spec: int(spec.MAX_BUILDERS_PER_WITHDRAWALS_SWEEP),
    },
)
