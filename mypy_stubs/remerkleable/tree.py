from typing import Callable, NewType, List, Optional, Protocol, TypeVar, Iterable, Iterator, Tuple
from hashlib import sha256


# Get the depth required for a given element count
# (in out): (0 0), (1 0), (2 1), (3 2), (4 2), (5 3), (6 3), (7 3), (8 3), (9 4)
def get_depth(elem_count: int) -> int:
    if elem_count <= 1:
        return 0
    return (elem_count - 1).bit_length()


Gindex = NewType("Gindex", int)

ROOT_GINDEX = Gindex(1)
LEFT_GINDEX = Gindex(2)
RIGHT_GINDEX = Gindex(3)


def to_gindex(index: int, depth: int):
    anchor = 1 << depth
    if index >= anchor:
        raise Exception("index %d too large for depth %d" % (index, depth))
    return anchor | index


def get_anchor_gindex(gindex: Gindex) -> Gindex:
    # noinspection PyTypeChecker
    return 1 << (gindex.bit_length() - 1)


def gindex_bit_iter(gindex: Gindex) -> Tuple[Iterator[bool], int]:
    if gindex < 1:
        raise Exception(f"invalid gindex: {gindex}")
    bit_len = gindex.bit_length()

    def iter_bits():
        if bit_len <= 1:
            return
        shift_v = 1 << (bit_len - 2)
        while shift_v != 0:
            yield (gindex & shift_v) != 0
            shift_v >>= 1
    return iter_bits(), bit_len - 1


def concat_gindices(steps: Iterable[Gindex]) -> Gindex:
    out = 1
    for step in steps:
        step_bit_len = step.bit_length() - 1
        out <<= step_bit_len
        out |= step ^ (1 << step_bit_len)
    return Gindex(out)


Root = NewType("Root", bytes)

MerkleFn = NewType("MerkleFn", Callable[[Root, Root], Root])

ZERO_ROOT: Root = Root(b'\x00' * 32)


def merkle_hash(left: Root, right: Root) -> Root:
    return sha256(left + right).digest()


Link = Callable[["Node"], "Node"]
SummaryLink = Callable[[], "Node"]


class Node(Protocol):

    def get_left(self) -> "Node":
        raise NavigationError

    def get_right(self) -> "Node":
        raise NavigationError

    def getter(self, target: Gindex) -> "Node":
        if target < 1:
            raise NavigationError
        if target == 1:
            return self
        node = self
        bit_iter, _ = gindex_bit_iter(target)
        for bit in bit_iter:
            if bit:
                node = node.get_right()
            else:
                node = node.get_left()
        return node

    def is_leaf(self) -> bool:
        return False

    def rebind_left(self, v: "Node") -> "Node":
        raise NavigationError

    def rebind_right(self, v: "Node") -> "Node":
        raise NavigationError

    def setter(self, target: Gindex, expand: bool = False) -> Link:
        raise NavigationError

    def summarize_into(self, target: Gindex) -> SummaryLink:
        setter = self.setter(target)
        node = self.getter(target)
        return lambda: setter(RootNode(node.merkle_root()))

    @property
    def root(self) -> Root:
        return self.merkle_root()

    def merkle_root(self) -> Root:
        raise


# hashes of hashes of zeroes etc.
zero_hashes: List[Root] = [ZERO_ROOT]

for i in range(100):
    zero_hashes.append(merkle_hash(zero_hashes[i], zero_hashes[i]))


def zero_node(depth: int) -> "RootNode":
    return RootNode(zero_hashes[depth])


def identity(v: Node) -> Node:
    return v


def compose(inner: Link, outer: Link) -> Link:
    return lambda v: outer(inner(v))


class NavigationError(RuntimeError):
    pass


V = TypeVar('V', bound=Node)


class RebindableNode(Node):
    def combine(self, left: Node, right: Node) -> Node:
        return PairNode(left, right)

    def rebind_left(self, v: Node) -> Node:
        return self.combine(v, self.get_right())

    def rebind_right(self, v: Node) -> Node:
        return self.combine(self.get_left(), v)

    def setter(self, target: Gindex, expand: bool = False) -> Link:
        if target < 1:
            raise NavigationError
        if target == 1:
            return identity
        if target == 2:
            return self.rebind_left
        if target == 3:
            return self.rebind_right
        bit_iter, depth = gindex_bit_iter(target)
        first = bit_iter.__next__()
        link = self.rebind_right if first else self.rebind_left
        prev_bit = first
        node = self
        for bit in bit_iter:
            if prev_bit:
                node = node.get_right()
            else:
                node = node.get_left()
            depth -= 1
            if node.is_leaf():
                if not expand:
                    raise NavigationError
                child = zero_node(depth - 1)
                node = self.combine(child, child)
            if bit:
                link = compose(node.rebind_right, link)
            else:
                link = compose(node.rebind_left, link)
            prev_bit = bit
        return link


