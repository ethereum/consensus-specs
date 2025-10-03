from ..constants import GLOAS
from .base import BaseSpecBuilder


class GloasSpecBuilder(BaseSpecBuilder):
    fork: str = GLOAS

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth2spec.utils.ssz.ssz_typing import ProgressiveBitlist, ProgressiveContainer, ProgressiveList

from eth2spec.fulu import {preset_name} as fulu
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
