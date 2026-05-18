from eth_consensus_specs.test import context

from .yield_generator import _yield_generator_post_processing, vector_test


class TestYieldGeneratorPostProcessing:
    """Tests for _yield_generator_post_processing function."""

    def test_with_none_values(self):
        """Test that None values are skipped."""

        def generator():
            yield ("key1", "value1")
            yield ("key2", None)
            yield ("key3", "value3")

        result = list(_yield_generator_post_processing(generator()))

        assert len(result) == 2
        assert result[0] == ("key1", "data", "value1")
        assert result[1] == ("key3", "data", "value3")

    def test_with_bytes(self):
        """Test that bytes values are tagged as ssz."""

        def generator():
            yield ("key1", b"some bytes")
            yield ("key2", b"more bytes")

        result = list(_yield_generator_post_processing(generator()))

        assert len(result) == 2
        assert result[0] == ("key1", "ssz", b"some bytes")
        assert result[1] == ("key2", "ssz", b"more bytes")

    def test_with_preformatted(self):
        """Test that preformatted 3-tuples are passed through unchanged."""

        def generator():
            yield ("bls_setting", "meta", 1)
            yield ("config", "meta", {"key": "value"})

        result = list(_yield_generator_post_processing(generator()))

        assert len(result) == 2
        assert result[0] == ("bls_setting", "meta", 1)
        assert result[1] == ("config", "meta", {"key": "value"})

    def test_with_data(self):
        """Test that non-SSZ data is tagged as data."""

        def generator():
            yield ("string_key", "some string")
            yield ("int_key", 42)
            yield ("dict_key", {"a": 1, "b": 2})
            yield ("list_key", [1, 2, 3])

        result = list(_yield_generator_post_processing(generator()))

        assert len(result) == 4
        assert result[0] == ("string_key", "data", "some string")
        assert result[1] == ("int_key", "data", 42)
        assert result[2] == ("dict_key", "data", {"a": 1, "b": 2})
        assert result[3] == ("list_key", "data", [1, 2, 3])

    def test_with_bytes_list(self):
        """Test that lists of bytes are handled correctly."""

        def generator():
            yield ("bytes_list", [b"first", b"second", b"third"])

        result = list(_yield_generator_post_processing(generator()))

        assert len(result) == 4
        assert result[0] == ("bytes_list_0", "ssz", b"first")
        assert result[1] == ("bytes_list_1", "ssz", b"second")
        assert result[2] == ("bytes_list_2", "ssz", b"third")
        assert result[3] == ("bytes_list_count", "meta", 3)


