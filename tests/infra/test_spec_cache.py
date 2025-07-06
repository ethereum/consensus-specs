from unittest.mock import patch

import pytest

import tests.infra.spec_cache as cache_module
from tests.infra.spec_cache import CACHES, spec_cache, SpecCache, SpecCacheStat, SpecCacheStats


class MockSpec:
    """Mock spec object for testing"""

    def __init__(self, fork="test_fork", config="test_config"):
        self.call_count = 0
        self.fork = fork
        self.config = config

    def test_function(self, x, y):
        """Test function that counts calls"""
        self.call_count += 1
        if x is None or y is None:
            return 0
        return x + y

    def test_function_with_kwargs(self, x, y=10):
        """Test function with keyword arguments"""
        self.call_count += 1
        return x + y

    def test_function_complex_args(self, data_dict, data_list):
        """Test function with complex arguments"""
        self.call_count += 1
        return len(data_dict) + len(data_list)


class TestSpecCache:
    """Test cases for SpecCache class"""

    def setup_method(self):
        """Setup for each test method"""
        self.mock_spec = MockSpec()
        self.cache = SpecCache(self.mock_spec)

    def test_init(self):
        """Test SpecCache initialization"""
        assert self.cache.spec is self.mock_spec
        assert isinstance(self.cache.cache, dict)
        assert isinstance(self.cache.original_fns, dict)
        assert isinstance(self.cache.stats, SpecCacheStats)
        assert len(self.cache.cache) == 0
        assert len(self.cache.original_fns) == 0

    def test_register_function_success(self):
        """Test successful function registration"""
        fn_name = "test_function"
        original_fn = getattr(self.mock_spec, fn_name)

        self.cache.register_function(fn_name)

        # Check that function is registered
        assert fn_name in self.cache.cache
        assert fn_name in self.cache.original_fns
        assert self.cache.original_fns[fn_name] == original_fn

        # Check that the spec function is replaced with cached version
        cached_fn = getattr(self.mock_spec, fn_name)
        assert cached_fn != original_fn

    def test_register_function_nonexistent(self):
        """Test registering a non-existent function raises ValueError"""
        with pytest.raises(
            ValueError, match="Function 'nonexistent' does not exist in the spec object"
        ):
            self.cache.register_function("nonexistent")

    def test_register_function_already_cached(self):
        """Test registering an already cached function raises ValueError"""
        fn_name = "test_function"
        self.cache.register_function(fn_name)

        with pytest.raises(ValueError, match="Function 'test_function' is already cached"):
            self.cache.register_function(fn_name)

    def test_deregister_function_success(self):
        """Test successful function deregistration"""
        fn_name = "test_function"
        original_fn = getattr(self.mock_spec, fn_name)

        # Register then deregister
        self.cache.register_function(fn_name)
        self.cache.deregister_function(fn_name)

        # Check that function is deregistered
        assert fn_name not in self.cache.original_fns
        assert getattr(self.mock_spec, fn_name) == original_fn

    def test_deregister_function_not_cached(self):
        """Test deregistering a non-cached function raises AssertionError"""
        with pytest.raises(AssertionError, match="Function test_function is not cached"):
            self.cache.deregister_function("test_function")

    def test_cache_preserved_after_deregister_reregister(self):
        """Test that cache is preserved when a function is deregistered and then registered again"""
        fn_name = "test_function"

        # Register function and populate cache
        self.cache.register_function(fn_name)

        # First call - cache miss
        result1 = self.mock_spec.test_function(1, 2)
        assert result1 == 3
        assert self.mock_spec.call_count == 1

        # Second call - cache hit
        result2 = self.mock_spec.test_function(1, 2)
        assert result2 == 3
        assert self.mock_spec.call_count == 1  # Should not increment

        # Verify cache stats before deregistration
        stats_before = self.cache.get_stats().get_stats(fn_name)
        assert stats_before["hits"] == 1
        assert stats_before["misses"] == 1

        # Deregister function
        self.cache.deregister_function(fn_name)

        # Verify function is deregistered but cache data is preserved
        assert fn_name not in self.cache.original_fns
        assert fn_name in self.cache.cache  # Cache should still exist
        stats_after_dereg = self.cache.get_stats().get_stats(fn_name)
        assert stats_after_dereg["hits"] == 1  # Stats should be preserved
        assert stats_after_dereg["misses"] == 1

        # Call function while deregistered - should not use cache
        result3 = self.mock_spec.test_function(1, 2)
        assert result3 == 3
        assert self.mock_spec.call_count == 2  # Should increment since not cached

        # Re-register the same function
        self.cache.register_function(fn_name)

        # Call with same args - should use preserved cache (cache hit)
        result4 = self.mock_spec.test_function(1, 2)
        assert result4 == 3
        assert self.mock_spec.call_count == 2  # Should not increment - cache hit

        # Verify cache stats after re-registration
        stats_after_rereg = self.cache.get_stats().get_stats(fn_name)
        assert stats_after_rereg["hits"] == 2  # Should have incremented due to cache hit
        assert stats_after_rereg["misses"] == 1  # Should be preserved from before

        # Test with different args - should be cache miss
        result5 = self.mock_spec.test_function(3, 4)
        assert result5 == 7
        assert self.mock_spec.call_count == 3  # Should increment

        # Final stats verification
        final_stats = self.cache.get_stats().get_stats(fn_name)
        assert final_stats["hits"] == 2
        assert final_stats["misses"] == 2

    def test_cached_function_miss_then_hit(self):
        """Test cache miss followed by cache hit"""
        fn_name = "test_function"
        self.cache.register_function(fn_name)

        # First call should be a cache miss
        result1 = self.mock_spec.test_function(1, 2)
        assert result1 == 3
        assert self.mock_spec.call_count == 1

        # Check stats after first call
        stats = self.cache.get_stats().get_stats(fn_name)
        assert stats["hits"] == 0
        assert stats["misses"] == 1

        # Second call with same args should be a cache hit
        result2 = self.mock_spec.test_function(1, 2)
        assert result2 == 3
        assert self.mock_spec.call_count == 1  # Should not increment

        # Check stats after second call
        stats = self.cache.get_stats().get_stats(fn_name)
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_cached_function_different_args(self):
        """Test cache with different arguments"""
        fn_name = "test_function"
        self.cache.register_function(fn_name)

        # Different args should cause cache miss
        result1 = self.mock_spec.test_function(1, 2)
        result2 = self.mock_spec.test_function(3, 4)

        assert result1 == 3
        assert result2 == 7
        assert self.mock_spec.call_count == 2

        # Check stats - both calls should be misses
        stats = self.cache.get_stats().get_stats(fn_name)
        assert stats["hits"] == 0
        assert stats["misses"] == 2

    def test_cached_function_with_kwargs(self):
        """Test caching with keyword arguments"""
        fn_name = "test_function_with_kwargs"
        self.cache.register_function(fn_name)

        # Test with kwargs
        result1 = self.mock_spec.test_function_with_kwargs(5, y=15)
        result2 = self.mock_spec.test_function_with_kwargs(5, y=15)

        assert result1 == 20
        assert result2 == 20
        assert self.mock_spec.call_count == 1  # Second call should be cached

        # Check stats - first call miss, second call hit
        stats = self.cache.get_stats().get_stats(fn_name)
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_register_function_list_success(self):
        """Test registering multiple functions"""
        fn_names = ["test_function", "test_function_with_kwargs"]
        self.cache.register_function_list(fn_names)

        for fn_name in fn_names:
            assert fn_name in self.cache.cache
            assert fn_name in self.cache.original_fns

    def test_register_function_list_partial_failure(self):
        """Test registering multiple functions with one failure"""
        fn_names = ["test_function", "nonexistent"]

        with pytest.raises(ValueError, match="Function 'nonexistent' does not exist"):
            self.cache.register_function_list(fn_names)

        # First function should still be registered
        assert "test_function" in self.cache.cache

    def test_deregister_function_list_success(self):
        """Test deregistering multiple functions"""
        fn_names = ["test_function", "test_function_with_kwargs"]

        # Register then deregister
        self.cache.register_function_list(fn_names)
        self.cache.deregister_function_list(fn_names)

        for fn_name in fn_names:
            assert fn_name not in self.cache.original_fns

    def test_deregister_function_list_partial_failure(self):
        """Test deregistering multiple functions with one failure"""
        fn_names = ["test_function", "test_function_with_kwargs"]

        # Only register one function
        self.cache.register_function("test_function")

        with pytest.raises(
            AssertionError, match="Function test_function_with_kwargs is not cached"
        ):
            self.cache.deregister_function_list(fn_names)


