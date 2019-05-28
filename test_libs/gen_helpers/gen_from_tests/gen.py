from inspect import getmembers, isfunction

def generate_from_tests(src, bls_active=True):
    """
    Generate a list of test cases by running tests from the given src in generator-mode.
    :param src: to retrieve tests from (discovered using inspect.getmembers)
    :param bls_active: optional, to override BLS switch preference. Defaults to True.
    :return: the list of test cases.
    """
    fn_names = [
        name for (name, _) in getmembers(src, isfunction)
        if name.startswith('test_')
    ]
    out = []
    print("generating test vectors from tests source: %s" % src.__name__)
    for name in fn_names:
        tfn = getattr(src, name)
        try:
            test_case = tfn(generator_mode=True, bls_active=bls_active)
            # If no test case data is returned, the test is ignored.
            if test_case is not None:
                out.append(test_case)
        except AssertionError:
            print("ERROR: failed to generate vector from test: %s (src: %s)" % (name, src.__name__))
    return out