class TestVectorTest:
    """Tests for vector_test decorator."""

    def test_with_non_generator_function(self):
        """Test that non-generator functions are returned as-is."""

        def simple_function():
            return "result"

        # Apply the decorator
        decorated = vector_test(simple_function)

        # The function should be returned unchanged
        assert decorated is simple_function
        assert decorated() == "result"

    def test_with_generator_is_pytest_true_is_generator_false(self):
        """Test generator function when is_pytest=True and is_generator=False (drain mode)."""

        call_count = 0

        def generator_function():
            nonlocal call_count
            call_count += 1
            yield ("key1", "value1")
            call_count += 1
            yield ("key2", "value2")
            call_count += 1

        # Temporarily set context
        original_is_pytest = context.is_pytest
        original_is_generator = context.is_generator
        try:
            context.is_pytest = True
            context.is_generator = False

            # Apply the decorator
            decorated = vector_test(generator_function)

            # When is_pytest=True and is_generator=False, it should return a drain wrapper
            # Calling it should drain the generator
            call_count = 0
            result = decorated()

            # Should have iterated through all yields
            assert call_count == 3
            # Should return None (drained)
            assert result is None

        finally:
            context.is_pytest = original_is_pytest
            context.is_generator = original_is_generator

    def test_with_generator_is_pytest_true_is_generator_true(self):
        """Test generator function when is_pytest=True and is_generator=True (new mode)."""

        def generator_function():
            yield ("key1", "value1")
            yield ("key2", "value2")
            yield ("key3", b"bytes_value")

        # Temporarily set context
        original_is_pytest = context.is_pytest
        original_is_generator = context.is_generator
        try:
            context.is_pytest = True
            context.is_generator = True

            # Apply the decorator
            decorated = vector_test(generator_function)

            # When is_generator=True, should return a generator with post-processing
            result = decorated()

            # Should be a generator
            assert hasattr(result, "__iter__")
            assert hasattr(result, "__next__")

            # Collect results
            items = list(result)

            # Should have post-processing applied
            assert len(items) == 3
            assert items[0] == ("key1", "data", "value1")
            assert items[1] == ("key2", "data", "value2")
            assert items[2] == ("key3", "ssz", b"bytes_value")

        finally:
            context.is_pytest = original_is_pytest
            context.is_generator = original_is_generator

    def test_with_generator_is_pytest_true_is_generator_true_post_processing(self):
        """Test post-processing integration when is_pytest=True and is_generator=True."""

        def generator_function():
            yield ("none_key", None)  # Should be skipped
            yield ("string_key", "string_value")
            yield ("bytes_key", b"bytes_value")
            yield ("preformatted", "meta", {"config": "value"})

        original_is_pytest = context.is_pytest
        original_is_generator = context.is_generator
        try:
            context.is_pytest = True
            context.is_generator = True

            decorated = vector_test(generator_function)
            result = decorated()
            items = list(result)

            assert len(items) == 3  # None value should be skipped
            assert items[0] == ("string_key", "data", "string_value")
            assert items[1] == ("bytes_key", "ssz", b"bytes_value")
            assert items[2] == ("preformatted", "meta", {"config": "value"})

        finally:
            context.is_pytest = original_is_pytest
            context.is_generator = original_is_generator

    def test_with_generator_is_pytest_false_is_generator_true(self):
        """Test generator function when is_pytest=False and is_generator=True."""

        def generator_function():
            yield ("key1", "value1")
            yield ("key2", "value2")
            yield ("key3", b"bytes_value")

        # Temporarily set context
        original_is_pytest = context.is_pytest
        original_is_generator = context.is_generator
        try:
            context.is_pytest = False
            context.is_generator = True

            # Apply the decorator
            decorated = vector_test(generator_function)

            # When is_generator=True, should return a generator with post-processing
            result = decorated()

            # Should be a generator
            assert hasattr(result, "__iter__")
            assert hasattr(result, "__next__")

            # Collect results
            items = list(result)

            # Should have post-processing applied
            assert len(items) == 3
            assert items[0] == ("key1", "data", "value1")
            assert items[1] == ("key2", "data", "value2")
            assert items[2] == ("key3", "ssz", b"bytes_value")

        finally:
            context.is_pytest = original_is_pytest
            context.is_generator = original_is_generator

    def test_with_generator_post_processing_integration(self):
        """Test that _yield_generator_post_processing is properly integrated."""

        def generator_function():
            # Mix of different data types
            yield ("none_key", None)  # Should be skipped
            yield (
                "string_key",
                "string_value",
            )  # Should become ("string_key", "data", "string_value")
            yield (
                "bytes_key",
                b"bytes_value",
            )  # Should become ("bytes_key", "ssz", b"bytes_value")
            yield ("preformatted", "meta", {"config": "value"})  # Should pass through unchanged

        # Temporarily set context
        original_is_pytest = context.is_pytest
        original_is_generator = context.is_generator
        try:
            context.is_pytest = False
            context.is_generator = True

            # Apply the decorator
            decorated = vector_test(generator_function)

            result = decorated()
            items = list(result)

            # Verify post-processing was applied correctly
            assert len(items) == 3  # None value should be skipped
            assert items[0] == ("string_key", "data", "string_value")
            assert items[1] == ("bytes_key", "ssz", b"bytes_value")
            assert items[2] == ("preformatted", "meta", {"config": "value"})

        finally:
            context.is_pytest = original_is_pytest
            context.is_generator = original_is_generator

    def test_with_generator_with_args_and_kwargs(self):
        """Test that args and kwargs are properly passed through."""

        received_args = None
        received_kwargs = None

        def generator_function(*args, **kwargs):
            nonlocal received_args, received_kwargs
            received_args = args
            received_kwargs = kwargs
            yield ("key", "value")

        # Temporarily set context
        original_is_pytest = context.is_pytest
        original_is_generator = context.is_generator
        try:
            context.is_pytest = False
            context.is_generator = True

            # Apply the decorator
            decorated = vector_test(generator_function)

            # Call with args and kwargs
            result = decorated("arg1", "arg2", param1="value1", param2="value2")
            list(result)  # consume generator to trigger inner function

            # Verify args and kwargs were passed through
            assert received_args == ("arg1", "arg2")
            assert received_kwargs == {"param1": "value1", "param2": "value2"}

        finally:
            context.is_pytest = original_is_pytest
            context.is_generator = original_is_generator
