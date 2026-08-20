from dataclasses import dataclass
from ..base import (
    Bool,
    BuilderType,
    Cmp,
    constraint,
    no_more_than_several_of,
    OpBool,
    OpCmp,
    Record,
    SignatureType,
)
from ..builder.builder import (
    Builder,
    builder_constraints,
    has_pending_withdrawals,
    is_active_builder,
    is_external_builder,
)


@dataclass
class ExecutionPayloadBidProcessing(Record):
    builder_type: BuilderType
    builder: Builder
    cmp_bid_value_zero: Cmp
    bid_signature: SignatureType
    cmp_builder_balance_to_bid_value_plus_min_balance: Cmp
    cmp_len_kzg_commitments_max_blobs: Cmp
    cmp_state_slot_bid_slot: Cmp
    parent_block_hash_match: Bool
    parent_block_root_match: Bool
    prev_randao_match: Bool


@constraint
def bid_processing_constraints(p: ExecutionPayloadBidProcessing) -> None:
    builder_constraints(p.builder)
    assert (p.builder_type == BuilderType.EXTERNAL) == is_external_builder(p.builder)
    assert p.cmp_bid_value_zero in {Cmp.GT, Cmp.EQ}

    if p.builder_type == BuilderType.EXTERNAL:
        if p.cmp_bid_value_zero == Cmp.EQ:
            assert p.cmp_builder_balance_to_bid_value_plus_min_balance in {Cmp.EQ, Cmp.GT}
            if p.cmp_builder_balance_to_bid_value_plus_min_balance == Cmp.EQ:
                assert has_pending_withdrawals(p.builder) or p.builder.cmp_balance_min_deposit == OpCmp.EQ
            if p.cmp_builder_balance_to_bid_value_plus_min_balance == Cmp.GT:
                assert p.builder.cmp_balance_min_deposit == OpCmp.GT

        if p.cmp_bid_value_zero == Cmp.GT:
            if p.cmp_builder_balance_to_bid_value_plus_min_balance in {Cmp.EQ, Cmp.GT}:
                assert p.builder.cmp_balance_min_deposit == OpCmp.GT

        assert no_more_than_several_of([
            not is_active_builder(p.builder),
            p.builder.payload_builder_version == OpBool.F,
            p.cmp_builder_balance_to_bid_value_plus_min_balance == Cmp.LT,
            p.bid_signature == SignatureType.INVALID,
            p.cmp_len_kzg_commitments_max_blobs == Cmp.GT,
            p.cmp_state_slot_bid_slot in {Cmp.GT, Cmp.LT},
            p.parent_block_hash_match == Bool.F,
            p.parent_block_root_match == Bool.F,
            p.prev_randao_match == Bool.F,
        ], 1)

    if p.builder_type == BuilderType.SELF:
        assert p.bid_signature in {SignatureType.INF, SignatureType.INVALID}
        assert p.cmp_builder_balance_to_bid_value_plus_min_balance in {Cmp.EQ, Cmp.LT}
        assert (p.cmp_bid_value_zero == Cmp.EQ) == (p.cmp_builder_balance_to_bid_value_plus_min_balance == Cmp.EQ)
        assert (p.cmp_bid_value_zero == Cmp.GT) == (p.cmp_builder_balance_to_bid_value_plus_min_balance == Cmp.LT)
        assert no_more_than_several_of([
            p.cmp_builder_balance_to_bid_value_plus_min_balance == Cmp.LT,
            p.bid_signature == SignatureType.INVALID,
            p.cmp_len_kzg_commitments_max_blobs == Cmp.GT,
            p.cmp_state_slot_bid_slot in {Cmp.GT, Cmp.LT},
            p.parent_block_hash_match == Bool.F,
            p.parent_block_root_match == Bool.F,
            p.prev_randao_match == Bool.F,
        ], 1)