class PairNode(RebindableNode, Node):
    """An optimized, with lazily-computed root, a node that references two child nodes."""

    __slots__ = 'left', 'right', '_root'

    left: Node
    right: Node
    _root: Optional[Root]

    def __init__(self, left: Node, right: Node):
        self.left = left
        self.right = right
        self._root = None

    def get_left(self) -> "Node":
        return self.left

    def get_right(self) -> "Node":
        return self.right

    def is_leaf(self) -> bool:
        return False

    def merkle_root(self) -> Root:
        if self._root is not None:
            return self._root
        self._root = merkle_hash(self.left.merkle_root(), self.right.merkle_root())
        return self._root

    def __repr__(self) -> str:
        return f"H({self.left}, {self.right})"


def subtree_fill_to_depth(bottom: Node, depth: int) -> Node:
    node = bottom
    while depth > 0:
        node = PairNode(node, node)
        depth -= 1
    return node


def subtree_fill_to_length(bottom: Node, depth: int, length: int) -> Node:
    if length == 0:
        return zero_node(depth)
    if length > (1 << depth):
        raise Exception("too many nodes")
    if length == (1 << depth):
        return subtree_fill_to_depth(bottom, depth)
    if depth == 0:
        if length == 1:
            return bottom
        else:
            raise NavigationError
    if depth == 1:
        return PairNode(bottom, bottom if length > 1 else zero_node(0))
    else:
        anchor = 1 << depth
        pivot = anchor >> 1
        if length <= pivot:
            return PairNode(subtree_fill_to_length(bottom, depth - 1, length), zero_node(depth))
        else:
            return PairNode(
                subtree_fill_to_depth(bottom, depth-1),
                subtree_fill_to_length(bottom, depth-1, length - pivot)
            )


def subtree_fill_to_contents(nodes: List[Node], depth: int) -> Node:
    if len(nodes) == 0:
        return zero_node(depth)
    if len(nodes) > (1 << depth):
        raise Exception("too many nodes")
    if depth == 0:
        if len(nodes) == 1:
            return nodes[0]
        else:
            raise NavigationError
    if depth == 1:
        return PairNode(nodes[0], nodes[1] if len(nodes) > 1 else zero_node(0))
    else:
        anchor = 1 << depth
        pivot = anchor >> 1
        if len(nodes) <= pivot:
            return PairNode(subtree_fill_to_contents(nodes, depth - 1), zero_node(depth - 1))
        else:
            return PairNode(
                subtree_fill_to_contents(nodes[:pivot], depth-1),
                subtree_fill_to_contents(nodes[pivot:], depth-1)
            )


class RootNode(Node):
    """An optimized root-holding node. To check if a Node functions as node without children,
     use node.is_leaf(), since there may be more classes implementing non-child node behavior."""

    __slots__ = '_root'

    _root: Root

    def __init__(self, root: Root):
        self._root = root

    def getter(self, target: Gindex) -> Node:
        if target != 1:
            raise NavigationError
        return self

    def is_leaf(self) -> bool:
        return True

    def setter(self, target: Gindex, expand: bool = False) -> Link:
        if target < 1:
            raise NavigationError
        if target == 1:
            return identity
        if expand:
            child = zero_node(target.bit_length() - 2)
            return PairNode(child, child).setter(target, expand=True)
        else:
            raise NavigationError

    @property
    def root(self) -> Root:
        # Override to directly provide the root instead of through merkle_root()
        return self._root

    def merkle_root(self) -> Root:
        return self._root

    def __repr__(self):
        return f"0x{self._root.hex()}"


def leaf_iter(node: Node) -> Iterator[Node]:
    """Iterate ove the leaf nodes of the given node. Left-to-right order."""
    if node.is_leaf():
        yield node
        return
    yield from leaf_iter(node.get_left())
    yield from leaf_iter(node.get_right())


def get_diff(a: Node, b: Node) -> Iterator[Tuple[Node, Node]]:
    """Iterate over the changes of b, not common with a. Left-to-right order.
     Returns (a,b) tuples that can't be diffed deeper."""
    if a.root != b.root:
        if a.is_leaf() or b.is_leaf():
            yield a, b
        else:
            yield from get_diff(a.get_left(), b.get_left())
            yield from get_diff(a.get_right(), b.get_right())
