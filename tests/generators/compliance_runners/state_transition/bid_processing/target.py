"""Declarative coverage for Gloas ``process_execution_payload_bid``."""

from itertools import combinations

from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    all_of,
    aspect,
    attribute,
    bind,
    Boolean,
    choose,
    cmp3,
    constant,
    coverage_spec,
    coverage_value,
    dimension,
    exhaustive,
    Finite,
    fix,
    implies,
    Integer,
    union,
)

from .observation import observe_attributes

builder_type_input = attribute(
    "observed_builder_type", Finite(("SELF", "EXTERNAL", "NON_EXISTING"))
)
signature_input = attribute("observed_bid_signature", Finite(("INF", "VALID", "INVALID")))
value_input = attribute("observed_bid_value", Integer(min=0))
balance_input = attribute("observed_builder_balance", Integer(min=0))
pending_input = attribute("observed_pending_balance", Integer(min=0))
epoch_input = attribute("observed_current_epoch", Integer(min=0))
deposit_input = attribute("observed_deposit_epoch", Integer(min=0))
withdrawable_input = attribute("observed_withdrawable_epoch", Integer(min=0))
finalized_input = attribute("observed_finalized_epoch", Integer(min=0))
version_input = attribute("observed_payload_builder_version", Boolean())
payment_input = attribute("observed_has_pending_payments", Boolean())
withdrawal_input = attribute("observed_has_pending_withdrawals", Boolean())
kzg_input = attribute("observed_kzg_commitment_count", Integer(min=0))
max_blobs_input = attribute("observed_max_blobs", Integer(min=1))
slot_input = attribute("observed_state_slot", Integer(min=0))
bid_slot_input = attribute("observed_bid_slot", Integer(min=0))
parent_hash_input = attribute("observed_parent_block_hash_match", Boolean())
parent_root_input = attribute("observed_parent_block_root_match", Boolean())
randao_input = attribute("observed_prev_randao_match", Boolean())
minimum = constant("minimum_deposit", Integer(min=1))
far_future = constant("far_future_epoch", Integer(min=1))
genesis_slot = constant("genesis_slot", Integer(min=0))

builder_type = dimension("builder_type", builder_type_input)
external = builder_type == "EXTERNAL"
is_self = builder_type == "SELF"
value = dimension("cmp_bid_value_zero", cmp3(value_input, 0, op="=="))
signature = dimension("bid_signature", signature_input)
funds = dimension(
    "cmp_builder_balance_to_bid_value_plus_min_balance",
    cmp3(
        balance_input,
        choose(
            builder_type_input == "EXTERNAL", value_input + minimum + pending_input, no=value_input
        ),
        op=">=",
    ),
)
kzg = dimension("cmp_len_kzg_commitments_max_blobs", cmp3(kzg_input, max_blobs_input, op="<="))
slot = dimension("cmp_state_slot_bid_slot", cmp3(slot_input, bid_slot_input, op="=="))
parent_hash = dimension("parent_block_hash_match", parent_hash_input)
parent_root = dimension("parent_block_root_match", parent_root_input)
randao = dimension("prev_randao_match", randao_input)
version = dimension("payload_builder_version", version_input, when=external)
deposit = dimension(
    "cmp_state_epoch_deposit_epoch", cmp3(epoch_input, deposit_input, op=">="), when=external
)
withdrawable = dimension(
    "cmp_state_epoch_withdrawal_epoch", cmp3(epoch_input, withdrawable_input, op="<"), when=external
)
finalized = dimension(
    "cmp_finalized_epoch_deposit_epoch", cmp3(finalized_input, deposit_input, op=">"), when=external
)
withdrawable_set = dimension(
    "withdrawable_epoch_set", withdrawable_input != far_future, when=external
)
zero = dimension("cmp_balance_zero", cmp3(balance_input, 0, op="=="), when=external)
balance = dimension("cmp_balance_min_deposit", cmp3(balance_input, minimum, op=">="), when=external)
payment = dimension("has_pending_payments", payment_input, when=external)
withdrawal = dimension("has_pending_withdrawals", withdrawal_input, when=external)
positive = dimension("amount_positive", value_input > 0)
past_genesis = dimension("state_slot_past_genesis", slot_input > genesis_slot)


def terminal_outcome(
    kind,
    amount_zero,
    sig,
    active,
    payload_version,
    funded,
    commitments,
    matching_slot,
    past,
    ph,
    pr,
    rr,
):
    common = choose(
        (~commitments, "REJECT_KZG_OVER_LIMIT"),
        (~matching_slot, "REJECT_WRONG_SLOT"),
        (~past, "REJECT_NOT_PAST_GENESIS"),
        (~ph, "REJECT_PARENT_HASH"),
        (~pr, "REJECT_PARENT_ROOT"),
        (~rr, "REJECT_PREV_RANDAO"),
        "ACCEPT",
    )
    return choose(
        (
            kind == "SELF",
            choose(
                (~amount_zero, "REJECT_SELF_BUILD_NONZERO_AMOUNT"),
                (sig != "INF", "REJECT_SELF_BUILD_BAD_SIGNATURE"),
                common,
            ),
        ),
        (kind == "NON_EXISTING", "REJECT_BUILDER_NOT_FOUND"),
        choose(
            (~active, "REJECT_BUILDER_INACTIVE"),
            (~payload_version, "REJECT_WRONG_VERSION"),
            (~funded, "REJECT_UNDERFUNDED"),
            (sig != "VALID", "REJECT_BAD_SIGNATURE"),
            common,
        ),
    )


