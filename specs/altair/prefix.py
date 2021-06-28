from typing import NewType, Union

_temp = __import__("eth2spec.phase0", globals(), locals(), [PRESET_NAME])
phase0: Any = getattr(_temp, PRESET_NAME)
from eth2spec.utils.ssz.ssz_typing import Path

SSZVariableName = str
GeneralizedIndex = NewType('GeneralizedIndex', int)


def get_generalized_index(ssz_class: Any, *path: Sequence[Union[int, SSZVariableName]]) -> GeneralizedIndex:
    ssz_path = Path(ssz_class)
    for item in path:
        ssz_path = ssz_path / item
    return GeneralizedIndex(ssz_path.gindex())
