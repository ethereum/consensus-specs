from typing import Dict, Set

from .base import BaseSpecBuilder
from ..constants import EIP7732


class EIP7732SpecBuilder(BaseSpecBuilder):
    fork: str = EIP7732

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.electra import {preset_name} as electra
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return '''
def concat_generalized_indices(*indices: GeneralizedIndex) -> GeneralizedIndex:
    o = GeneralizedIndex(1)
    for i in indices:
        o = GeneralizedIndex(o * bit_floor(i) + (i - bit_floor(i)))
    return o'''


    @classmethod
    def hardcoded_custom_type_dep_constants(cls, spec_object) -> Dict[str, str]:
        return {
            'PTC_SIZE': spec_object.preset_vars['PTC_SIZE'].value,
            'MAX_PAYLOAD_ATTESTATIONS': spec_object.preset_vars['MAX_PAYLOAD_ATTESTATIONS'].value,
            'KZG_COMMITMENT_INCLUSION_PROOF_DEPTH_EIP7732':
                spec_object.preset_vars['KZG_COMMITMENT_INCLUSION_PROOF_DEPTH_EIP7732'].value,
        }

    @classmethod
    def deprecate_constants(cls) -> Set[str]:
        return set([
            'EXECUTION_PAYLOAD_GINDEX',
        ])

    @classmethod
    def deprecate_presets(cls) -> Set[str]:
        return set([
            'KZG_COMMITMENT_INCLUSION_PROOF_DEPTH',
        ])
