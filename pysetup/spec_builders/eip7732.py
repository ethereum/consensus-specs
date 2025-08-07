from ..constants import EIP7732
from .base import BaseSpecBuilder


class EIP7732SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7732

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from eth2spec.electra import {preset_name} as electra
"""

    @classmethod
    def sundry_functions(cls) -> str:
        return """
def get_power_of_two_floor(x: int) -> int:
    if x <= 1:
        return 1
    if x == 2:
        return x
    else:
        return 2 * get_power_of_two_floor(x // 2)

def concat_generalized_indices(*indices: GeneralizedIndex) -> GeneralizedIndex:
    o = GeneralizedIndex(1)
    for i in indices:
        o = GeneralizedIndex(o * get_power_of_two_floor(i) + (i - get_power_of_two_floor(i)))
    return o"""

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
            ]
        )
