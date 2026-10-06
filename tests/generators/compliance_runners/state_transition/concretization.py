"""Provider-level strategies for turning abstract cases into concrete inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    import random


ConcreteAttributes = Mapping[str, Any]


class Concretizer(Protocol):
    """Choose concrete target attributes for one abstract coverage case."""

    def concretize(
        self, abstract_case: Any, spec: Any, rng: random.Random
    ) -> ConcreteAttributes: ...


@dataclass(frozen=True)
class ConcretizationStrategy:
    """A provider's concrete-attribute selection policy."""

    name: str
    concretizer: Concretizer


def concretize(
    strategy: ConcretizationStrategy,
    abstract_case: Any,
    spec: Any,
    rng: random.Random,
) -> dict[str, Any]:
    """Run and validate a provider strategy's concrete attribute assignment."""
    attributes = dict(strategy.concretizer.concretize(abstract_case, spec, rng))
    if not all(isinstance(name, str) for name in attributes):
        raise TypeError(f"{strategy.name}: concrete attribute names must be strings")
    return attributes
