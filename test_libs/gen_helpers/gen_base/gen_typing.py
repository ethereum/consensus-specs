from typing import Callable, Dict, Tuple, Any

TestCase = Dict[str, Any]
TestSuite = Dict[str, Any]
# Tuple: (output name, handler name, suite) -- output name excl. ".yaml"
TestSuiteOutput = Tuple[str, str, TestSuite]
# Args: <presets path>
TestSuiteCreator = Callable[[str], TestSuiteOutput]
