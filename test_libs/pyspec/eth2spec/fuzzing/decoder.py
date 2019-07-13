from eth2spec.utils.ssz import ssz_typing as spec_ssz
import ssz


def translate_typ(typ) -> ssz.BaseSedes:
    """
    Translates a spec type to a Py-SSZ type description (sedes).
    :param typ: The spec type, a class.
    :return: The Py-SSZ equivalent.
    """
    if issubclass(typ, spec_ssz.Container):
        return ssz.Container(
            [translate_typ(field_typ) for field_name, field_typ in typ.get_fields().items()])
    elif issubclass(typ, spec_ssz.BytesN):
        return ssz.ByteVector(typ.length)
    elif issubclass(typ, spec_ssz.Bytes):
        return ssz.ByteList()
    elif issubclass(typ, spec_ssz.Vector):
        return ssz.Vector(translate_typ(typ.elem_type), typ.length)
    elif issubclass(typ, spec_ssz.List):
        return ssz.List(translate_typ(typ.elem_type), typ.length)
    elif issubclass(typ, spec_ssz.Bitlist):
        return ssz.Bitlist(typ.length)
    elif issubclass(typ, spec_ssz.Bitvector):
        return ssz.Bitvector(typ.length)
    elif issubclass(typ, spec_ssz.boolean):
        return ssz.boolean
    elif issubclass(typ, spec_ssz.uint):
        if typ.byte_len == 1:
            return ssz.uint8
        elif typ.byte_len == 2:
            return ssz.uint16
        elif typ.byte_len == 4:
            return ssz.uint32
        elif typ.byte_len == 8:
            return ssz.uint64
        elif typ.byte_len == 16:
            return ssz.uint128
        elif typ.byte_len == 32:
            return ssz.uint256
        else:
            raise TypeError("invalid uint size")
    else:
        raise TypeError("Type not supported: {}".format(typ))


def translate_value(value, typ):
    """
    Translate a value output from Py-SSZ deserialization into the given spec type.
    :param value: The PySSZ value
    :param typ: The type from the spec to translate into
    :return: the translated value
    """
    if issubclass(typ, spec_ssz.uint):
        if typ.byte_len == 1:
            return spec_ssz.uint8(value)
        elif typ.byte_len == 2:
            return spec_ssz.uint16(value)
        elif typ.byte_len == 4:
            return spec_ssz.uint32(value)
        elif typ.byte_len == 8:
            return spec_ssz.uint64(value)
        elif typ.byte_len == 16:
            return spec_ssz.uint128(value)
        elif typ.byte_len == 32:
            return spec_ssz.uint256(value)
        else:
            raise TypeError("invalid uint size")
    elif issubclass(typ, spec_ssz.List):
        return [translate_value(elem, typ.elem_type) for elem in value]
    elif issubclass(typ, spec_ssz.boolean):
        return value
    elif issubclass(typ, spec_ssz.Vector):
        return typ(*(translate_value(elem, typ.elem_type) for elem in value))
    elif issubclass(typ, spec_ssz.Bitlist):
        return typ(value)
    elif issubclass(typ, spec_ssz.Bitvector):
        return typ(value)
    elif issubclass(typ, spec_ssz.BytesN):
        return typ(value)
    elif issubclass(typ, spec_ssz.Bytes):
        return value
    if issubclass(typ, spec_ssz.Container):
        return typ(**{f_name: translate_value(f_val, f_typ) for (f_val, (f_name, f_typ))
                      in zip(value, typ.get_fields().items())})
    else:
        raise TypeError("Type not supported: {}".format(typ))
