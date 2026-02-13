from collections.abc import Callable, Sequence
from typing import Any

from lru import LRU

from tests.core.pyspec.eth2spec.test.helpers.genesis import create_genesis_state
from tests.core.pyspec.eth2spec.test.helpers.typing import Spec, SpecForks


def _prepare_state(
    balances_fn: Callable[[Any], Sequence[int]],
    threshold_fn: Callable[[Any], int],
    spec: Spec,
    phases: SpecForks,
):
    balances = balances_fn(spec)
    activation_threshold = threshold_fn(spec)
    state = create_genesis_state(
        spec=spec,
        validator_balances=balances,
        activation_threshold=activation_threshold,
    )
    return state


_custom_state_cache_dict = LRU(size=10)


def with_custom_state(
    balances_fn: Callable[[Any], Sequence[int]], threshold_fn: Callable[[Any], int]
):
    """
    Decorator that provides a cached BeaconState constructed from custom balances
    and activation threshold functions. The cache key is a tuple of:
      (spec.fork, spec.config.__hash__(), spec.__file__, balances_fn, threshold_fn)
    The cached value stores the immutable state backing to enable fast view reconstruction.
    """

    def deco(fn):
        def entry(*args, spec: Spec, phases: SpecForks, **kw):
            key = (
                spec.fork,
                spec.config.__hash__(),
                spec.__file__,
                balances_fn,
                threshold_fn,
            )
            if key not in _custom_state_cache_dict:
                state = _prepare_state(balances_fn, threshold_fn, spec, phases)
                _custom_state_cache_dict[key] = state.get_backing()

            # Wrap cached immutable backing with a fresh view
            state = spec.BeaconState(backing=_custom_state_cache_dict[key])
            kw["state"] = state
            return fn(*args, spec=spec, phases=phases, **kw)

        return entry

    return deco
