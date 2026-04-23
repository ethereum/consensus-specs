from ..constants import GLOAS
from .base import BaseSpecBuilder


class GloasSpecBuilder(BaseSpecBuilder):
    fork: str = GLOAS

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.fulu import {preset_name} as fulu
"""

    @classmethod
    def deprecate_constants(cls) -> set[str]:
        return set(
            [
                "EXECUTION_PAYLOAD_GINDEX",
            ]
        )

    @classmethod
    def deprecate_presets(cls) -> set[str]:
        return set(
            [
                "KZG_COMMITMENT_INCLUSION_PROOF_DEPTH",
                "KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH",
            ]
        )

    @classmethod
    def deprecate_containers(cls) -> set[str]:
        return set(
            [
                "ExecutionPayloadHeader",
                "PartialDataColumnHeader",
                # Temporarily deprecate light-client containers
                # See: https://github.com/ethereum/consensus-specs/pull/5142
                "ExecutionBranch",
                "LightClientBootstrap",
                "LightClientFinalityUpdate",
                "LightClientHeader",
                "LightClientOptimisticUpdate",
                "LightClientStore",
                "LightClientUpdate",
            ]
        )

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return set(
            [
                "compute_proposer_index",
                "initialize_proposer_lookahead",
                "process_execution_payload",
                "retrieve_column_sidecars",
                "verify_partial_data_column_header_inclusion_proof",
                "upgrade_to_fulu",
                # Temporarily deprecate light-client functions
                # See: https://github.com/ethereum/consensus-specs/pull/5142
                "apply_light_client_update",
                "block_to_light_client_header",
                "create_light_client_bootstrap",
                "create_light_client_finality_update",
                "create_light_client_optimistic_update",
                "create_light_client_update",
                "get_lc_execution_root",
                "get_safety_threshold",
                "initialize_light_client_store",
                "is_better_update",
                "is_finality_update",
                "is_next_sync_committee_known",
                "is_sync_committee_update",
                "is_valid_light_client_header",
                "process_light_client_finality_update",
                "process_light_client_optimistic_update",
                "process_light_client_store_force_update",
                "process_light_client_update",
                "upgrade_lc_bootstrap_to_capella",
                "upgrade_lc_bootstrap_to_deneb",
                "upgrade_lc_bootstrap_to_electra",
                "upgrade_lc_finality_update_to_capella",
                "upgrade_lc_finality_update_to_deneb",
                "upgrade_lc_finality_update_to_electra",
                "upgrade_lc_header_to_capella",
                "upgrade_lc_header_to_deneb",
                "upgrade_lc_header_to_electra",
                "upgrade_lc_optimistic_update_to_capella",
                "upgrade_lc_optimistic_update_to_deneb",
                "upgrade_lc_optimistic_update_to_electra",
                "upgrade_lc_store_to_capella",
                "upgrade_lc_store_to_deneb",
                "upgrade_lc_store_to_electra",
                "upgrade_lc_update_to_capella",
                "upgrade_lc_update_to_deneb",
                "upgrade_lc_update_to_electra",
                "validate_light_client_update",
            ]
        )

    @classmethod
    def sundry_functions(cls) -> str:
        return """
def retrieve_column_sidecars_and_kzg_commitments(
    beacon_block_root: Root
) -> tuple[Sequence[DataColumnSidecar], Sequence[KZGCommitment]]:
    # pylint: disable=unused-argument
    return [], []
"""
