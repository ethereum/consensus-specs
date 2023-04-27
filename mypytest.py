class Example:
    a: int
    def __init__(self) -> None:
        self.a = 0

def f_example(a: int) -> None:
    return None

def test() -> None:
    e = Example()
    e2 = Example(1)
    f_example()
    f_example(1)

test()