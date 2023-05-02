from enough import AttrMap

import pytest


def test_attr_map() -> None:
    # Test AttrMap, a wrapped around an object which serves as a mapping from
    # that objects attributes to their values.
    class A:
        def __init__(self) -> None:
            self.attr1 = 1
            self._attr2 = 2
            self.__attr3__ = 3

        def method(self) -> int:
            return self.attr1 + self._attr2 + self.__attr3__

        @property
        def prop(self) -> int:
            return 4

        @classmethod
        def clsmethod(cls) -> int:
            return 5

        @staticmethod
        def static() -> int:
            return 6

    obj = A()
    mapping = AttrMap(obj)
    assert mapping.wrapped is obj
    assert mapping['__init__'] == obj.__init__
    assert mapping['attr1'] == 1
    assert mapping['_attr2'] == 2
    assert mapping['__attr3__'] == 3
    assert mapping['method'] == obj.method
    assert mapping['prop'] == 4
    assert mapping['clsmethod'] == obj.clsmethod
    assert mapping['static'] == obj.static
    assert len(mapping) == len(dir(obj))

    assert {
        k: mapping[k] for k in (
            '__init__',
            'attr1',
            '_attr2',
            '__attr3__',
            'method',
            'prop',
            'clsmethod',
            'static'
        )
    } == {
        '__init__': obj.__init__,
        'attr1': 1,
        '_attr2': 2,
        '__attr3__': 3,
        'method': obj.method,
        'prop': obj.prop,
        'clsmethod': obj.clsmethod,
        'static': obj.static
    }

    with pytest.raises(KeyError):
        # noinspection PyStatementEffect
        mapping['attr4']
