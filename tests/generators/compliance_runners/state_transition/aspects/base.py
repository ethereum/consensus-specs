from enum import auto, Enum


class Cmp(Enum):
    LT = auto()
    EQ = auto()
    GT = auto()


class OpCmp(Enum):
    LT = auto()
    EQ = auto()
    GT = auto()
    NA = auto()


class Bool(Enum):
    F = auto()
    T = auto()


class OpBool(Enum):
    F = auto()
    T = auto()
    NA = auto()


class BuilderType(Enum):
    EXTERNAL = auto()
    SELF = auto()


class SignatureType(Enum):
    INF = auto()
    VALID = auto()
    INVALID = auto()


class ValidatorCredentialKind(Enum):
    BLS = auto()
    ETH1 = auto()
    COMPOUNDING = auto()


class Record:
    """
    Record is a Record in Minizinc.
    """


def predicate(fn):
    """
    Marks `fn` as should be a Minizinc predicate.
    """
    return fn


def constraint(fn):
    """
    Marks `fn` as should be a Minizinc constraint.
    Specifically, `fn` body should be broken down into a set of constraints, where:
    - ```if expression_a:
        assert expression_b
        assert expression_c
        assert expression_d``` is:
        ```constraint expression_a -> expression_b
        constraint expression_a -> expression_c
        constraint expression_a -> expression_d```
    - `assert expression_a == expression_b` is `constraint expression_a <-> expression_b`
    - ```if expression:
            return``` implies that constraints defined below this statement are not applicable
        if `expression` satisfied.
    - if constraint function is called inside of `fn` body apply constraints defined by that function to its parameter
    - if constraint function has an assert on the length of the list from the Record,
      this list must be translated to a minizinc array with the corresponding length constraints,
      if there is no upper boundary constraint then use 0 as the placeholder,
      note that upper bound constraint can come from some other place when the Record is imported into some other place.
    - asserts in a loop should be applied to items of the corresponding minizinc array
    - `fn` may have parameters like `int` arguments constraining a size of an array,
      this parameters should be replaced with array lengths in Minizinc models.
    """
    return fn


def validator(fn):
    """
    Validates materialization of a minizinc model solution.
    `fn` can accept the following arguments:
    - `spec` is an instance of consensus specification,
    - `beacon_state` is an instance of the BeaconState with materialized solution,
    - `solution` is the minizinc model solution that is used by materializer,
    - other arguments specific to the model that should be read from the `fn` definition.
    `fn` returns True if a materialized instance matches the `solution`, otherwise, it returns False.
    """
    return fn


def no_more_than_several_of(predicates: list[bool], count: int) -> None:
    """
    Accepts a list of `predicates` and outlines constraints
    in a way that either all predicates are false
    or only `count` of them can be true at the same time.
    """


def _to_op_bool(value: bool) -> OpBool:
    if value:
        return OpBool.T
    else:
        return OpBool.F


def _to_bool(value: bool) -> Bool:
    if value:
        return Bool.T
    else:
        return Bool.F


def _to_op_cmp(v1: int, v2: int) -> OpCmp:
    if v1 > v2:
        return OpCmp.GT
    elif v1 < v2:
        return OpCmp.LT
    else:
        return OpCmp.EQ


def _to_cmp(v1: int, v2: int) -> Cmp:
    if v1 > v2:
        return Cmp.GT
    elif v1 < v2:
        return Cmp.LT
    else:
        return Cmp.EQ
