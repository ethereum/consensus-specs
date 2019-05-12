from typing import Dict, Any

from .ssz_typing import *

# SSZ Switch statement runner factory
# -----------------------------


def ssz_switch(sw: Dict[Any, Any], arg_names=None):
    """
    Creates an SSZ switch statement: a function, that when executed, checks every switch-statement
    """
    if arg_names is None:
        arg_names = ["value", "typ"]

    # Runner, the function that executes the switch when called.
    # Accepts a arguments based on the arg_names declared in the ssz_switch.
    def run_switch(*args):
        # value may be None
        value = None
        try:
            value = args[arg_names.index("value")]
        except ValueError:
            pass # no value argument

        # typ may be None when value is not None
        typ = None
        try:
            typ = args[arg_names.index("typ")]
        except ValueError:
            # no typ argument expected
            pass
        except IndexError:
            # typ argument expected, but not passed. Try to get it from the class info
            typ = value.__class__
        if hasattr(typ, '__forward_arg__'):
            typ = typ.__forward_arg__

        # Now, go over all switch cases
        for matchers, worker in sw.items():
            if not isinstance(matchers, tuple):
                matchers = (matchers,)
            # for each matcher of the case key
            for m in matchers:
                data = m(typ)
                # if we have data, the matcher matched, and we can return the result
                if data is not None:
                    # Supply value and type by default, and any data presented by the matcher.
                    kwargs = {"value": value, "typ": typ, **data}
                    # Filter out unwanted arguments
                    filtered_kwargs = {k: kwargs[k] for k in worker.__code__.co_varnames}
                    # run the switch case and return result
                    return worker(**filtered_kwargs)
        raise Exception("cannot find matcher for type: %s (value: %s)" % (typ, value))
    return run_switch


def ssz_type_switch(sw: Dict[Any, Any]):
    return ssz_switch(sw, ["typ"])


# SSZ Switch matchers
# -----------------------------

def ssz_bool(typ):
    if typ == bool:
        return {}


def ssz_uint(typ):
    # Note: only the type reference exists,
    #  but it really resolves to 'int' during run-time for zero computational/memory overhead.
    # Hence, we check equality to the type references (which are really just 'NewType' instances),
    #  and don't use any sub-classing like we normally would.
    if typ == uint8 or typ == uint16 or typ == uint32 or typ == uint64\
            or typ == uint128 or typ == uint256 or typ == byte:
        return {"byte_len": typ.byte_len}


def ssz_list(typ):
    if hasattr(typ, '__bases__') and List in typ.__bases__:
        return {"elem_typ": read_list_elem_typ(typ), "byte_form": False}
    if typ == bytes:
        return {"elem_typ": uint8, "byte_form": True}


def ssz_vector(typ):
    if hasattr(typ, '__bases__'):
        if Vector in typ.__bases__:
            return {"elem_typ": read_vec_elem_typ(typ), "length": read_vec_len(typ), "byte_form": False}
        if BytesN in typ.__bases__:
            return {"elem_typ": uint8, "length": read_bytesN_len(typ), "byte_form": True}


def ssz_container(typ):
    if hasattr(typ, '__bases__') and SSZContainer in typ.__bases__:
        def get_field_values(value):
            return [getattr(value, field) for field in typ.__annotations__.keys()]
        field_names = list(typ.__annotations__.keys())
        field_types = list(typ.__annotations__.values())
        return {"get_field_values": get_field_values, "field_names": field_names, "field_types": field_types}


def ssz_default(typ):
    return {}