class TestSpecCacheMakeInputKey:
    """Test cases for SpecCache._make_input_key static method"""

    def test_make_input_key_simple_args(self):
        """Test _make_input_key with simple arguments"""
        args = (1, 2, "test")
        kwargs = {"key": "value"}

        key1 = SpecCache._make_input_key(args, kwargs)
        key2 = SpecCache._make_input_key(args, kwargs)

        assert key1 == key2

    def test_make_input_key_complex_args(self):
        """Test _make_input_key with complex arguments"""
        args = ([1, 2, 3], {"nested": "dict"})
        kwargs = {"list_arg": [4, 5, 6]}

        key1 = SpecCache._make_input_key(args, kwargs)
        key2 = SpecCache._make_input_key(args, kwargs)

        assert key1 == key2

    def test_make_input_key_different_args(self):
        """Test _make_input_key with different arguments produces different keys"""
        args1 = (1, 2)
        args2 = (1, 3)
        kwargs = {}

        key1 = SpecCache._make_input_key(args1, kwargs)
        key2 = SpecCache._make_input_key(args2, kwargs)

        assert key1 != key2

    @patch("tests.infra.spec_cache._make_key")
    def test_make_input_key_fallback_to_custom(self, mock_make_key):
        """Test _make_input_key falls back to custom implementation when _make_key fails"""
        mock_make_key.side_effect = TypeError("Cannot hash")

        args = ([1, 2], {"key": "value"})
        kwargs = {}

        key = SpecCache._make_input_key(args, kwargs)
        assert isinstance(key, int)  # hash returns int


class TestSpecCacheMakeHashable:
    """Test cases for SpecCache._make_hashable static method"""

    def test_make_hashable_dict(self):
        """Test _make_hashable with dictionary"""
        obj = {"b": 2, "a": 1}
        result = SpecCache._make_hashable(obj)

        expected = (("a", 1), ("b", 2))  # Should be sorted
        assert result == expected

    def test_make_hashable_list(self):
        """Test _make_hashable with list"""
        obj = [1, 2, 3]
        result = SpecCache._make_hashable(obj)

        expected = (1, 2, 3)
        assert result == expected

    def test_make_hashable_tuple(self):
        """Test _make_hashable with tuple"""
        obj = (1, 2, 3)
        result = SpecCache._make_hashable(obj)

        expected = (1, 2, 3)
        assert result == expected

    def test_make_hashable_set(self):
        """Test _make_hashable with set"""
        obj = {3, 1, 2}
        result = SpecCache._make_hashable(obj)

        expected = (1, 2, 3)  # Should be sorted
        assert result == expected

    def test_make_hashable_nested_structures(self):
        """Test _make_hashable with nested structures"""
        obj = {"list": [1, 2], "dict": {"nested": "value"}}
        result = SpecCache._make_hashable(obj)

        expected = (("dict", (("nested", "value"),)), ("list", (1, 2)))
        assert result == expected

    def test_make_hashable_object_with_dict(self):
        """Test _make_hashable with object that has __dict__"""

        class TestObj:
            def __init__(self):
                self.x = 1
                self.y = 2

        obj = TestObj()
        result = SpecCache._make_hashable(obj)

        expected = (("x", 1), ("y", 2))
        assert result == expected

    def test_make_hashable_already_hashable(self):
        """Test _make_hashable with already hashable object"""
        obj = "test_string"
        result = SpecCache._make_hashable(obj)

        assert result == obj

    def test_make_hashable_unhashable_object(self):
        """Test _make_hashable with unhashable object raises ValueError"""

        class UnhashableObj:
            __slots__ = ["value"]  # Prevent __dict__ creation

            def __init__(self):
                self.value = "test"

            def __hash__(self):
                raise TypeError("unhashable")

            def __eq__(self, other):
                return True  # To prevent any comparison issues

        obj = UnhashableObj()

        with pytest.raises(ValueError, match="Object of type .* is not hashable"):
            SpecCache._make_hashable(obj)


class TestSpecCacheStat:
    """Test cases for SpecCacheStat class"""

    def setup_method(self):
        """Setup for each test method"""
        self.stat = SpecCacheStat()

    def test_init(self):
        """Test SpecCacheStat initialization"""
        assert self.stat.hits == 0
        assert self.stat.misses == 0

    def test_record_hit(self):
        """Test recording cache hits"""
        self.stat.record_hit()
        assert self.stat.hits == 1
        assert self.stat.misses == 0

        self.stat.record_hit()
        assert self.stat.hits == 2

    def test_record_miss(self):
        """Test recording cache misses"""
        self.stat.record_miss()
        assert self.stat.hits == 0
        assert self.stat.misses == 1

        self.stat.record_miss()
        assert self.stat.misses == 2

    def test_get_stats_empty(self):
        """Test get_stats with no recorded events"""
        stats = self.stat.get_stats()

        expected = {"hits": 0, "misses": 0, "hit_rate": 0}
        assert stats == expected

    def test_get_stats_with_data(self):
        """Test get_stats with recorded events"""
        self.stat.record_hit()
        self.stat.record_hit()
        self.stat.record_miss()

        stats = self.stat.get_stats()

        expected = {"hits": 2, "misses": 1, "hit_rate": 2 / 3}
        assert stats == expected


class TestSpecCacheStats:
    """Test cases for SpecCacheStats class"""

    def setup_method(self):
        """Setup for each test method"""
        self.stats = SpecCacheStats()

    def test_init(self):
        """Test SpecCacheStats initialization"""
        assert isinstance(self.stats.stats, dict)
        assert len(self.stats.stats) == 0

    def test_record_hit_new_function(self):
        """Test recording hit for new function"""
        fn_name = "test_function"
        self.stats.record_hit(fn_name)

        assert fn_name in self.stats.stats
        assert self.stats.stats[fn_name].hits == 1
        assert self.stats.stats[fn_name].misses == 0

    def test_record_miss_new_function(self):
        """Test recording miss for new function"""
        fn_name = "test_function"
        self.stats.record_miss(fn_name)

        assert fn_name in self.stats.stats
        assert self.stats.stats[fn_name].hits == 0
        assert self.stats.stats[fn_name].misses == 1

    def test_record_hit_existing_function(self):
        """Test recording hit for existing function"""
        fn_name = "test_function"
        self.stats.record_hit(fn_name)
        self.stats.record_hit(fn_name)

        assert self.stats.stats[fn_name].hits == 2

    def test_get_stats_existing_function(self):
        """Test get_stats for existing function"""
        fn_name = "test_function"
        self.stats.record_hit(fn_name)
        self.stats.record_miss(fn_name)

        stats = self.stats.get_stats(fn_name)

        expected = {"hits": 1, "misses": 1, "hit_rate": 0.5}
        assert stats == expected

    def test_get_stats_nonexistent_function(self):
        """Test get_stats for non-existent function returns default stats"""
        stats = self.stats.get_stats("nonexistent")

        expected = {"hits": 0, "misses": 0, "hit_rate": 0}
        assert stats == expected

    def test_get_total_stats_empty(self):
        """Test get_total_stats with no recorded events"""
        stats = self.stats.get_total_stats()

        expected = {"total_hits": 0, "total_misses": 0, "total_hit_rate": 0}
        assert stats == expected

    def test_get_total_stats_with_data(self):
        """Test get_total_stats with recorded events across multiple functions"""
        self.stats.record_hit("func1")
        self.stats.record_hit("func1")
        self.stats.record_miss("func1")

        self.stats.record_hit("func2")
        self.stats.record_miss("func2")
        self.stats.record_miss("func2")

        stats = self.stats.get_total_stats()

        expected = {"total_hits": 3, "total_misses": 3, "total_hit_rate": 0.5}
        assert stats == expected


