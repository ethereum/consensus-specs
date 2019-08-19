from eth2spec.utils.ssz.ssz_typing import Container, ElementsType, Bytes32, BasicType
from typing import Sequence
from eth2spec.utils.ssz.ssz_gen_index import GeneralizedIndex, concat_generalized_indices
from eth2spec.utils.ssz.ssz_multi_proofs import verify_merkle_multiproof
from eth2spec.utils.ssz.ssz_math import next_power_of_two
from eth2spec.utils.ssz.ssz_impl import item_length


class PartialMask(object):

    @classmethod
    def get_gen_indices(cls) -> Sequence[GeneralizedIndex]:
        raise Exception("Implement in subclass")

    # TODO: implement load/get leaves, and load/get-proof.
    def load_leaves(self, leaves: Sequence[Bytes32]):
        raise Exception("Implement in subclass")

    def get_leaves(self) -> Sequence[Bytes32]:
        raise Exception("Implement in subclass")

    def load_proof(self, proof: Sequence[Bytes32]):
        raise Exception("Implement in subclass")

    def get_proof(self) -> Sequence[Bytes32]:
        raise Exception("Implement in subclass")

    @classmethod
    def verify_proof(cls, leaves: Sequence[Bytes32], proof: Sequence[Bytes32], root: Bytes32) -> bool:
        gen_indices = cls.get_gen_indices()
        return verify_merkle_multiproof(leaves, proof, gen_indices, root)

    def load_and_verify_proof(self, leaves: Sequence[Bytes32], proof: Sequence[Bytes32], root: Bytes32) -> bool:
        if self.__class__.verify_proof(leaves, proof, root):
            self.load_proof(proof)
            self.load_leaves(leaves)
            return True
        else:
            return False

    def verify(self, root: Bytes32) -> bool:
        return self.__class__.verify_proof(self.get_leaves(), self.get_proof(), root)


class PartialContainerMask(PartialMask, Container):
    __partial_base__: Container

    def __new__(cls, *args, **kwargs):
        mask = list(cls.__annotations__.items())
        base = list(cls.__partial_base__.get_fields().items())
        mask_i = 0
        base_i = 0
        while True:
            if len(mask) <= mask_i:
                break
            if len(base) <= base_i:
                raise Exception("more partial mask fields than base fields, or out of order and thus not recognized")
            m_key, m_type = mask[mask_i]
            b_key, b_type = base[base_i]
            if m_key != b_key:
                base_i += 1
            else:
                if not issubclass(b_type, m_type):
                    raise Exception("partial mask field can only declare an equal or super type of the base field type")
                base_i += 1
                mask_i += 1
        # note: the produced class will not include `__ssz_fields__` from the `cls.__partial_base__`.
        # This prevents unnecessary default-initialization of these fields,
        # and proof data will not be strictly affected by these fields anyway,
        # as proofs may not be 1:1 (e.g. two adjacent ignored leaf nodes will be witness together)
        return super().__new__(cls, *args, **kwargs)

    @classmethod
    def get_gen_indices(cls) -> Sequence[GeneralizedIndex]:
        mask = list(cls.__ssz_fields__.items())
        base = list(cls.__partial_base__.get_fields().items())
        mask_i = 0
        base_i = 0
        out = []
        depth = next_power_of_two(len(base))
        while True:
            if len(mask) <= mask_i:
                break
            m_key, m_type = mask[mask_i]
            b_key, b_type = base[base_i]
            if m_key != b_key:
                base_i += 1
            else:
                base_i += 1
                mask_i += 1
                g_index = depth | base_i
                if issubclass(m_type, PartialMask):
                    out.extend(concat_generalized_indices(g_index, i) for i in m_type.get_gen_indices())
                else:
                    out.append(g_index)
        return out


class PartialElementsMask(PartialMask, object):

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)

    # TODO: should this be a classmethod, or can partial things be non-uniform within elements?
    @classmethod
    def get_gen_indices(cls) -> Sequence[GeneralizedIndex]:
        if not isinstance(cls, ElementsType):
            raise Exception("cannot get generalized indices for non-elements type")
        depth = next_power_of_two(cls.max_elements())
        out = []
        if isinstance(cls.elem_type, BasicType):
            last_chunk_i = None
            elems_per_chunk = 32 / item_length(cls.elem_type)
            for i in cls.__incl_indices__:
                chunk_i = i // elems_per_chunk
                if last_chunk_i is not None or chunk_i == last_chunk_i:
                    continue
                last_chunk_i = chunk_i
                out.append(depth | chunk_i)
        else:
            elem_type_is_partial = issubclass(cls.elem_type, PartialMask)
            for i in cls.__incl_indices__:
                g_index = depth | i
                if elem_type_is_partial:
                    out.extend(concat_generalized_indices(g_index, inner_i) for inner_i in cls.elem_type.get_gen_indices())
                else:
                    out.append(g_index)


class PartialType(type):

    def __getitem__(self, params):
        if not isinstance(params, tuple):
            params = (params,)
        if not (0 < len(params) <= 2):
            raise Exception("partial constructed with wrong amount of parameters")
        if len(params) == 1 and issubclass(params[0], Container):
            return type(f'PartialContainer[{params[0].__name__}]',
                        (PartialContainerMask, params[0]), {'__partial_base__': params[0]})
        elif len(params) == 2 and isinstance(params[0], ElementsType)\
                and isinstance(params[1], list) and all(map(lambda x: isinstance(x, int), params[1])):
            # Partial is a complex type, and we select some fields with the second argument.
            sorted_indices = sorted(params[1])
            if sorted_indices != params[1]:
                raise Exception(f"partial indices {params[1]} must be sorted (incremental order)")
            if len(set(params[1])) != len(params[1]):
                raise Exception(f"partial indices {params[1]} must be unique")
            max_els = params[0].max_elements()
            if sorted_indices[-1] >= max_els:  # just check the last sorted element, it is faster and easier.
                raise Exception(f"partial indices {params[1]} may not exceed max length {max_els}")
            return type(f'Partial({", ".join(map(str, sorted_indices))})[{params[0].__name__}]',
                        (PartialElementsMask, params[0]), {'__incl_indices__': sorted_indices})
        else:
            raise Exception("invalid parameters for partial construction")


class Partial(metaclass=PartialType):
    pass


from eth2spec.utils.ssz.ssz_typing import byte, uint64, List


class Foo(Container):
    Abc: byte
    Bar: uint64
    Wowow: uint64


class PFoo2(Partial[Foo]):
    Bar: uint64
    Wowow: uint64


class PFoo(Partial[Foo]):
    Bar: uint64

pf = PFoo

pfi = pf()

print(pfi)

FooLi = List[Foo, 128]

# make a partial of the list type, requiring specific list-indices
PFooLi = Partial[FooLi, [2, 4, 5]]

f = PFooLi()

print(f)
