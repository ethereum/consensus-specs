from pysetup.constants import PQ

from .base import BaseSpecBuilder


class PQSpecBuilder(BaseSpecBuilder):
    fork: str = PQ

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.prereg import {preset_name} as prereg
from eth_consensus_specs.utils import stark, xmss
"""

    @classmethod
    def sundry_functions(cls) -> str:
        return """
get_total_active_balance = cache_this(
    lambda state: (state.pq_validators.hash_tree_root(), compute_epoch_at_slot(state.slot)),
    _get_total_active_balance, lru_size=10)

get_base_reward = cache_this(
    lambda state, index, *args: (state.pq_validators.hash_tree_root(), state.slot, index, *args),
    _get_base_reward, lru_size=2048)

get_committee_count_per_slot = cache_this(
    lambda state, epoch: (state.pq_validators.hash_tree_root(), epoch),
    _get_committee_count_per_slot, lru_size=SLOTS_PER_EPOCH * 3)

get_active_validator_indices = cache_this(
    lambda state, epoch: (state.pq_validators.hash_tree_root(), epoch),
    _get_active_validator_indices, lru_size=3)

get_beacon_committee = cache_this(
    lambda state, slot, index: (
        state.pq_validators.hash_tree_root(), state.randao_mixes.hash_tree_root(), slot, index
    ),
    _get_beacon_committee, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)

get_attesting_indices = cache_this(
    lambda state, attestation: (
        state.randao_mixes.hash_tree_root(),
        state.pq_validators.hash_tree_root(), attestation.hash_tree_root()
    ),
    _get_attesting_indices, lru_size=SLOTS_PER_EPOCH * MAX_COMMITTEES_PER_SLOT * 3)

compute_balance_weighted_selection = cache_this(
    lambda state, indices, seed, size, shuffle_indices: (
        state.pq_validators.hash_tree_root(), tuple(indices), seed, size, shuffle_indices
    ),
    _compute_balance_weighted_selection, lru_size=SLOTS_PER_EPOCH * 6)
"""

    @classmethod
    def deprecate_constants(cls) -> set[str]:
        return {
            "CONSOLIDATION_REQUEST_TYPE",
            "CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS",
            "DOMAIN_SELECTION_PROOF",
            "G2_POINT_AT_INFINITY",
            "NEXT_SYNC_COMMITTEE_GINDEX_GLOAS",
            "PQ_REGISTRATION_REQUEST_TYPE",
            "TARGET_AGGREGATORS_PER_COMMITTEE",
        }

    @classmethod
    def deprecate_presets(cls) -> set[str]:
        return {
            "EPOCHS_PER_SYNC_COMMITTEE_PERIOD",
            "MAX_ATTESTATIONS_ELECTRA",
            "MAX_ATTESTER_SLASHING_SIZE",
            "MAX_BLS_TO_EXECUTION_CHANGES",
            "MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD",
            "MAX_PAYLOAD_ATTESTATIONS",
            "MAX_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD",
            "MAX_SIGNED_AGGREGATE_AND_PROOF_SIZE",
            "MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE",
            "MIN_SYNC_COMMITTEE_PARTICIPANTS",
            "SYNC_COMMITTEE_SIZE",
            "UPDATE_TIMEOUT",
        }

    @classmethod
    def deprecate_config_vars(cls) -> set[str]:
        return {
            "CONTRIBUTION_DUE_BPS_GLOAS",
            "SYNC_MESSAGE_DUE_BPS_GLOAS",
        }

    @classmethod
    def deprecate_containers(cls) -> set[str]:
        return {
            "BLSToExecutionChange",
            "BLSToExecutionChanges",
            "ConsolidationRequest",
            "ConsolidationRequests",
            "ContributionAndProof",
            "CurrentSyncCommitteeBranch",
            "ExecutionBranch",
            "FinalityBranch",
            "IndexedPayloadAttestation",
            "LightClientBootstrap",
            "LightClientFinalityUpdate",
            "LightClientHeader",
            "LightClientOptimisticUpdate",
            "LightClientStore",
            "LightClientUpdate",
            "LightClientUpdates",
            "NextSyncCommitteeBranch",
            "PQRegistration",
            "PQRegistrationRequest",
            "PQRegistrationRequests",
            "PQRegistrations",
            "PayloadAttestation",
            "PayloadAttestations",
            "PayloadTimelinessCommitteeBits",
            "PayloadTimelinessCommitteeIndices",
            "SignedBLSToExecutionChange",
            "SignedContributionAndProof",
            "SyncAggregate",
            "SyncAggregatorSelectionData",
            "SyncCommittee",
            "SyncCommitteeBits",
            "SyncCommitteeContribution",
            "SyncCommitteeMessage",
            "SyncCommitteePubkeys",
            "SyncSubcommitteeBits",
        }

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "add_builder_to_registry",
            "add_validator_to_registry",
            "apply_light_client_update",
            "block_to_light_client_header",
            "compute_consolidation_epoch_and_update_churn",
            "compute_subnets_for_sync_committee",
            "compute_sync_committee_period",
            "compute_sync_committee_period_at_slot",
            "create_light_client_bootstrap",
            "create_light_client_finality_update",
            "create_light_client_optimistic_update",
            "create_light_client_update",
            "current_sync_committee_gindex_at_slot",
            "eth_aggregate_pubkeys",
            "eth_fast_aggregate_verify",
            "finalized_root_gindex_at_slot",
            "get_contribution_and_proof",
            "get_contribution_and_proof_signature",
            "get_contribution_due_ms",
            "get_index_for_new_builder",
            "get_index_for_new_validator",
            "get_indexed_payload_attestation",
            "get_lc_execution_root",
            "get_next_sync_committee",
            "get_next_sync_committee_indices",
            "get_safety_threshold",
            "get_slot_signature",
            "get_sync_committee_message",
            "get_sync_committee_selection_proof",
            "get_sync_message_due_ms",
            "get_sync_subcommittee_pubkeys",
            "get_validator_from_deposit",
            "initialize_light_client_store",
            "is_assigned_to_sync_committee",
            "is_better_update",
            "is_finality_update",
            "is_next_sync_committee_known",
            "is_pending_validator",
            "is_sync_committee_aggregator",
            "is_sync_committee_update",
            "is_valid_indexed_payload_attestation",
            "is_valid_light_client_header",
            "is_valid_switch_to_compounding_request",
            "next_sync_committee_gindex_at_slot",
            "notify_ptc_messages",
            "onboard_builders_from_pending_deposits",
            "process_bls_to_execution_change",
            "process_consolidation_request",
            "process_light_client_finality_update",
            "process_light_client_optimistic_update",
            "process_light_client_store_force_update",
            "process_light_client_update",
            "process_payload_attestation",
            "process_pq_registration_request",
            "process_sync_aggregate",
            "process_sync_committee_contributions",
            "process_sync_committee_updates",
            "queue_excess_active_balance",
            "switch_to_compounding_validator",
            "upgrade_attestation_to_gloas",
            "upgrade_attester_slashing_to_gloas",
            "upgrade_indexed_attestation_to_gloas",
            "upgrade_lc_bootstrap_to_gloas",
            "upgrade_lc_finality_update_to_gloas",
            "upgrade_lc_header_to_gloas",
            "upgrade_lc_optimistic_update_to_gloas",
            "upgrade_lc_store_to_gloas",
            "upgrade_lc_update_to_gloas",
            "upgrade_to_prereg",
            "validate_bls_to_execution_change_gossip",
            "validate_light_client_update",
            "validate_sync_committee_contribution_and_proof_gossip",
            "validate_sync_committee_message_gossip",
        }