class TestSpecCacheIntegration:
    """Integration tests for SpecCache with complex scenarios"""

    def setup_method(self):
        """Setup for each test method"""
        self.mock_spec = MockSpec()
        self.cache = SpecCache(self.mock_spec)

    def test_complex_arguments_caching(self):
        """Test caching with complex arguments"""
        fn_name = "test_function_complex_args"
        self.cache.register_function(fn_name)

        data_dict = {"key1": "value1", "key2": [1, 2, 3]}
        data_list = [{"nested": "dict"}, [1, 2]]

        # First call
        result1 = self.mock_spec.test_function_complex_args(data_dict, data_list)
        assert result1 == 4  # 2 dict keys + 2 list items
        assert self.mock_spec.call_count == 1

        # Second call with same complex args should hit cache
        result2 = self.mock_spec.test_function_complex_args(data_dict, data_list)
        assert result2 == 4
        assert self.mock_spec.call_count == 1  # Should not increment

        # Verify cache statistics
        stats = self.cache.get_stats().get_stats(fn_name)
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_multiple_functions_caching(self):
        """Test caching multiple functions simultaneously"""
        fn_names = ["test_function", "test_function_with_kwargs"]
        self.cache.register_function_list(fn_names)

        # Call both functions
        result1 = self.mock_spec.test_function(1, 2)
        result2 = self.mock_spec.test_function_with_kwargs(5)

        assert result1 == 3
        assert result2 == 15
        assert self.mock_spec.call_count == 2

        # Call again - should use cache
        result3 = self.mock_spec.test_function(1, 2)
        result4 = self.mock_spec.test_function_with_kwargs(5)

        assert result3 == 3
        assert result4 == 15
        assert self.mock_spec.call_count == 2  # Should not increment

    def test_cache_stats_integration(self):
        """Test cache statistics integration"""
        fn_name = "test_function"
        self.cache.register_function(fn_name)

        # Generate some cache hits and misses
        self.mock_spec.test_function(1, 2)  # miss
        self.mock_spec.test_function(1, 2)  # hit
        self.mock_spec.test_function(3, 4)  # miss
        self.mock_spec.test_function(1, 2)  # hit

        # Check function-specific stats
        stats = self.cache.stats.get_stats(fn_name)
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["hit_rate"] == 0.5

        # Check total stats
        total_stats = self.cache.stats.get_total_stats()
        assert total_stats["total_hits"] == 2
        assert total_stats["total_misses"] == 2
        assert total_stats["total_hit_rate"] == 0.5


class ComplexTestClass:
    """Mock complex class with multiple fields including lists - no __eq__ or __repr__"""

    def __init__(self, id: int, name: str, values: list, nested_data: dict):
        self.id = id
        self.name = name
        self.values = values
        self.nested_data = nested_data


class NestedComplexClass:
    """Another complex class for nested testing - no __eq__ or __repr__"""

    def __init__(self, metadata: dict, items: list, references: set):
        self.metadata = metadata
        self.items = items
        self.references = references


class MockSpecWithComplexTypes:
    """Mock spec object with functions that take complex types"""

    def __init__(self):
        self.call_count = 0

    def process_complex_sequence(self, data_sequence, config=None):
        """Function that takes a sequence of complex objects"""
        self.call_count += 1
        if config is None:
            config = {}

        total_id = sum(item.id for item in data_sequence)
        total_values = sum(len(item.values) for item in data_sequence)
        return {"total_id": total_id, "total_values": total_values, "config": config}

    def process_nested_structures(self, primary_data, secondary_data_list, metadata_dict):
        """Function with multiple complex arguments"""
        self.call_count += 1

        result = {
            "primary_id": primary_data.id,
            "secondary_count": len(secondary_data_list),
            "metadata_keys": list(metadata_dict.keys()),
        }

        for item in secondary_data_list:
            if hasattr(item, "metadata"):
                result["has_metadata"] = True
                break

        return result

    def process_deeply_nested(self, complex_structure):
        """Function that processes deeply nested structures"""
        self.call_count += 1

        result = {}  # Use empty dict to avoid type inference issues
        result["processed"] = True

        if isinstance(complex_structure, dict):
            result["type"] = "dict"
            result["keys_count"] = len(complex_structure.keys())

            # Process nested lists
            for key, value in complex_structure.items():
                if isinstance(value, list):
                    result[f"{key}_list_length"] = len(value)
                    if value and hasattr(value[0], "__dict__"):
                        result[f"{key}_first_item_fields"] = list(value[0].__dict__.keys())

        elif isinstance(complex_structure, list):
            result["type"] = "list"
            result["length"] = len(complex_structure)

            if complex_structure and hasattr(complex_structure[0], "__dict__"):
                result["first_item_fields"] = list(complex_structure[0].__dict__.keys())

        return result


