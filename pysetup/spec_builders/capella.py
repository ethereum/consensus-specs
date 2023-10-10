from typing import Dict

from .base import BaseSpecBuilder
from ..constants import CAPELLA


class CapellaSpecBuilder(BaseSpecBuilder):
    fork: str = CAPELLA

    @classmethod
    def imports(cls, preset_name: str):
        return f'''
from eth2spec.bellatrix import {preset_name} as bellatrix
'''


    @classmethod
    def sundry_functions(cls) -> str:
        return '''
def compute_merkle_proof_for_block_body(body: BeaconBlockBody,
                                        index: GeneralizedIndex) -> Sequence[Bytes32]:
    return build_proof(body.get_backing(), index)'''


    @classmethod
    def hardcoded_ssz_dep_constants(cls) -> Dict[str, str]:
        return {
            'EXECUTION_PAYLOAD_INDEX': 'GeneralizedIndex(25)',
        }
