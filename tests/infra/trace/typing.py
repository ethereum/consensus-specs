from collections.abc import Sequence  # noqa: F401
from typing import TypeAlias, TypeVar

from typing_extensions import TypeAliasType

from eth2spec.utils.ssz.ssz_typing import View

# normal primitives (can subclass View or not)
PRIMITIVES: TypeAlias = bool | int | str | bytes

# typing aliases for serialized values and arguments
SERIALIZED: TypeAlias = PRIMITIVES | None  # optional primitives
# recursive lists, allows arbitrary nesting
# (definition compatible with pydantic schema)
SERIALIZED_ARGS = TypeAliasType("SERIALIZED_ARGS", "SERIALIZED | list[SERIALIZED_ARGS]")
SERIALIZED_KWARGS: TypeAlias = dict[str, SERIALIZED_ARGS]
# typing aliases for non-serialized values and arguments
RAW: TypeAlias = View | None  # allowed simple argument types (View is wide!)
# recursive sequences, allows arbitrary nesting
RAW_ARGS = TypeAliasType("RAW_ARGS", "RAW | Sequence[RAW_ARGS]")
RAW_KWARGS: TypeAlias = dict[str, RAW_ARGS]

STATE = TypeVar("STATE", bound=View)