class TestSpecCacheComplexTypes:
    """Test cases for SpecCache with complex data types"""

    def setup_method(self):
        """Setup for each test method"""
        self.mock_spec = MockSpecWithComplexTypes()
        self.cache = SpecCache(self.mock_spec)

    def create_sample_complex_objects(self):
        """Helper to create sample complex objects"""
        obj1 = ComplexTestClass(
            id=1, name="object1", values=[10, 20, 30], nested_data={"type": "A", "priority": 1}
        )

        obj2 = ComplexTestClass(
            id=2,
            name="object2",
            values=[40, 50],
            nested_data={"type": "B", "priority": 2, "tags": ["important"]},
        )

        obj3 = ComplexTestClass(id=3, name="object3", values=[], nested_data={"type": "C"})

        return [obj1, obj2, obj3]

    def create_nested_complex_objects(self):
        """Helper to create nested complex objects"""
        nested1 = NestedComplexClass(
            metadata={"version": "1.0", "author": "test"},
            items=[{"id": 1, "value": "a"}, {"id": 2, "value": "b"}],
            references={101, 102, 103},
        )

        nested2 = NestedComplexClass(
            metadata={"version": "2.0", "category": "experimental"},
            items=[{"id": 3, "value": "c"}],
            references={201, 202},
        )

        return [nested1, nested2]

    def test_cache_complex_sequence_arguments(self):
        """Test caching with sequence of complex objects"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        complex_objects = self.create_sample_complex_objects()
        config = {"mode": "test", "options": [1, 2, 3]}

        # First call - should be cache miss
        result1 = self.mock_spec.process_complex_sequence(complex_objects, config)
        assert result1["total_id"] == 6  # 1 + 2 + 3
        assert result1["total_values"] == 5  # 3 + 2 + 0
        assert result1["config"]["mode"] == "test"
        assert self.mock_spec.call_count == 1

        # Second call with same arguments - should be cache hit
        result2 = self.mock_spec.process_complex_sequence(complex_objects, config)
        assert result2 == result1
        assert self.mock_spec.call_count == 1  # Should not increment

        # Verify cache statistics
        stats = self.cache.get_stats().get_stats(fn_name)
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_cache_with_different_complex_sequences(self):
        """Test that different complex sequences produce cache misses"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        complex_objects1 = self.create_sample_complex_objects()
        complex_objects2 = self.create_sample_complex_objects()

        # Modify one object to make sequences different
        complex_objects2[0].id = 999

        # Check initial stats
        initial_stats = self.cache.get_stats()
        initial_fn_stats = initial_stats.get_stats(fn_name)
        assert initial_fn_stats["misses"] == 0
        assert initial_fn_stats["hits"] == 0

        # Call with first sequence
        result1 = self.mock_spec.process_complex_sequence(complex_objects1)
        assert self.mock_spec.call_count == 1

        # Check stats after first call
        stats_after_first = self.cache.get_stats()
        first_fn_stats = stats_after_first.get_stats(fn_name)
        assert first_fn_stats["misses"] == 1
        assert first_fn_stats["hits"] == 0

        # Call with modified sequence - should be cache miss
        result2 = self.mock_spec.process_complex_sequence(complex_objects2)
        assert result2["total_id"] != result1["total_id"]  # Results should be different
        assert self.mock_spec.call_count == 2

        # Verify both calls were cache misses
        stats_after_second = self.cache.get_stats()
        second_fn_stats = stats_after_second.get_stats(fn_name)
        assert second_fn_stats["misses"] == 2
        assert second_fn_stats["hits"] == 0

    def test_cache_nested_complex_structures(self):
        """Test caching with multiple complex arguments including nested structures"""
        fn_name = "process_nested_structures"
        self.cache.register_function(fn_name)

        primary_data = self.create_sample_complex_objects()[0]
        secondary_data_list = self.create_nested_complex_objects()
        metadata_dict = {
            "session": {"id": "abc123", "timestamp": 1234567890},
            "config": {"debug": True, "levels": [1, 2, 3]},
            "users": [{"name": "user1"}, {"name": "user2"}],
        }

        # Check initial stats
        initial_stats = self.cache.get_stats()
        initial_fn_stats = initial_stats.get_stats(fn_name)
        assert initial_fn_stats["misses"] == 0
        assert initial_fn_stats["hits"] == 0

        # First call - cache miss
        result1 = self.mock_spec.process_nested_structures(
            primary_data, secondary_data_list, metadata_dict
        )
        assert result1["primary_id"] == 1
        assert result1["secondary_count"] == 2
        assert result1["has_metadata"] == True
        assert "session" in result1["metadata_keys"]
        assert self.mock_spec.call_count == 1

        # Check stats after first call
        stats_after_miss = self.cache.get_stats()
        miss_fn_stats = stats_after_miss.get_stats(fn_name)
        assert miss_fn_stats["misses"] == 1
        assert miss_fn_stats["hits"] == 0

        # Second call with same complex arguments - cache hit
        result2 = self.mock_spec.process_nested_structures(
            primary_data, secondary_data_list, metadata_dict
        )
        assert result2 == result1
        assert self.mock_spec.call_count == 1  # Should not increment

        # Check stats after second call
        stats_after_hit = self.cache.get_stats()
        hit_fn_stats = stats_after_hit.get_stats(fn_name)
        assert hit_fn_stats["misses"] == 1
        assert hit_fn_stats["hits"] == 1

    def test_cache_deeply_nested_dict_structures(self):
        """Test caching with deeply nested dictionary structures"""
        fn_name = "process_deeply_nested"
        self.cache.register_function(fn_name)

        complex_objects = self.create_sample_complex_objects()
        nested_objects = self.create_nested_complex_objects()

        deeply_nested_structure = {
            "level1": {
                "complex_list": complex_objects,
                "nested_list": nested_objects,
                "metadata": {"created": "2025-01-01", "version": 1.0},
            },
            "level2": {
                "data": complex_objects[:2],  # Subset
                "config": {"mode": "production", "flags": [True, False]},
                "refs": {"primary": complex_objects[0], "secondary": nested_objects},
            },
        }

        # Check initial stats
        initial_stats = self.cache.get_stats()
        initial_fn_stats = initial_stats.get_stats(fn_name)
        assert initial_fn_stats["misses"] == 0
        assert initial_fn_stats["hits"] == 0

        # First call - cache miss
        result1 = self.mock_spec.process_deeply_nested(deeply_nested_structure)
        assert result1["type"] == "dict"
        assert result1["keys_count"] == 2
        assert self.mock_spec.call_count == 1

        # Check stats after first call
        stats_after_miss = self.cache.get_stats()
        miss_fn_stats = stats_after_miss.get_stats(fn_name)
        assert miss_fn_stats["misses"] == 1
        assert miss_fn_stats["hits"] == 0

        # Second call with same structure - cache hit
        result2 = self.mock_spec.process_deeply_nested(deeply_nested_structure)
        assert result2 == result1
        assert self.mock_spec.call_count == 1  # Should not increment

        # Check stats after second call
        stats_after_hit = self.cache.get_stats()
        hit_fn_stats = stats_after_hit.get_stats(fn_name)
        assert hit_fn_stats["misses"] == 1
        assert hit_fn_stats["hits"] == 1

    def test_cache_list_of_complex_objects(self):
        """Test caching with lists containing complex objects"""
        fn_name = "process_deeply_nested"
        self.cache.register_function(fn_name)

        complex_objects = self.create_sample_complex_objects()

        # Check initial stats
        initial_stats = self.cache.get_stats()
        initial_fn_stats = initial_stats.get_stats(fn_name)
        assert initial_fn_stats["misses"] == 0
        assert initial_fn_stats["hits"] == 0

        # First call with list structure
        result1 = self.mock_spec.process_deeply_nested(complex_objects)
        assert result1["type"] == "list"
        assert result1["length"] == 3
        assert "first_item_fields" in result1
        assert self.mock_spec.call_count == 1

        # Check stats after first call
        stats_after_miss = self.cache.get_stats()
        miss_fn_stats = stats_after_miss.get_stats(fn_name)
        assert miss_fn_stats["misses"] == 1
        assert miss_fn_stats["hits"] == 0

        # Second call with same list - cache hit
        result2 = self.mock_spec.process_deeply_nested(complex_objects)
        assert result2 == result1
        assert self.mock_spec.call_count == 1  # Should not increment

        # Check stats after second call
        stats_after_hit = self.cache.get_stats()
        hit_fn_stats = stats_after_hit.get_stats(fn_name)
        assert hit_fn_stats["misses"] == 1
        assert hit_fn_stats["hits"] == 1

    def test_cache_with_modified_nested_objects(self):
        """Test that modifying nested objects creates new cache entries"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        complex_objects = self.create_sample_complex_objects()

        # First call
        result1 = self.mock_spec.process_complex_sequence(complex_objects)
        assert self.mock_spec.call_count == 1

        # Modify nested data in one object
        complex_objects[0].nested_data["new_field"] = "added"

        # Second call with modified object - should be cache miss
        result2 = self.mock_spec.process_complex_sequence(complex_objects)
        assert self.mock_spec.call_count == 2  # Should increment

        # Results should be the same since function doesn't use the modified field
        assert result1["total_id"] == result2["total_id"]
        assert result1["total_values"] == result2["total_values"]

    def test_cache_with_empty_complex_structures(self):
        """Test caching with empty complex structures"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        # Test with empty sequence
        empty_sequence = []

        result1 = self.mock_spec.process_complex_sequence(empty_sequence)
        assert result1["total_id"] == 0
        assert result1["total_values"] == 0
        assert self.mock_spec.call_count == 1

        # Second call with same empty sequence - should hit cache
        result2 = self.mock_spec.process_complex_sequence(empty_sequence)
        assert result2 == result1
        assert self.mock_spec.call_count == 1  # Should not increment

    def test_cache_statistics_with_complex_types(self):
        """Test cache statistics work correctly with complex types"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        complex_objects1 = self.create_sample_complex_objects()
        complex_objects2 = self.create_sample_complex_objects()
        complex_objects2[1].values.append(999)  # Make it different

        # Generate cache hits and misses
        self.mock_spec.process_complex_sequence(complex_objects1)  # miss
        self.mock_spec.process_complex_sequence(complex_objects1)  # hit
        self.mock_spec.process_complex_sequence(complex_objects2)  # miss
        self.mock_spec.process_complex_sequence(complex_objects1)  # hit
        self.mock_spec.process_complex_sequence(complex_objects2)  # hit

        # Check statistics
        stats = self.cache.stats.get_stats(fn_name)
        assert stats["hits"] == 3
        assert stats["misses"] == 2
        assert stats["hit_rate"] == 0.6

    def test_cache_with_circular_references_handling(self):
        """Test that cache throws RecursionError for circular references - documenting current limitation"""
        fn_name = "process_deeply_nested"
        self.cache.register_function(fn_name)

        # Create a structure that references itself (circular reference)
        circular_dict = {}  # Start with empty dict
        circular_dict["name"] = "root"
        nested_dict = {"parent": circular_dict, "data": [1, 2, 3]}
        circular_dict["child"] = nested_dict  # Create circular reference

        # The current implementation should raise RecursionError when trying to hash circular references
        # This test documents this known limitation
        with pytest.raises(RecursionError):
            self.mock_spec.process_deeply_nested(circular_dict)

        # Verify that the function was never actually called due to the error in cache key generation
        assert self.mock_spec.call_count == 0

        # Verify cache statistics - no stats should be recorded due to the error
        stats = self.cache.get_stats().get_stats(fn_name)
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestSpecCacheComplexTypesIntegration:
    """Integration tests combining complex types with other SpecCache features"""

    def setup_method(self):
        """Setup for each test method"""
        self.mock_spec = MockSpecWithComplexTypes()
        self.cache = SpecCache(self.mock_spec)

    def test_multiple_functions_with_complex_types(self):
        """Test caching multiple functions that use complex types"""
        fn_names = [
            "process_complex_sequence",
            "process_nested_structures",
            "process_deeply_nested",
        ]
        self.cache.register_function_list(fn_names)

        # Create test data
        complex_objects = [ComplexTestClass(1, "test", [1, 2], {"key": "value"})]
        nested_objects = [NestedComplexClass({"meta": "data"}, [1, 2, 3], {1, 2})]
        metadata = {"config": {"setting": True}}
        nested_structure = {"data": complex_objects, "meta": metadata}

        # Call all functions
        result1 = self.mock_spec.process_complex_sequence(complex_objects)
        result2 = self.mock_spec.process_nested_structures(
            complex_objects[0], nested_objects, metadata
        )
        result3 = self.mock_spec.process_deeply_nested(nested_structure)

        assert self.mock_spec.call_count == 3

        # Call again - all should hit cache
        result1_cached = self.mock_spec.process_complex_sequence(complex_objects)
        result2_cached = self.mock_spec.process_nested_structures(
            complex_objects[0], nested_objects, metadata
        )
        result3_cached = self.mock_spec.process_deeply_nested(nested_structure)

        assert self.mock_spec.call_count == 3  # Should not increment
        assert result1 == result1_cached
        assert result2 == result2_cached
        assert result3 == result3_cached

    def test_complex_types_with_function_deregistration(self):
        """Test that complex type caching works correctly with function deregistration"""
        fn_name = "process_complex_sequence"

        # Register and use cache
        self.cache.register_function(fn_name)
        complex_objects = [ComplexTestClass(1, "test", [1], {"k": "v"})]

        result1 = self.mock_spec.process_complex_sequence(complex_objects)
        result2 = self.mock_spec.process_complex_sequence(complex_objects)  # Should hit cache
        assert self.mock_spec.call_count == 1
        assert result1 == result2  # Results should be the same

        # Deregister function
        self.cache.deregister_function(fn_name)

        # Call again - should not use cache
        result3 = self.mock_spec.process_complex_sequence(complex_objects)
        assert self.mock_spec.call_count == 2  # Should increment
        assert result1 == result3  # Results should still be the same


class TestSpecCacheWithoutEqRepr:
    """Test cases specifically for classes without __eq__ and __repr__"""

    def setup_method(self):
        """Setup for each test method"""
        self.mock_spec = MockSpecWithComplexTypes()
        self.cache = SpecCache(self.mock_spec)

    def test_cache_with_identical_objects_without_eq(self):
        """Test that objects with identical content are cached together even without __eq__"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        # Create two objects with identical content but different identity
        obj1 = ComplexTestClass(1, "test", [1, 2], {"key": "value"})
        obj2 = ComplexTestClass(1, "test", [1, 2], {"key": "value"})

        # They should be different objects (no __eq__ method)
        assert obj1 is not obj2

        # Call with first object
        result1 = self.mock_spec.process_complex_sequence([obj1])
        assert self.mock_spec.call_count == 1

        # Call with second object (identical content, different identity) - should be cache HIT
        # because SpecCache uses object content (__dict__) for hashing, not identity
        result2 = self.mock_spec.process_complex_sequence([obj2])
        assert self.mock_spec.call_count == 1  # Should NOT increment - cache hit

        # Results should be the same because content is identical
        assert result1["total_id"] == result2["total_id"]
        assert result1["total_values"] == result2["total_values"]

    def test_cache_with_same_object_instance_without_eq(self):
        """Test that the same object instance still hits cache without __eq__"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        # Create one object
        obj1 = ComplexTestClass(1, "test", [1, 2], {"key": "value"})

        # Call with same object instance twice
        result1 = self.mock_spec.process_complex_sequence([obj1])
        assert self.mock_spec.call_count == 1

        result2 = self.mock_spec.process_complex_sequence([obj1])  # Same instance
        assert self.mock_spec.call_count == 1  # Should not increment - cache hit

        assert result1 == result2

    def test_cache_with_nested_objects_without_eq(self):
        """Test caching with nested objects that don't have __eq__"""
        fn_name = "process_nested_structures"
        self.cache.register_function(fn_name)

        primary = ComplexTestClass(1, "primary", [1], {"type": "main"})
        nested1 = NestedComplexClass({"v": "1.0"}, [1, 2], {10, 20})
        nested2 = NestedComplexClass({"v": "2.0"}, [3, 4], {30, 40})
        metadata = {"session": "test123"}

        # First call
        result1 = self.mock_spec.process_nested_structures(primary, [nested1, nested2], metadata)
        assert self.mock_spec.call_count == 1

        # Second call with same object instances - should hit cache
        result2 = self.mock_spec.process_nested_structures(primary, [nested1, nested2], metadata)
        assert self.mock_spec.call_count == 1  # Should not increment
        assert result1 == result2

        # Third call with new objects with same content - should also be cache HIT
        # because SpecCache uses object content (__dict__) for hashing
        primary_new = ComplexTestClass(1, "primary", [1], {"type": "main"})
        nested1_new = NestedComplexClass({"v": "1.0"}, [1, 2], {10, 20})
        nested2_new = NestedComplexClass({"v": "2.0"}, [3, 4], {30, 40})

        result3 = self.mock_spec.process_nested_structures(
            primary_new, [nested1_new, nested2_new], metadata
        )
        assert self.mock_spec.call_count == 1  # Should NOT increment - cache hit

        # Results should be the same because content is identical
        assert result1["primary_id"] == result3["primary_id"]
        assert result1["secondary_count"] == result3["secondary_count"]

    def test_cache_statistics_with_objects_without_eq(self):
        """Test that cache statistics work correctly with objects without __eq__"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        # Create multiple objects with different identities
        obj1 = ComplexTestClass(1, "obj1", [1], {"type": "A"})
        obj2 = ComplexTestClass(2, "obj2", [2], {"type": "B"})
        obj3 = ComplexTestClass(
            1, "obj1", [1], {"type": "A"}
        )  # Same content as obj1, different identity

        # Generate cache interactions
        self.mock_spec.process_complex_sequence([obj1])  # miss
        self.mock_spec.process_complex_sequence([obj1])  # hit (same instance)
        self.mock_spec.process_complex_sequence([obj2])  # miss (different content)
        self.mock_spec.process_complex_sequence(
            [obj3]
        )  # hit (same content as obj1, even though different identity)
        self.mock_spec.process_complex_sequence([obj1])  # hit (same instance as first)

        # Check statistics
        stats = self.cache.stats.get_stats(fn_name)
        assert stats["hits"] == 3  # obj1 (2nd call), obj3 (same content as obj1), obj1 (5th call)
        assert stats["misses"] == 2  # obj1 (1st call), obj2 (different content)
        assert stats["hit_rate"] == 0.6  # 3 hits out of 5 total calls

    def test_object_mutation_detection_without_eq(self):
        """Test that object mutations are detected even without __eq__"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        obj = ComplexTestClass(1, "test", [1, 2], {"key": "value"})

        # First call
        result1 = self.mock_spec.process_complex_sequence([obj])
        assert self.mock_spec.call_count == 1

        # Second call with same object - should hit cache
        result2 = self.mock_spec.process_complex_sequence([obj])
        assert self.mock_spec.call_count == 1
        assert result1 == result2

        # Mutate the object
        obj.values.append(3)

        # Third call with mutated object - should be cache miss
        result3 = self.mock_spec.process_complex_sequence([obj])
        assert self.mock_spec.call_count == 2  # Should increment

        # Results should be different because object was mutated
        assert result1["total_values"] != result3["total_values"]

    def test_deeply_nested_without_eq_repr(self):
        """Test deeply nested structures with objects that don't have __eq__ or __repr__"""
        fn_name = "process_deeply_nested"
        self.cache.register_function(fn_name)

        obj1 = ComplexTestClass(1, "obj1", [1, 2], {"nested": {"deep": "value"}})
        obj2 = NestedComplexClass({"meta": "data"}, [obj1], {100, 200})

        complex_structure = {
            "level1": [obj1, obj2],
            "level2": {"nested_obj": obj1, "list_with_objs": [obj1, obj2]},
            "level3": [{"embedded": obj2}],
        }

        # First call
        result1 = self.mock_spec.process_deeply_nested(complex_structure)
        assert self.mock_spec.call_count == 1

        # Second call with same structure - should hit cache
        result2 = self.mock_spec.process_deeply_nested(complex_structure)
        assert self.mock_spec.call_count == 1  # Should not increment
        assert result1 == result2

        # Create new structure with different object instances but same content
        obj1_new = ComplexTestClass(1, "obj1", [1, 2], {"nested": {"deep": "value"}})
        obj2_new = NestedComplexClass({"meta": "data"}, [obj1_new], {100, 200})

        complex_structure_new = {
            "level1": [obj1_new, obj2_new],
            "level2": {"nested_obj": obj1_new, "list_with_objs": [obj1_new, obj2_new]},
            "level3": [{"embedded": obj2_new}],
        }

        # Third call with new structure - should also be cache HIT because content is identical
        result3 = self.mock_spec.process_deeply_nested(complex_structure_new)
        assert self.mock_spec.call_count == 1  # Should NOT increment - cache hit

        # Results should be the same because structure content is identical
        assert result1["type"] == result3["type"]
        assert result1["keys_count"] == result3["keys_count"]

    def test_objects_with_different_content_not_cached_without_eq(self):
        """Test that objects with different content are NOT cached together even without __eq__"""
        fn_name = "process_complex_sequence"
        self.cache.register_function(fn_name)

        # Create two objects with different content
        obj1 = ComplexTestClass(1, "test1", [1, 2], {"key": "value1"})
        obj2 = ComplexTestClass(
            2, "test2", [3, 4, 5], {"key": "value2"}
        )  # Different number of values

        # Call with first object
        result1 = self.mock_spec.process_complex_sequence([obj1])
        assert self.mock_spec.call_count == 1

        # Call with second object (different content) - should be cache miss
        result2 = self.mock_spec.process_complex_sequence([obj2])
        assert self.mock_spec.call_count == 2  # Should increment because content is different

        # Results should be different because content is different
        assert result1["total_id"] != result2["total_id"]  # 1 vs 2
        assert result1["total_values"] != result2["total_values"]  # 2 vs 3


