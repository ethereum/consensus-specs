
from tests.utils import spectest
from tests.context import with_state


# shorthand for decorating @with_state @spectest()
def spec_state_test(fn):
    return with_state(spectest()(fn))
