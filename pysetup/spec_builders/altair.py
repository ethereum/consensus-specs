from typing import Dict

from .base import BaseSpecBuilder
from ..constants import ALTAIR, OPTIMIZED_BLS_AGGREGATE_PUBKEYS


class AltairSpecBuilder(BaseSpecBuilder):
    fork: str = ALTAIR

    @classmethod
    def imports(cls, preset_name: str) -> str:
        return f'''
from typing import NewType, Union as PyUnion

from eth2spec.phase0 import {preset_name} as phase0
from eth2spec.test.helpers.merkle import build_proof
from eth2spec.utils.ssz.ssz_typing import Path
'''

    @classmethod
    def preparations(cls):
        return '''
SSZVariableName = str
GeneralizedIndex = int
'''

    @classmethod
    def sundry_functions(cls) -> str:
        return '''
def get_generalized_index(ssz_class: Any, *path: PyUnion[int, SSZVariableName]) -> GeneralizedIndex:
    ssz_path = Path(ssz_class)
    for item in path:
        ssz_path = ssz_path / item
    return GeneralizedIndex(ssz_path.gindex())


def compute_merkle_proof(object: SSZObject,
                         index: GeneralizedIndex) -> list[Bytes32]:
    return build_proof(object.get_backing(), index)'''


    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        return {
            'FINALIZED_ROOT_GINDEX': 'GeneralizedIndex(105)',
            'CURRENT_SYNC_COMMITTEE_GINDEX': 'GeneralizedIndex(54)',
            'NEXT_SYNC_COMMITTEE_GINDEX': 'GeneralizedIndex(55)',
        }

    @classmethod
    def implement_optimizations(cls, functions: Dict[str, str]) -> Dict[str, str]:
        if "eth_aggregate_pubkeys" in functions:
            functions["eth_aggregate_pubkeys"] = OPTIMIZED_BLS_AGGREGATE_PUBKEYS.strip()
        return functions