class MockSpecForDecorator:
    """Mock spec object for testing the spec_cache decorator"""

    def __init__(self, fork="test_fork", config="test_config"):
        self.fork = fork
        self.config = config
        self.cache_function_call_count = 0
        self.cache_function2_call_count = 0
        self.another_function_call_count = 0

    def cache_function(self, x, y):
        """Function to be cached"""
        self.cache_function_call_count += 1
        return x * y + 1

    def cache_function2(self, x, y):
        """Second function to be cached"""
        self.cache_function2_call_count += 1
        return x * y + y

    def another_function(self, a):
        """Another function to be cached"""
        self.another_function_call_count += 1
        return a * 2


class TestSpecCacheDecorator:
    """Test cases for the spec_cache decorator function"""

    def setup_method(self):
        """Setup for each test method"""
        # Clear global caches before each test
        CACHES.clear()

        # Reset DISABLED_CACHE to default
        cache_module.DISABLED_CACHE = False

    def test_spec_cache_decorator_with_single_function_string(self):
        """Test spec_cache decorator with a single function name as string"""

        @spec_cache("cache_function")
        def test_function(x, y, spec=None):
            return spec.cache_function(x, y)

        mock_spec = MockSpecForDecorator()

        # First call - should cache the function
        result1 = test_function(1, 2, spec=mock_spec)
        assert result1 == 3
        assert mock_spec.cache_function_call_count == 1

        # Second call with same args - should use cache
        result2 = test_function(1, 2, spec=mock_spec)
        assert result2 == 3
        assert mock_spec.cache_function_call_count == 1  # Should not increment

    def test_spec_cache_decorator_with_function_list(self):
        """Test spec_cache decorator with a list of function names"""

        @spec_cache(["cache_function", "another_function"])
        def test_function(x, y, a, spec=None):
            result1 = spec.cache_function(x, y)
            result2 = spec.another_function(a)
            return result1 + result2

        mock_spec = MockSpecForDecorator()

        # First call
        result1 = test_function(1, 2, 5, spec=mock_spec)
        assert result1 == 13  # (1+2) + (5*2) = 13
        assert mock_spec.cache_function_call_count == 1
        assert mock_spec.another_function_call_count == 1

        # Second call with same args - should use cache for both functions
        result2 = test_function(1, 2, 5, spec=mock_spec)
        assert result2 == 13
        assert mock_spec.cache_function_call_count == 1  # Should not increment
        assert mock_spec.another_function_call_count == 1  # Should not increment

    def test_spec_cache_decorator_disabled_cache(self):
        """Test spec_cache decorator when caching is disabled"""
        cache_module.DISABLED_CACHE = True

        @cache_module.spec_cache("cache_function")
        def test_function(x, y, spec=None):
            return spec.cache_function(x, y)

        mock_spec = MockSpecForDecorator()

        # When cache is disabled, the original function should be returned
        result1 = test_function(1, 2, spec=mock_spec)
        result2 = test_function(1, 2, spec=mock_spec)

        assert result1 == 3
        assert result2 == 3
        # Both calls should hit the original function since caching is disabled
        assert mock_spec.cache_function_call_count == 2

    def test_spec_cache_decorator_no_spec_parameter(self):
        """Test spec_cache decorator raises error when spec parameter is None"""

        @spec_cache("cache_function")
        def test_function(x, y, spec=None):
            return spec.cache_function(x, y)

        with pytest.raises(
            ValueError,
            match="Decorator 'spec_cache' requires a previous decorator that adds a spec",
        ):
            test_function(1, 2, spec=None)

    def test_spec_cache_decorator_with_generator_function(self):
        """Test spec_cache decorator with a function that returns a generator"""

        @spec_cache("cache_function")
        def test_generator_function(count, spec=None):
            for i in range(count):
                yield spec.cache_function(i, 1)

        mock_spec = MockSpecForDecorator()

        # Call generator function
        results = list(test_generator_function(3, spec=mock_spec))

        assert results == [1, 2, 3]  # 0*1+1, 1*1+1, 2*1+1
        # The cache_function should be called for each iteration that's not cached
        assert mock_spec.cache_function_call_count == 3

        # Call again - should use cached values
        results2 = list(test_generator_function(3, spec=mock_spec))
        assert results2 == [1, 2, 3]
        # Should not increment because values are cached
        assert mock_spec.cache_function_call_count == 3

    def test_spec_cache_decorator_generator_with_different_args(self):
        """Test generator functions with different argument patterns"""

        @spec_cache("cache_function")
        def test_generator_with_args(start, end, multiplier=2, spec=None):
            for i in range(start, end):
                yield spec.cache_function(i, multiplier)

        mock_spec = MockSpecForDecorator()

        # Test with different argument combinations
        results1 = list(test_generator_with_args(1, 4, spec=mock_spec))
        assert results1 == [3, 5, 7]  # 1*2+1, 2*2+1, 3*2+1

        results2 = list(test_generator_with_args(2, 5, multiplier=3, spec=mock_spec))
        assert results2 == [7, 10, 13]  # 2*3+1, 3*3+1, 4*3+1

        # Verify cache statistics
        spec_key = hash((mock_spec.fork, mock_spec.config))
        cache_obj = CACHES[spec_key]
        stats = cache_obj.get_stats().get_stats("cache_function")
        assert stats["misses"] == 6  # All unique calls

    def test_spec_cache_decorator_generator_multiple_functions(self):
        """Test generator using multiple cached functions"""

        @spec_cache(["cache_function", "cache_function2"])
        def test_generator_multi_functions(values, spec=None):
            for value in values:
                result1 = spec.cache_function(value, 10)
                result2 = spec.cache_function2(value, 20)
                yield {"sum": result1 + result2, "diff": result2 - result1}

        mock_spec = MockSpecForDecorator()

        results = list(test_generator_multi_functions([1, 2], spec=mock_spec))
        expected = [
            {"sum": 1 * 10 + 1 + 1 * 20 + 20, "diff": (1 * 20 + 20) - (1 * 10 + 1)},
            {"sum": 2 * 10 + 1 + 2 * 20 + 20, "diff": (2 * 20 + 20) - (2 * 10 + 1)},
        ]
        assert results == expected

        # Check both functions are cached
        spec_key = hash((mock_spec.fork, mock_spec.config))
        cache_obj = CACHES[spec_key]
        stats1 = cache_obj.get_stats().get_stats("cache_function")
        stats2 = cache_obj.get_stats().get_stats("cache_function2")
        assert stats1["misses"] == 2
        assert stats2["misses"] == 2

    def test_spec_cache_decorator_generator_early_termination(self):
        """Test generator with early termination (break/return)"""

        @spec_cache("cache_function")
        def test_generator_early_exit(values, stop_at, spec=None):
            for value in values:
                result = spec.cache_function(value, 1)
                yield result
                if value == stop_at:
                    return  # Early termination

        mock_spec = MockSpecForDecorator()

        # Generator that terminates early
        results = list(test_generator_early_exit([1, 2, 3, 4, 5], 3, spec=mock_spec))
        assert results == [2, 3, 4]  # Only processes up to value 3: 1*1+1, 2*1+1, 3*1+1

        # Function should still be deregistered after early termination
        spec_key = hash((mock_spec.fork, mock_spec.config))
        cache_obj = CACHES[spec_key]
        assert "cache_function" not in cache_obj.original_fns

        # Verify cache statistics
        stats = cache_obj.get_stats().get_stats("cache_function")
        assert stats["misses"] == 3  # Only 3 calls before early exit

    def test_spec_cache_decorator_generator_with_exceptions(self):
        """Test generator that raises exceptions during iteration"""

        @spec_cache("cache_function")
        def test_generator_with_exception(values, spec=None):
            for value in values:
                if value == 999:
                    raise ValueError("Test exception")
                yield spec.cache_function(value, 1)

        mock_spec = MockSpecForDecorator()

        # Normal operation first
        results = list(test_generator_with_exception([1, 2], spec=mock_spec))
        assert results == [2, 3]  # 1*1+1, 2*1+1

        # Test exception handling
        with pytest.raises(ValueError, match="Test exception"):
            list(test_generator_with_exception([1, 999, 3], spec=mock_spec))

        # Function should be deregistered even after exception
        spec_key = hash((mock_spec.fork, mock_spec.config))
        cache_obj = CACHES[spec_key]
        assert "cache_function" not in cache_obj.original_fns.keys()

        # Cache should still record the calls made before exception
        stats = cache_obj.get_stats().get_stats("cache_function")
        assert stats["hits"] >= 1  # At least one hit from the repeated value 1

    def test_spec_cache_decorator_generator_complex_yielded_objects(self):
        """Test generator yielding complex objects"""

        @spec_cache("cache_function")
        def test_generator_complex_objects(data_list, spec=None):
            for data in data_list:
                cached_result = spec.cache_function(data["key"], data["multiplier"])
                yield {
                    "input": data,
                    "cached_result": cached_result,
                    "processed": cached_result * 2,
                    "metadata": {"timestamp": data.get("timestamp", "unknown")},
                }

        mock_spec = MockSpecForDecorator()

        test_data = [
            {"key": 1, "multiplier": 5, "timestamp": "2023-01-01"},
            {"key": 2, "multiplier": 3, "timestamp": "2023-01-02"},
            {"key": 1, "multiplier": 5},  # Same as first, should hit cache
        ]

        results = list(test_generator_complex_objects(test_data, spec=mock_spec))

        # Verify structure and content
        assert len(results) == 3
        assert results[0]["input"] == test_data[0]
        assert results[0]["cached_result"] == 6  # 1 * 5 + 1
        assert results[0]["processed"] == 12  # 6 * 2
        assert results[0]["metadata"]["timestamp"] == "2023-01-01"

        assert results[2]["cached_result"] == 6  # Same as first due to caching
        assert results[2]["metadata"]["timestamp"] == "unknown"

        # Verify cache behavior
        spec_key = hash((mock_spec.fork, mock_spec.config))
        cache_obj = CACHES[spec_key]
        stats = cache_obj.get_stats().get_stats("cache_function")
        assert stats["misses"] == 2  # Only 2 unique cache calls
        assert stats["hits"] == 1  # Third call was a hit

    def test_spec_cache_decorator_generator_nested_iteration(self):
        """Test generator with nested iteration patterns"""

        @spec_cache("cache_function")
        def test_nested_generator(matrix, spec=None):
            for row in matrix:
                row_results = []
                for value in row:
                    row_results.append(spec.cache_function(value, 2))
                yield row_results

        mock_spec = MockSpecForDecorator()

        test_matrix = [
            [1, 2, 3],
            [2, 3, 4],  # 2 and 3 should be cache hits
            [1, 4, 5],  # 1 should be cache hit
        ]

        results = list(test_nested_generator(test_matrix, spec=mock_spec))
        expected = [
            [3, 5, 7],  # [1*2+1, 2*2+1, 3*2+1]
            [5, 7, 9],  # [2*2+1, 3*2+1, 4*2+1] (first two cached)
            [3, 9, 11],  # [1*2+1, 4*2+1, 5*2+1] (first one cached)
        ]
        assert results == expected

        # Verify cache efficiency
        spec_key = hash((mock_spec.fork, mock_spec.config))
        cache_obj = CACHES[spec_key]
        stats = cache_obj.get_stats().get_stats("cache_function")
        assert stats["misses"] == 5  # Unique values: 1, 2, 3, 4, 5
        assert stats["hits"] == 4  # Repeated values: 2, 3, 1, 4

    def test_spec_cache_decorator_generator_with_send_and_throw(self):
        """Test generator with send() and throw() methods"""

        @spec_cache("cache_function")
        def test_advanced_generator(spec=None):
            value = 1
            while True:
                result = spec.cache_function(value, 10)
                sent_value = yield result
                if sent_value is not None:
                    value = sent_value
                else:
                    value += 1

        mock_spec = MockSpecForDecorator()

        gen = test_advanced_generator(spec=mock_spec)

        # Initial call
        result1 = next(gen)
        assert result1 == 11  # 1 * 10 + 1

        # Send a value
        result2 = gen.send(5)
        assert result2 == 51  # 5 * 10 + 1

        # Normal iteration
        result3 = next(gen)
        assert result3 == 61  # 6 * 10 + 1 (5 + 1)

        # Test throw
        with pytest.raises(ValueError):
            gen.throw(ValueError, "Test exception")

        # Function should be deregistered after exception
        spec_key = hash((mock_spec.fork, mock_spec.config))
        cache_obj = CACHES[spec_key]
        assert "cache_function" not in cache_obj.original_fns

    def test_spec_cache_decorator_generator_concurrent_access(self):
        """Test generator behavior with concurrent cache access patterns"""

        @spec_cache("cache_function")
        def test_generator_a(values, spec=None):
            for value in values:
                yield f"A:{spec.cache_function(value, 1)}"

        @spec_cache("cache_function")
        def test_generator_b(values, spec=None):
            for value in values:
                yield f"B:{spec.cache_function(value, 2)}"

        mock_spec = MockSpecForDecorator()

        # Interleave generator calls
        gen_a = test_generator_a([1, 2, 3], spec=mock_spec)
        gen_b = test_generator_b([2, 3, 4], spec=mock_spec)

        # In current implementation, we need to completely consume one generator before the other.
        next(gen_a)
        with pytest.raises(ValueError, match="Function 'cache_function' is already cached."):
            next(gen_b)


