from typing import List as PyList, Optional, Type, Sequence
from remerkleable.core import BasicView, View
from remerkleable.tree import Node, Root, RootNode, ZERO_ROOT


class BitfieldIter(object):
    """Iterates a subtree by traversing it with a stack (thus readonly), returning bits"""

    anchor: Node
    depth: int
    i: int
    j: int
    rootIndex: int
    length: int
    currentRoot: Root
    stack: PyList[Optional[Node]]

    def __init__(self, anchor: Node, depth: int, length: int):
        self.anchor = anchor
        self.depth = depth
        self.length = length
        self.i = 0
        self.j = 0
        self.rootIndex = 0
        self.currentRoot = ZERO_ROOT
        self.stack = [None] * depth
        limit = (1 << depth) << 8
        if limit < length:
            raise Exception(f"cannot handle iterate {length} bits in subtree of depth {depth} deep (limit {limit} bits)")

    def __iter__(self):
        self.i = 0
        self.j = 0
        self.rootIndex = 0
        self.currentRoot = ZERO_ROOT
        self.stack = [None] * self.depth
        return self

    def __next__(self):
        # done yet?
        if self.i >= self.length:
            raise StopIteration

        # in the middle of a node currently? finish that first
        if self.j > 0:
            elByte = self.currentRoot[self.j >> 3]
            elem = ((elByte >> (self.j & 7)) & 1) == 1
            self.j += 1
            if self.j > 0xff:
                self.j = 0
            self.i += 1
            return elem

        stackIndex: int
        if self.rootIndex != 0:
            # XOR current index with previous index
            # Result: highest bit matches amount we have to backtrack up the stack
            s = self.rootIndex ^ (self.rootIndex - 1)
            stackIndex = self.depth
            while s != 0:
                s >>= 1
                stackIndex -= 1

            # then move to the right from that upper previously remembered left-hand node
            node = self.stack[stackIndex]
            node = node.get_right()
            stackIndex += 1
        else:
            node = self.anchor
            stackIndex = 0

        # and move down left into this new subtree
        for x in range(stackIndex, self.depth):
            # remember left-hand nodes, we may revisit them
            self.stack[x] = node
            node = node.get_left()

        # Get leaf node as a root
        if not node.is_leaf():
            raise Exception(f"expected leaf node {self.rootIndex} to be a Root type")

        # remember the root, we need it for more bits
        self.currentRoot = node.root

        # get the first bit
        el = (self.currentRoot[0] & 1 == 1)
        # indicate that we have done one bit, and need to read more
        self.j = 1
        # And that the next root will be 1 after
        self.rootIndex += 1
        # And we progress the general element counter
        self.i += 1

        # Return the actual element
        return el


class PackedIter(object):
    """Iterates a subtree by traversing it with a stack (thus readonly), returning the unpacked elements"""

    anchor: Node
    depth: int
    i: int
    j: int
    rootIndex: int
    length: int
    per_node: int
    currentRoot: RootNode
    elem_type: Type[BasicView]
    stack: PyList[Optional[Node]]

    def __init__(self, anchor: Node, depth: int, length: int, elem_type: Type[BasicView]):
        self.anchor = anchor
        self.depth = depth
        self.length = length
        self.i = 0
        self.rootIndex = 0
        self.currentRoot = RootNode(ZERO_ROOT)
        self.stack = [None] * depth
        self.elem_type = elem_type

        self.per_node = 32 // elem_type.type_byte_length()
        self.j = self.per_node

        limit = (1 << depth) * self.per_node

        if limit < length:
            raise Exception(f"cannot handle iterate length {length} bottom subviews ({self.per_node} per node) "
                            f"in subtree of depth {depth} deep (limit {limit} subviews)")

    def __iter__(self):
        self.i = 0
        self.j = self.per_node
        self.rootIndex = 0
        self.currentRoot = RootNode(ZERO_ROOT)
        self.stack = [None] * self.depth
        return self

    def __next__(self):
        # done yet?
        if self.i >= self.length:
            raise StopIteration

        # in the middle of a node currently? finish that first
        if self.j < self.per_node:
            elem = self.elem_type.basic_view_from_backing(self.currentRoot, self.j)
            self.j += 1
            self.i += 1
            return elem

        stackIndex: int
        if self.rootIndex != 0:
            # XOR current index with previous index
            # Result: highest bit matches amount we have to backtrack up the stack
            s = self.rootIndex ^ (self.rootIndex - 1)
            stackIndex = self.depth
            while s != 0:
                s >>= 1
                stackIndex -= 1

            # then move to the right from that upper previously remembered left-hand node
            node = self.stack[stackIndex]
            node = node.get_right()
            stackIndex += 1
        else:
            node = self.anchor
            stackIndex = 0

        # and move down left into this new subtree
        for x in range(stackIndex, self.depth):
            # remember left-hand nodes, we may revisit them
            self.stack[x] = node
            node = node.get_left()

        # Get leaf node as a root
        if not node.is_leaf():
            raise Exception(f"expected leaf node {self.rootIndex} to be a Root type")

        # remember the root, we need it for more elements
        self.currentRoot = node

        # get the first element
        el = self.elem_type.basic_view_from_backing(node, 0)
        # indicate that we have done one packed element, and need to read more
        self.j = 1
        # And that the next root will be 1 after
        self.rootIndex += 1
        # And we progress the general element counter
        self.i += 1

        # Return the actual element
        return el


