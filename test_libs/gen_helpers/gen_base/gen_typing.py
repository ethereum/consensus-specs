from typing import Callable, Dict, Any

TestCase = Dict[str, Any]
TestSuite = Dict[str, Any]
# Args: <presets path>
TestSuiteCreator = Callable[[str], TestSuite]