class TestGlobalCacheManagement:
    """Test cases for global cache management functionality"""

    def setup_method(self):
        """Setup for each test method"""
        # Clear global caches before each test
        CACHES.clear()
        # Reset DISABLED_CACHE to default
        cache_module.DISABLED_CACHE = False

    def teardown_method(self):
        """Cleanup after each test method"""
        # Reset to default state
        cache_module.DISABLED_CACHE = False
        CACHES.clear()

    def test_disabled_cache_global_flag(self):
        """Test global DISABLED_CACHE flag behavior with decorator"""

        # Test with cache enabled (default)
        @spec_cache("test_function")
        def test_with_cache_enabled(x, y, spec=None):
            return spec.test_function(x, y)

        mock_spec1 = MockSpec()
        result1 = test_with_cache_enabled(1, 2, spec=mock_spec1)
        result2 = test_with_cache_enabled(1, 2, spec=mock_spec1)
        assert mock_spec1.call_count == 1  # Should hit cache
        assert result1 == result2 == 3

        # Disable cache globally
        cache_module.DISABLED_CACHE = True

        # Test with cache disabled
        @spec_cache("test_function")
        def test_with_cache_disabled(x, y, spec=None):
            return spec.test_function(x, y)

        mock_spec2 = MockSpec()
        result3 = test_with_cache_disabled(1, 2, spec=mock_spec2)
        result4 = test_with_cache_disabled(1, 2, spec=mock_spec2)
        assert mock_spec2.call_count == 2  # Should not hit cache
        assert result3 == result4 == 3

    def test_disabled_cache_decorator_bypass(self):
        """Test that spec_cache decorator bypasses when DISABLED_CACHE is True"""
        cache_module.DISABLED_CACHE = True

        @spec_cache("test_function")
        def test_function(x, y, spec=None):
            return spec.test_function(x, y)

        mock_spec = MockSpec()

        # Both calls should hit the original function
        result1 = test_function(1, 2, spec=mock_spec)
        result2 = test_function(1, 2, spec=mock_spec)

        assert result1 == 3
        assert result2 == 3
        assert mock_spec.call_count == 2  # Both calls should execute

    def test_caches_dictionary_management(self):
        """Test global CACHES dictionary management"""
        mock_spec1 = MockSpec()
        mock_spec1.fork = "fork1"
        mock_spec1.config = "config1"

        mock_spec2 = MockSpec()
        mock_spec2.fork = "fork2"
        mock_spec2.config = "config2"

        # Initially empty
        assert len(CACHES) == 0

        # Create first cache
        cache1 = SpecCache(mock_spec1)
        spec_key1 = hash((mock_spec1.fork, mock_spec1.config))
        CACHES[spec_key1] = cache1

        assert len(CACHES) == 1
        assert spec_key1 in CACHES

        # Create second cache
        cache2 = SpecCache(mock_spec2)
        spec_key2 = hash((mock_spec2.fork, mock_spec2.config))
        CACHES[spec_key2] = cache2

        assert len(CACHES) == 2
        assert spec_key2 in CACHES

        # Verify different caches
        assert CACHES[spec_key1] is cache1
        assert CACHES[spec_key2] is cache2
        assert cache1 is not cache2

    def test_cache_isolation_between_different_specs(self):
        """Test that caches are isolated between different spec configurations"""
        mock_spec1 = MockSpec()
        mock_spec1.fork = "fork1"
        mock_spec1.config = "config1"

        mock_spec2 = MockSpec()
        mock_spec2.fork = "fork2"
        mock_spec2.config = "config2"

        @spec_cache("test_function")
        def test_function(x, y, spec=None):
            return spec.test_function(x, y)

        # Call with first spec
        result1 = test_function(1, 2, spec=mock_spec1)
        assert result1 == 3
        assert mock_spec1.call_count == 1

        # Call with second spec (different key)
        result2 = test_function(1, 2, spec=mock_spec2)
        assert result2 == 3
        assert mock_spec2.call_count == 1

        # Both specs should have separate caches
        spec_key1 = hash((mock_spec1.fork, mock_spec1.config))
        spec_key2 = hash((mock_spec2.fork, mock_spec2.config))

        assert len(CACHES) == 2
        assert spec_key1 in CACHES
        assert spec_key2 in CACHES
        assert CACHES[spec_key1] is not CACHES[spec_key2]


