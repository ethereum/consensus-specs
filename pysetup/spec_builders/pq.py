from pysetup.constants import PQ

from .base import BaseSpecBuilder


class PQSpecBuilder(BaseSpecBuilder):
    fork: str = PQ

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.eip8483 import {preset_name} as eip8483
from eth_consensus_specs.utils import stark, xmss
from eth_consensus_specs.utils.ssz.bytes import Bytes16
"""

    @classmethod
    def deprecate_constants(cls) -> set[str]:
        return {
            "BUILDER_PQ_REGISTRATION_REQUEST_TYPE",
            "CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS",
            "G2_POINT_AT_INFINITY",
            "NEXT_SYNC_COMMITTEE_GINDEX_GLOAS",
            "TARGET_AGGREGATORS_PER_COMMITTEE",
            "VALIDATOR_PQ_REGISTRATION_REQUEST_TYPE",
        }

    @classmethod
    def deprecate_presets(cls) -> set[str]:
        return {
            "EPOCHS_PER_SYNC_COMMITTEE_PERIOD",
            "MAX_ATTESTATIONS_ELECTRA",
            "MAX_ATTESTER_SLASHING_SIZE",
            "MAX_BLS_TO_EXECUTION_CHANGES",
            "MAX_BUILDER_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD",
            "MAX_PAYLOAD_ATTESTATIONS",
            "MAX_SIGNED_AGGREGATE_AND_PROOF_SIZE",
            "MAX_SIGNED_EXECUTION_PAYLOAD_BID_SIZE",
            "MAX_VALIDATOR_PQ_REGISTRATION_REQUESTS_PER_PAYLOAD",
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
            "BuilderPQRegistration",
            "BuilderPQRegistrationRequest",
            "BuilderPQRegistrationRequests",
            "BuilderPQRegistrations",
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
            "ValidatorPQRegistration",
            "ValidatorPQRegistrationRequest",
            "ValidatorPQRegistrationRequests",
            "ValidatorPQRegistrations",
        }

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return {
            "apply_light_client_update",
            "block_to_light_client_header",
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
            "get_aggregate_signature",
            "get_contribution_and_proof",
            "get_contribution_and_proof_signature",
            "get_contribution_due_ms",
            "get_epoch_signature",
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
            "initialize_light_client_store",
            "is_assigned_to_sync_committee",
            "is_better_update",
            "is_finality_update",
            "is_next_sync_committee_known",
            "is_sync_committee_aggregator",
            "is_sync_committee_update",
            "is_valid_builder_deposit_signature",
            "is_valid_deposit_signature",
            "is_valid_indexed_payload_attestation",
            "is_valid_light_client_header",
            "next_sync_committee_gindex_at_slot",
            "notify_ptc_messages",
            "onboard_builders_from_pending_deposits",
            "process_bls_to_execution_change",
            "process_builder_pq_registration_request",
            "process_light_client_finality_update",
            "process_light_client_optimistic_update",
            "process_light_client_store_force_update",
            "process_light_client_update",
            "process_payload_attestation",
            "process_sync_aggregate",
            "process_sync_committee_contributions",
            "process_sync_committee_updates",
            "process_validator_pq_registration_request",
            "upgrade_attestation_to_gloas",
            "upgrade_attester_slashing_to_gloas",
            "upgrade_indexed_attestation_to_gloas",
            "upgrade_lc_bootstrap_to_gloas",
            "upgrade_lc_finality_update_to_gloas",
            "upgrade_lc_header_to_gloas",
            "upgrade_lc_optimistic_update_to_gloas",
            "upgrade_lc_store_to_gloas",
            "upgrade_lc_update_to_gloas",
            "upgrade_to_eip8483",
            "validate_bls_to_execution_change_gossip",
            "validate_light_client_update",
            "validate_sync_committee_contribution_and_proof_gossip",
            "validate_sync_committee_message_gossip",
        }
