# This is a "hack" which allows other test files (e.g., test_deposit_transition.py)
# to reuse the sanity/block test format.
from .test_blocks import *  # noqa: F401 F403
from .test_deposit_transition import *  # noqa: F401 F403