class TestErrorHandlingAndEdgeCases:
    """Test cases for error handling and edge case scenarios"""

    def setup_method(self):
        """Setup for each test method"""
        CACHES.clear()
        cache_module.DISABLED_CACHE = False

    def test_function_call_after_deregistration(self):
        """Test that function works correctly after deregistration"""
        mock_spec = MockSpec()
        cache = SpecCache(mock_spec)

        # Register and use function
        cache.register_function("test_function")
        result1 = mock_spec.test_function(1, 2)
        assert result1 == 3
        assert mock_spec.call_count == 1

        # Deregister function
        cache.deregister_function("test_function")

        # Function should still work but not use cache
        result2 = mock_spec.test_function(1, 2)
        assert result2 == 3
        assert mock_spec.call_count == 2  # Should increment

        # Third call should also not use cache
        result3 = mock_spec.test_function(1, 2)
        assert result3 == 3
        assert mock_spec.call_count == 3  # Should increment again

    def test_cache_key_generation_with_none_values(self):
        """Test cache key generation with None values"""
        mock_spec = MockSpec()
        cache = SpecCache(mock_spec)

        cache.register_function("test_function")

        # Test with None arguments
        mock_spec.test_function(None, None)
        mock_spec.test_function(None, None)

        # Should cache properly even with None values
        assert mock_spec.call_count == 1  # Second call should be cached

    def test_cache_with_extremely_large_objects(self):
        """Test cache behavior with very large objects"""
        mock_spec = MockSpecWithComplexTypes()
        cache = SpecCache(mock_spec)

        # Create a large object
        large_obj = ComplexTestClass(
            id=1,
            name="large_object",
            values=list(range(1000)),  # Large list
            nested_data={"large_dict": {f"key_{i}": f"value_{i}" for i in range(100)}},
        )

        cache.register_function("process_complex_sequence")

        # Should handle large objects without issues
        result1 = mock_spec.process_complex_sequence([large_obj])
        result2 = mock_spec.process_complex_sequence([large_obj])

        assert mock_spec.call_count == 1  # Should cache even large objects
        assert result1 == result2

    def test_function_with_side_effects_caching(self):
        """Test caching behavior with functions that have side effects"""

        class MockSpecWithSideEffects:
            def __init__(self):
                self.call_count = 0
                self.side_effect_value = 0

            def function_with_side_effects(self, x):
                self.call_count += 1
                self.side_effect_value += x  # Side effect
                return x * 2

        mock_spec = MockSpecWithSideEffects()
        cache = SpecCache(mock_spec)
        cache.register_function("function_with_side_effects")

        # First call
        result1 = mock_spec.function_with_side_effects(5)
        assert result1 == 10
        assert mock_spec.call_count == 1
        assert mock_spec.side_effect_value == 5

        # Second call with same args - should use cache
        result2 = mock_spec.function_with_side_effects(5)
        assert result2 == 10
        assert mock_spec.call_count == 1  # Should not increment
        assert mock_spec.side_effect_value == 5  # Side effect should not occur again

    def test_decorator_with_missing_spec_attribute(self):
        """Test decorator behavior when spec object is missing required attributes"""

        @spec_cache("test_function")
        def test_function(x, y, spec=None):
            return spec.test_function(x, y)

        # Spec object without required attributes
        class IncompleteSpec:
            def test_function(self, x, y):
                return x + y

        incomplete_spec = IncompleteSpec()

        # Should raise AttributeError when trying to create spec key
        with pytest.raises(AttributeError):
            test_function(1, 2, spec=incomplete_spec)
