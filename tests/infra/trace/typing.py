from collections.abc import Sequence
from typing import TypeAlias

from eth2spec.utils.ssz.ssz_typing import View

# normal primitives (can subclass View or not)
PRIMITIVES: TypeAlias = bool | int | str | bytes

# typing aliases for serialized values and arguments
SERIALIZED: TypeAlias = PRIMITIVES | None  # optional primitives
# two recursion levels max
SERIALIZED_ARGS: TypeAlias = SERIALIZED | list[SERIALIZED] | list[list[SERIALIZED] | SERIALIZED]
SERIALIZED_KWARGS: TypeAlias = dict[str, SERIALIZED_ARGS]

# typing aliases for non-serialized values and arguments
RAW: TypeAlias = View | None  # allowed simple argument types (View is wide!)
RAW_ARGS: TypeAlias = RAW | Sequence[RAW] | Sequence[Sequence[RAW] | RAW]
RAW_KWARGS: TypeAlias = dict[str, RAW_ARGS]

STATE: TypeAlias = View  # this could be generic
