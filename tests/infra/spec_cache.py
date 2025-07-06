import inspect
from functools import _make_key

DISABLED_CACHE = False

CACHES = {}


def spec_cache(cache_fns: list[str] | str):
    """
    Decorator to cache the results of a function in the spec object.
    """

    if isinstance(cache_fns, str):
        cache_fns = [cache_fns]

    def decorator(fn):
        if DISABLED_CACHE:
            return fn

        def wrapper(*args, **kwargs):
            spec = kwargs["spec"]
            if spec is None:
                raise ValueError(
                    "Decorator 'spec_cache' requires a previous decorator that adds a spec."
                )

            spec_key = make_spec_key(spec)
            if spec_key not in CACHES:
                CACHES[spec_key] = SpecCache(spec)

            CACHES[spec_key].register_function_list(cache_fns)

            try:
                result = fn(*args, **kwargs)
            finally:
                CACHES[spec_key].deregister_function_list(cache_fns)

            return result

        def wrapper_generator(*args, **kwargs):
            spec = kwargs["spec"]
            if spec is None:
                raise ValueError(
                    "Decorator 'spec_cache' requires a previous decorator that adds a spec."
                )

            spec_key = make_spec_key(spec)
            if spec_key not in CACHES:
                CACHES[spec_key] = SpecCache(spec)

            CACHES[spec_key].register_function_list(cache_fns)

            try:
                yield from fn(*args, **kwargs)
            finally:
                CACHES[spec_key].deregister_function_list(cache_fns)

        if inspect.isgeneratorfunction(fn):
            return wrapper_generator
        else:
            return wrapper

    return decorator


def spec_cache_peerdas(fn):
    return spec_cache(
        [
            "compute_cells_and_kzg_proofs",
            "verify_data_column_sidecar_kzg_proofs",
            "recover_cells_and_kzg_proofs",
        ]
    )(fn)


def make_spec_key(spec):
    return hash((spec.fork, spec.config))


class SpecCacheStats:
    """
    A class to manage statistics for multiple cached functions.
    """

    def __init__(self):
        self.stats = {}

    def record_hit(self, fn_name: str):
        if fn_name not in self.stats:
            self.stats[fn_name] = SpecCacheStat()
        self.stats[fn_name].record_hit()

    def record_miss(self, fn_name: str):
        if fn_name not in self.stats:
            self.stats[fn_name] = SpecCacheStat()
        self.stats[fn_name].record_miss()

    def get_stats(self, fn_name: str):
        return self.stats.get(fn_name, SpecCacheStat()).get_stats()

    def get_total_stats(self):
        total_hits = sum(stat.hits for stat in self.stats.values())
        total_misses = sum(stat.misses for stat in self.stats.values())
        return {
            "total_hits": total_hits,
            "total_misses": total_misses,
            "total_hit_rate": total_hits / (total_hits + total_misses)
            if (total_hits + total_misses) > 0
            else 0,
        }


class SpecCache:
    """
    A class to manage caching of function results in a specification context.
    """

    def __init__(self, spec):
        self.spec = spec
        self.cache = {}
        self.original_fns = {}
        self.stats = SpecCacheStats()

    def register_function(self, fn_name: str):
        """
        Register a function to be cached.
        """
        if not hasattr(self.spec, fn_name):
            raise ValueError(f"Function '{fn_name}' does not exist in the spec object.")

        if fn_name in self.original_fns:
            raise ValueError(f"Function '{fn_name}' is already cached.")

        if fn_name not in self.cache:
            self.cache[fn_name] = {}

        self.original_fns[fn_name] = getattr(self.spec, fn_name)

        setattr(self.spec, fn_name, self._get_cached_fn(fn_name))

    def deregister_function(self, fn_name: str):
        """
        Deregister a function.
        """
        assert fn_name in self.original_fns, f"Function {fn_name} is not cached."

        setattr(self.spec, fn_name, self.original_fns[fn_name])
        del self.original_fns[fn_name]

    def get_stats(self) -> SpecCacheStats:
        return self.stats

    def _get_cached_fn(self, fn_name: str):
        def cached_fn(*args, **kwargs):
            key = SpecCache._make_input_key(args, kwargs)

            result = self.cache[fn_name].get(key)
            if result is None:
                # print(f"Cache miss for {fn_name}.")
                self.stats.record_miss(fn_name)
                original_fn = self.original_fns[fn_name]
                result = original_fn(*args, **kwargs)
                self.cache[fn_name][key] = result
            else:
                self.stats.record_hit(fn_name)
                # print(f"Cache hit for {fn_name}.")

            return result

        return cached_fn

    def register_function_list(self, fn_names: list[str]):
        for fn_name in fn_names:
            self.register_function(fn_name)

    def deregister_function_list(self, fn_names: list[str]):
        for fn_name in fn_names:
            self.deregister_function(fn_name)

    @staticmethod
    def _make_input_key(args, kwargs):
        """
        Create a hashable key from the function arguments and keyword arguments.
        This method attempts to use the original _make_key for simple cases,
        and falls back to a custom hashable representation for complex cases.
        """
        try:
            # Attempt to use the original _make_key for simple cases
            return _make_key(args, kwargs, typed=False)
        except TypeError:
            # If it fails, we need to create a custom hashable representation
            pass

        hashable_args = tuple(SpecCache._make_hashable(arg) for arg in args)
        hashable_kwargs = tuple((k, SpecCache._make_hashable(v)) for k, v in kwargs.items())

        return hash((hashable_args, hashable_kwargs))

    @staticmethod
    def _make_hashable(obj):
        """
        Convert an object into a hashable representation.
        """
        if isinstance(obj, dict):
            return tuple(sorted((k, SpecCache._make_hashable(v)) for k, v in obj.items()))
        elif isinstance(obj, list | tuple):
            return tuple(SpecCache._make_hashable(item) for item in obj)
        elif isinstance(obj, set):
            return tuple(sorted(SpecCache._make_hashable(item) for item in obj))
        elif hasattr(obj, "__dict__"):
            return tuple(sorted((k, SpecCache._make_hashable(v)) for k, v in obj.__dict__.items()))
        else:
            try:
                hash(obj)
                return obj
            except TypeError:
                raise ValueError(f"Object of type {type(obj)} is not hashable.")


class SpecCacheStat:
    """
    A class to manage statistics for cached functions.
    """

    def __init__(self):
        self.hits = 0
        self.misses = 0

    def record_hit(self):
        self.hits += 1

    def record_miss(self):
        self.misses += 1

    def get_stats(self):
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / (self.hits + self.misses)
            if (self.hits + self.misses) > 0
            else 0,
        }
