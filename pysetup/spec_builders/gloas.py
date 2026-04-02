from ..constants import GLOAS, OPTIMIZED_BALANCE_WEIGHTED_SELECTION
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
    def sundry_functions(cls) -> str:
        return """
def retrieve_column_sidecars_and_kzg_commitments(
    beacon_block_root: Root
) -> tuple[Sequence[DataColumnSidecar], Sequence[KZGCommitment]]:
    # pylint: disable=unused-argument
    return [], []
"""

    @classmethod
    def implement_optimizations(cls, functions: dict[str, str]) -> dict[str, str]:
        if "compute_balance_weighted_selection" in functions:
            functions["compute_balance_weighted_selection"] = (
                OPTIMIZED_BALANCE_WEIGHTED_SELECTION.strip()
            )
        return functions
