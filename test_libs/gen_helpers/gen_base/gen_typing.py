from typing import Callable, Dict, Any

TestCase = Dict[str, Any]
TestSuite = Dict[str, Any]
TestSuiteCreator = Callable[[], TestSuite]