class NodeIter(object):
    """Iterates a subtree by traversing it with a stack (thus readonly), returning the bottom nodes"""

    anchor: Node
    depth: int
    i: int
    length: int
    per_node: int
    stack: PyList[Optional[Node]]

    def __init__(self, anchor: Node, depth: int, length: int):
        self.anchor = anchor
        self.depth = depth
        self.length = length
        self.i = 0
        self.currentRoot = RootNode(ZERO_ROOT)
        self.stack = [None] * depth

        limit = 1 << depth
        if limit < length:
            raise Exception(f"cannot handle iterate length {length} bottom nodes "
                            f"in subtree of depth {depth} deep (limit {limit} nodes)")

    def __iter__(self):
        self.i = 0
        self.stack = [None] * self.depth
        return self

    def __next__(self):
        # done yet?
        if self.i >= self.length:
            raise StopIteration

        stackIndex: int
        if self.i != 0:
            # XOR current index with previous index
            # Result: highest bit matches amount we have to backtrack up the stack
            s = self.i ^ (self.i - 1)
            stackIndex = self.depth
            while s != 0:
                s >>= 1
                stackIndex -= 1

            # then move to the right from that upper previously remembered left-hand node
            node = self.stack[stackIndex]
            node = node.get_right()
            stackIndex += 1
        else:
            node = self.anchor
            stackIndex = 0

        # and move down left into this new subtree
        for x in range(stackIndex, self.depth):
            # remember left-hand nodes, we may revisit them
            self.stack[x] = node
            node = node.get_left()

        # We progress the general element counter
        self.i += 1

        return node


class ComplexElemIter(NodeIter):
    """Iterates a subtree by traversing it with a stack (thus readonly), reusing a view to return elements"""

    reused_view: View

    def __init__(self, anchor: Node, depth: int, length: int, elem_type: Type[View]):
        super().__init__(anchor, depth, length)
        self.reused_view = elem_type.default(None)

    def __next__(self):
        node = super().__next__()
        self.reused_view.set_backing(node)
        return self.reused_view


class ComplexFreshElemIter(NodeIter):
    """Iterates a subtree by traversing it with a stack (thus readonly), not reusing a view to return elements"""

    elem_type: Type[View]

    def __init__(self, anchor: Node, depth: int, length: int, elem_type: Type[View]):
        super().__init__(anchor, depth, length)
        self.elem_type = elem_type

    def __next__(self):
        node = super().__next__()
        return self.elem_type.view_from_backing(node, None)


class ContainerElemIter(NodeIter):
    """Iterates a subtree by traversing it with a stack (thus readonly), not reusing a view to return elements"""

    elem_types: Sequence[Type[View]]

    def __init__(self, anchor: Node, depth: int, elem_types: Sequence[Type[View]]):
        super().__init__(anchor, depth, len(elem_types))
        self.elem_types = elem_types

    def __next__(self):
        i = self.i
        node = super().__next__()
        return self.elem_types[i].view_from_backing(node, None)
