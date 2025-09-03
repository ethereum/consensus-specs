import pytest
from tests.infra.generator import only_generator


@only_generator
def sample_function(x, y, generator_mode=False):
    return x + y


@only_generator
def function_with_kwargs(a, b=10, generator_mode=False):
    return a * b


@only_generator
def function_with_args_and_kwargs(*args, **kwargs):
    return sum(args) + sum(kwargs.values())


class TestOnlyGeneratorDecorator:
    
    def test_function_called_when_generator_mode_true(self):
        result = sample_function(5, 3, generator_mode=True)
        assert result == 8
    
    def test_function_not_called_when_generator_mode_false(self):
        result = sample_function(5, 3, generator_mode=False)
        assert result is None
    
    def test_function_not_called_when_generator_mode_missing(self):
        result = sample_function(5, 3)
        assert result is None
    
    def test_function_with_default_kwargs_generator_mode_true(self):
        result = function_with_kwargs(5, generator_mode=True)
        assert result == 50
    
    def test_function_with_custom_kwargs_generator_mode_true(self):
        result = function_with_kwargs(3, b=7, generator_mode=True)
        assert result == 21
    
    def test_function_with_custom_kwargs_generator_mode_false(self):
        result = function_with_kwargs(3, b=7, generator_mode=False)
        assert result is None
    
    def test_function_with_args_and_kwargs_generator_mode_true(self):
        result = function_with_args_and_kwargs(1, 2, 3, x=4, y=5, generator_mode=True)
        assert result == 16  # sum(1,2,3) + sum(4,5,1) = 6 + 10 = 16 (generator_mode=True adds 1)
    
    def test_function_with_args_and_kwargs_generator_mode_false(self):
        result = function_with_args_and_kwargs(1, 2, 3, x=4, y=5, generator_mode=False)
        assert result is None
    
    def test_function_preserves_function_name(self):
        assert sample_function.__name__ == 'sample_function'
    
    def test_function_preserves_docstring(self):
        @only_generator
        def documented_function(generator_mode=False):
            """This is a test function."""
            return "result"
        
        assert documented_function.__doc__ == "This is a test function."