def fault_total(
    kind,
    amount_zero,
    sig,
    active,
    payload_version,
    funded,
    commitments,
    matching_slot,
    past,
    ph,
    pr,
    rr,
):
    common = sum(choose(gate, 0, no=1) for gate in (commitments, matching_slot, past, ph, pr, rr))
    return common + choose(
        (kind == "SELF", choose(amount_zero, 0, no=1) + choose(sig == "INF", 0, no=1)),
        (kind == "NON_EXISTING", 1),
        sum(choose(gate, 0, no=1) for gate in (active, payload_version, funded, sig == "VALID")),
    )


raw_gates = (
    builder_type_input,
    value_input == 0,
    signature_input,
    all_of(finalized_input > deposit_input, withdrawable_input == far_future),
    version_input,
    balance_input >= value_input + minimum + pending_input,
    kzg_input <= max_blobs_input,
    slot_input == bid_slot_input,
    slot_input > genesis_slot,
    parent_hash_input,
    parent_root_input,
    randao_input,
)
outcome = dimension("outcome", terminal_outcome(*raw_gates))
fault_count = dimension("fault_count", fault_total(*raw_gates), domain=Finite(tuple(range(11))))
active = all_of(finalized, ~withdrawable_set)
pending = payment | withdrawal
abstract_gates = (
    builder_type,
    value,
    signature,
    active,
    version,
    funds,
    kzg,
    slot,
    past_genesis,
    parent_hash,
    parent_root,
    randao,
)

INPUT_ASPECTS = (
    aspect("builder_type", builder_type),
    aspect("bid_amount", value),
    aspect("signed_message", signature),
    aspect("builder_funds", funds),
    aspect("blob_kzg_capacity", kzg),
    aspect("slot_epoch", slot),
    aspect("block_context", parent_hash, parent_root, randao),
    aspect("builder_version", version),
    aspect("builder_lifecycle", deposit, withdrawable, finalized, withdrawable_set),
    aspect("builder_balance", zero, balance),
    aspect("builder_pending_balance", payment, withdrawal),
)
OUTCOME = aspect("outcome", outcome)
LOCAL = aspect("handler_context", positive, past_genesis, fault_count)
ASPECTS = (*INPUT_ASPECTS, OUTCOME, LOCAL)
FACTORS = tuple(f for a in ASPECTS for f in a.declarations)
NORMAL_SCOPE = fix(fault_count=0)
SINGLE_FAULT = fix(fault_count=1)
NORMAL = union(
    *(a.exhaustive() * b.exhaustive() * NORMAL_SCOPE for a, b in combinations(INPUT_ASPECTS, 2))
)
EXCEPTIONAL = OUTCOME.exhaustive() * SINGLE_FAULT

# Preserve the legacy fixture constraints, including its INVALID-only signature
# fault bound. An external INF signature may therefore coexist with one other
# failing gate, producing two independently counted faults.
legacy_external_faults = sum(
    choose(gate, 0, no=1)
    for gate in (
        active,
        version,
        funds,
        signature != "INVALID",
        kzg,
        slot,
        parent_hash,
        parent_root,
        randao,
    )
)
legacy_self_faults = sum(
    choose(gate, 0, no=1)
    for gate in (funds, signature != "INVALID", kzg, slot, parent_hash, parent_root, randao)
)
COVERAGE = coverage_spec(
    "bid_processing",
    focus="process_execution_payload_bid: self/external builders, lifecycle, funds, signatures, and block context",
    record="one signed execution payload bid",
    aspects=ASPECTS,
    constraints=(
        builder_type != "NON_EXISTING",
        past_genesis,
        coverage_value(value) != "LT",
        implies(external, coverage_value(deposit) != "LT"),
        implies(external, coverage_value(zero) != "LT"),
        implies(external, zero == ~balance),
        implies(external & active, balance),
        implies(external & pending, active & (coverage_value(balance) == "GT")),
        implies(external & ~withdrawable_set, withdrawable),
        implies(is_self, signature != "VALID"),
        implies(is_self, (coverage_value(value) == "EQ") == (coverage_value(funds) == "EQ")),
        implies(is_self, (coverage_value(value) == "GT") == (coverage_value(funds) == "LT")),
        implies(external & value, funds),
        implies(
            external & value & (coverage_value(funds) == "EQ"),
            pending | (coverage_value(balance) == "EQ"),
        ),
        implies(
            external & value & (coverage_value(funds) == "GT"), coverage_value(balance) == "GT"
        ),
        implies(external & ~value & funds, coverage_value(balance) == "GT"),
        implies(external, legacy_external_faults <= 1),
        implies(is_self, legacy_self_faults <= 1),
        positive == ~value,
        outcome == terminal_outcome(*abstract_gates),
        fault_count == fault_total(*abstract_gates),
    ),
    profiles={
        "smoke": OUTCOME.exhaustive() * union(NORMAL_SCOPE, SINGLE_FAULT),
        "normal": NORMAL,
        "exceptional": EXCEPTIONAL,
        "standard": NORMAL | EXCEPTIONAL,
        "max": exhaustive(FACTORS),
    },
)
TARGET = bind(
    COVERAGE,
    observe_attributes=observe_attributes,
    constants={
        "minimum_deposit": lambda spec: int(spec.MIN_DEPOSIT_AMOUNT),
        "far_future_epoch": lambda spec: int(spec.FAR_FUTURE_EPOCH),
        "genesis_slot": lambda spec: int(spec.GENESIS_SLOT),
    },
)
