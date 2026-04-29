from ..constants import GLOAS
from .base import BaseSpecBuilder


class GloasSpecBuilder(BaseSpecBuilder):
    fork: str = GLOAS

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth_consensus_specs.utils.ssz.ssz_typing import ProgressiveBitlist, ProgressiveContainer, ProgressiveList

from eth_consensus_specs.fulu import {preset_name} as fulu
"""

    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> dict[str, str]:
        return {
            "FINALIZED_ROOT_GINDEX_GLOAS": "GeneralizedIndex(735)",
            "CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS": "GeneralizedIndex(2945)",
            "NEXT_SYNC_COMMITTEE_GINDEX_GLOAS": "GeneralizedIndex(2946)",
            "EXECUTION_BLOCK_HASH_GINDEX": "GeneralizedIndex(412)",
            "EXECUTION_BLOCK_HASH_GINDEX_DENEB": "GeneralizedIndex(812)",
            "EXECUTION_BLOCK_HASH_GINDEX_GLOAS": "GeneralizedIndex(11424)",
        }

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
            ]
        )

    @classmethod
    def deprecate_functions(cls) -> set[str]:
        return set(
            [
                "compute_proposer_index",
                "get_activation_exit_churn_limit",
                "get_balance_churn_limit",
                "initialize_proposer_lookahead",
                "process_execution_payload",
                "retrieve_column_sidecars",
                "upgrade_to_fulu",
                "verify_partial_data_column_header_inclusion_proof",
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
