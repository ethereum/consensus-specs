from ..constants import FULU
from .base import BaseSpecBuilder


class FuluSpecBuilder(BaseSpecBuilder):
    fork: str = FULU

    @classmethod
    def imports(cls, preset_name: str):
        return f"""
from frozendict import frozendict
from eth_consensus_specs.electra import {preset_name} as electra
"""

    @classmethod
    def classes(cls):
        return """
class PolynomialCoeff(list):
    def __init__(self, coeffs: Sequence[BLSFieldElement]):
        if len(coeffs) > FIELD_ELEMENTS_PER_EXT_BLOB:
            raise ValueError("expected <= FIELD_ELEMENTS_PER_EXT_BLOB coeffs")
        super().__init__(coeffs)


class Coset(list):
    def __init__(self, coeffs: Optional[Sequence[BLSFieldElement]] = None):
        if coeffs is None:
            coeffs = [BLSFieldElement(0)] * FIELD_ELEMENTS_PER_CELL
        if len(coeffs) != FIELD_ELEMENTS_PER_CELL:
            raise ValueError("expected FIELD_ELEMENTS_PER_CELL coeffs")
        super().__init__(coeffs)


class CosetEvals(list):
    def __init__(self, evals: Optional[Sequence[BLSFieldElement]] = None):
        if evals is None:
            evals = [BLSFieldElement(0)] * FIELD_ELEMENTS_PER_CELL
        if len(evals) != FIELD_ELEMENTS_PER_CELL:
            raise ValueError("expected FIELD_ELEMENTS_PER_CELL coeffs")
        super().__init__(evals)
"""

    @classmethod
    def sundry_functions(cls) -> str:
        return """
def retrieve_column_sidecars(beacon_block_root: Root) -> Sequence[DataColumnSidecar]:
    # pylint: disable=unused-argument
    return []


_compute_proposer_indices = compute_proposer_indices
compute_proposer_indices = cache_this(
    lambda state, epoch, seed, indices: (state.validators.hash_tree_root(), epoch, seed),
    _compute_proposer_indices, lru_size=SLOTS_PER_EPOCH * 2)
"""

    @classmethod
    def hardcoded_func_dep_presets(cls, spec_object) -> dict[str, str]:
        return {
            "KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH": spec_object.preset_vars[
                "KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH"
            ].value,
        }
