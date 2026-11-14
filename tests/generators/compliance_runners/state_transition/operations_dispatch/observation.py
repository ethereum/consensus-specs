"""Observe dispatch scenarios from block contents and participation effects."""

FIELDS = (
    "proposer_slashings",
    "attester_slashings",
    "attestations",
    "voluntary_exits",
    "bls_to_execution_changes",
    "payload_attestations",
)


def observe_attributes(ctx):
    spec, pre, block = ctx.spec, ctx.pre, ctx.operation.message
    body = block.body
    result = {f"observed_{field}_count": len(getattr(body, field)) for field in FIELDS}
    result.update(
        observed_post_present=ctx.post is not None,
        observed_shared_slash_exit=bool(
            body.proposer_slashings
            and body.voluntary_exits
            and body.proposer_slashings[0].signed_header_1.message.proposer_index
            == body.voluntary_exits[0].message.validator_index
        ),
        observed_payload_root_matches=bool(
            body.payload_attestations
            and body.payload_attestations[0].data.beacon_block_root == block.parent_root
        ),
        observed_parent_slot_differs=False,
        observed_parent_slot_payload_available=False,
        observed_attestation_slot_payload_available=False,
        observed_attestation_index=0,
        observed_head_flag_set=False,
    )
    if body.attestations:
        attestation = body.attestations[0]
        parent_slot = int(pre.latest_block_header.slot)
        attestation_slot = int(attestation.data.slot)
        result.update(
            observed_parent_slot_differs=parent_slot != attestation_slot,
            observed_parent_slot_payload_available=bool(
                pre.execution_payload_availability[
                    parent_slot % int(spec.SLOTS_PER_HISTORICAL_ROOT)
                ]
            ),
            observed_attestation_slot_payload_available=bool(
                pre.execution_payload_availability[
                    attestation_slot % int(spec.SLOTS_PER_HISTORICAL_ROOT)
                ]
            ),
            observed_attestation_index=int(attestation.data.index),
        )
        if ctx.post is not None:
            indices = spec.get_attesting_indices(ctx.post, attestation)
            result["observed_head_flag_set"] = bool(indices) and all(
                spec.has_flag(
                    ctx.post.current_epoch_participation[index], spec.TIMELY_HEAD_FLAG_INDEX
                )
                for index in indices
            )
    return result
