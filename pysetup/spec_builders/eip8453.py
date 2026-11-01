from pysetup.constants import EIP8453

from .base import BaseSpecBuilder


class EIP8453SpecBuilder(BaseSpecBuilder):
    fork: str = EIP8453

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.heze import {preset_name} as heze
"""

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> dict[str, str]:
        return {
            "FINALIZED_ROOT_GINDEX_EIP8453": "GeneralizedIndex(5943)",
        }

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "calculate_committee_fraction",
            "compute_adversarial_weight",
            "compute_empty_slot_support_discount",
            "compute_honest_ffg_support_for_current_target",
            "compute_on_chain_aggregate",
            "compute_pulled_up_tip",
            "compute_proposer_score",
            "compute_safety_threshold",
            "filter_node_tree",
            "find_latest_confirmed_descendant",
            "get_adversarial_weight",
            "get_aggregate_and_proof",
            "get_aggregate_and_proof_signature",
            "get_attestation_participation_flag_indices",
            "get_attestation_score",
            "get_beacon_committee",
            "get_builder_payment_quorum_threshold",
            "get_checkpoint_block",
            "get_checkpoint_for_block",
            "get_committee_assignment",
            "get_committee_count_per_slot",
            "get_current_balance_source",
            "get_current_target",
            "get_current_target_score",
            "get_equivocation_score",
            "get_fast_confirmation_store",
            "get_filtered_node_tree",
            "get_flag_index_deltas",
            "get_inactivity_penalty_deltas",
            "get_latest_confirmed",
            "get_node_support_between_slots",
            "get_previous_balance_source",
            "get_proposer_head",
            "get_proposer_score",
            "get_pulled_up_head_state",
            "get_restart_resilient_confirmed_root",
            "get_slot_committee",
            "get_support_discount",
            "get_supported_node",
            "get_voting_source",
            "get_weight",
            "is_aggregator",
            "is_attestation_same_slot",
            "is_bid_compatible_with_head",
            "is_confirmed_chain_safe",
            "is_head_late",
            "is_head_weak",
            "is_ffg_competitive",
            "is_finalization_ok",
            "is_one_confirmed",
            "is_parent_strong",
            "is_proposer_equivocation",
            "is_proposing_on_time",
            "is_valid_dependent_root",
            "on_attestation",
            "on_attester_slashing",
            "on_fast_confirmation",
            "on_inclusion_list",
            "on_tick_per_slot",
            "process_justification_and_finalization",
            "process_rewards_and_penalties",
            "record_block_timeliness",
            "should_apply_proposer_boost",
            "store_target_checkpoint_state",
            "update_checkpoints",
            "update_fast_confirmation_variables",
            "update_latest_messages",
            "update_proposer_boost_root",
            "update_unrealized_checkpoints",
            "upgrade_attestation_to_gloas",
            "upgrade_attester_slashing_to_gloas",
            "upgrade_indexed_attestation_to_gloas",
            "upgrade_to_heze",
            "validate_attester_slashing_gossip",
            "validate_attestation_gossip",
            "validate_beacon_aggregate_and_proof_gossip",
            "validate_beacon_attestation_gossip",
            "validate_beacon_block_gossip",
            "validate_bls_to_execution_change_gossip",
            "validate_execution_payload_bid_gossip",
            "validate_execution_payload_envelope_gossip",
            "validate_head_vote_gossip",
            "validate_inclusion_list_gossip",
            "validate_on_attestation",
            "validate_payload_attestation_message_gossip",
            "validate_proposer_preferences_gossip",
            "validate_proposer_slashing_gossip",
            "validate_sync_committee_contribution_and_proof_gossip",
            "validate_sync_committee_message_gossip",
            "validate_target_epoch_against_current_time",
            "validate_voluntary_exit_gossip",
            "verify_attestation_payload_status",
            "weigh_justification_and_finalization",
            "will_current_target_be_justified",
            "will_no_conflicting_checkpoint_be_justified",
        }
