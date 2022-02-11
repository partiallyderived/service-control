from unittest.mock import Mock

import pytest

import enough as br
from enough import EnumErrors
from enough.exceptions import BRError, EnumErrorsErrors


# These classes are used in test_enum_errors but are defined outside of it to avoid issues with '<locals>' being part of
# the qualified path to created errors, which messes with the expected __str__ and __repr__ results. Also note that the
# below classes are deliberately named so that they do not start with "Test", as otherwise Pytest would try to use them
# as test classes.

class ErrorToTest(Exception):
    @property
    def derived(self) -> int:
        # noinspection PyUnresolvedReferences
        return self.var1 + sum(int(val) for val in self.var2)


class ErrorsToTest(EnumErrors[ErrorToTest]):
    Error1 = 'First error format', (), ValueError
    Error2 = (
        'Second error ({_name_}) format: {var1} {", ".join(var2)} {derived}',
        ('var1', 'var2', 'var3'),
        (TypeError, ValueError)
    )
    # This error tests if args can be used as an attribute.
    Error3 = 'Third error format: {args} {value}', ('args', 'value')


def test_enum_errors() -> None:
    # Test the functionality of EnumErrors.
    # Test that exception type argument is correctly inferred.
    assert EnumErrorsErrors.error_type() is BRError
    assert ErrorsToTest.error_type() is ErrorToTest

    # Test that type rather than Enum __str__ and __repr__ are used.
    assert str(ErrorsToTest.Error1) == type.__str__(ErrorsToTest.Error1)
    assert repr(ErrorsToTest.Error1) == type.__repr__(ErrorsToTest.Error1)

    # Test that __name__ and __qualname__ are correctly set for the class (they are set dynamically).
    assert ErrorsToTest.Error1.__name__ == 'Error1'
    assert ErrorsToTest.Error1.__qualname__ == f'{ErrorsToTest.__qualname__}.Error1'

    # Verify correct naming of the dynamically created __str__ method.
    assert ErrorsToTest.Error1.__str__.__name__ == '__str__'
    assert ErrorsToTest.Error1.__str__.__qualname__ == f'{ErrorsToTest.Error1.__qualname__}.__str__'

    # Verify that the temporary attribute _original_init was deleted.
    assert not hasattr(ErrorsToTest.Error1, '_original_init')

    # Assert that Error1 and Error2 have the appropriate superclasses.
    assert issubclass(ErrorsToTest.Error1, ValueError)
    assert issubclass(ErrorsToTest.Error2, TypeError)
    assert issubclass(ErrorsToTest.Error2, ValueError)
    assert not issubclass(ErrorsToTest.Error1, TypeError)  # Sanity check.

    exc1 = ErrorsToTest.Error1()
    assert str(exc1) == 'First error format'

    # noinspection PyArgumentList
    exc2 = ErrorsToTest.Error2(var1=3, var2=['1', '2', '3'], var3='asdf')
    # noinspection PyUnresolvedReferences
    assert exc2.var1 == 3
    # noinspection PyUnresolvedReferences
    assert exc2.var2 == ['1', '2', '3']
    # noinspection PyUnresolvedReferences
    assert exc2.var3 == 'asdf'
    # noinspection PyUnresolvedReferences
    assert exc2.derived == 9
    assert str(exc2) == 'Second error (Error2) format: 3 1, 2, 3 9'

    # Check that Error3 can be instantiated.
    exc3 = ErrorsToTest.Error3('args', 'value')
    assert exc3.args == 'args'
    assert exc3.value == 'value'

    # Catch each exception type EnumErrors can raise.
    # noinspection PyTypeChecker
    with pytest.raises(EnumErrorsErrors.NoTypeArg) as exc_info:
        # noinspection PyUnusedLocal
        class NoTypeArgErrors(EnumErrors):
            Irrelevant = ''
    assert exc_info.value.type.__name__ == 'NoTypeArgErrors'

    # noinspection PyTypeChecker
    with br.raises(EnumErrorsErrors.NotType) as exc_info:
        # noinspection PyUnusedLocal
        class NonTypeArgErrors(EnumErrors[int | str]):
            Irrelevant = ''
    assert exc_info.value.obj == int | str

    # noinspection PyTypeChecker
    with br.raises(EnumErrorsErrors.NotExcType) as exc_info:
        # noinspection PyUnusedLocal
        class NonExceptionTypeArgErrors(EnumErrors[int]):
            Irrelevant = ''
    assert exc_info.value.type is int


def test_collect_errors() -> None:
    # Test that an exception type can use collect_errors to catch multiple exceptions while mapping values in a
    # collection and raise itself with a keyword argument set to a mapping from any values for which the mapping
    # function raised an exception of the specified type to the raised exception.
    class TestErrors(EnumErrors[Exception]):
        Error = 'msg', ('exceptions', 'val')

    err1 = ValueError()
    err2 = TypeError()
    m = Mock()
    side_effects = [err1, None, err2]
    m.side_effect = side_effects
    with br.raises(TestErrors.Error(exceptions={'arg1': err1, 'arg3': err2}, val='val')):
        TestErrors.Error.collect_errors(
            ('arg1', 'arg2', 'arg3'), m, (ValueError, TypeError), dest='exceptions', val='val'
        )

    # Exceptions raised which are not of the specified type will not be caught.
    m.side_effect = side_effects
    with br.raises(err2):
        TestErrors.Error.collect_errors(('arg1', 'arg2', 'arg3'), m, ValueError, dest='exceptions', val='val')

    # dest=None means the exceptions mapping will not be set in the context.
    m.side_effect = side_effects
    with br.raises(TestErrors.Error(exceptions={}, val='val')):
        TestErrors.Error.collect_errors(
            ('arg1', 'arg2', 'arg3'), m, (ValueError, TypeError), dest=None, exceptions={}, val='val'
        )

    # Specifying key_fn allows us to choose how the resulting error mapping is constructed.
    m.side_effect = side_effects
    with br.raises(TestErrors.Error(exceptions={'ARG1': err1, 'ARG3': err2}, val='val')):
        TestErrors.Error.collect_errors(
            ('arg1', 'arg2', 'arg3'), m, (ValueError, TypeError), dest='exceptions', key_fn=str.upper, val='val'
        )

    # No exception should result if nothing is caught.
    m.side_effect = None
    TestErrors.Error.collect_errors(
        ('arg1', 'arg2', 'arg3'), m, (ValueError, TypeError), dest='exceptions', val='val'
    )


def test_wrap() -> None:
    # Test that an exception type can use wrap to catch a particular EnumErrors enum and raise itself instead,
    # optionally copying over some of the attributes of the raised exception.

    class TestEnumErrors1(EnumErrors[Exception]):
        Error1 = 'msg1', ('attr1', 'attr2')
        Error1_2 = 'msg22', ('attr1', 'attr2')

    class TestEnumErrors2(EnumErrors[Exception]):
        Error2 = 'msg2', ('attr1', 'attr2', 'attr3')

    class TestEnumErrors3(EnumErrors[Exception]):
        Error3 = 'msg3', ('attr1', 'attr2')

    with br.raises(TestEnumErrors2.Error2(attr1=1, attr2=2, attr3=3)):
        with TestEnumErrors2.Error2.wrap(TestEnumErrors1.Error1, attr3=3):
            raise TestEnumErrors1.Error1(attr1=1, attr2=2)

    # Trying to wrap another exception won't work.
    with br.raises(TestEnumErrors3.Error3(attr1=1, attr2=2)):
        with TestEnumErrors2.Error2.wrap(TestEnumErrors1.Error1, attr3=3):
            raise TestEnumErrors3.Error3(attr1=1, attr2=2)

    # Same result even if the differing types are from different enumerations.
    with br.raises(TestEnumErrors1.Error1_2(attr1=1, attr2=2)):
        with TestEnumErrors2.Error2.wrap(TestEnumErrors1.Error1, attr3=3):
            raise TestEnumErrors1.Error1_2(attr1=1, attr2=2)

    # forward=False should result in no attributes being forwarded.
    with br.raises(TestEnumErrors2.Error2(attr1=1, attr2=2, attr3=3)):
        with TestEnumErrors2.Error2.wrap(TestEnumErrors1.Error1, forward=False, attr1=1, attr2=2, attr3=3):
            raise TestEnumErrors1.Error1(attr1=4, attr2=5)

    # Giving an iterable for forward should result in only those attributes being forwarded.
    with br.raises(TestEnumErrors2.Error2(attr1=1, attr2=5, attr3=3)):
        with TestEnumErrors2.Error2.wrap(TestEnumErrors1.Error1, forward={'attr2'}, attr1=1, attr3=3):
            raise TestEnumErrors1.Error1(attr1=4, attr2=5)

    # No exception should result if nothing is caught.
    with TestEnumErrors2.Error2.wrap(TestEnumErrors1.Error1, attr3=3):
        pass


def test_wrap_error() -> None:
    # Test that EnumErrors.wrap_error can catch a specified exception type and set it as a destination attribute.
    class TestErrors(EnumErrors[Exception]):
        Error = 'msg', ('exc', 'arg')

    err = ValueError()
    with br.raises(TestErrors.Error(exc=err, arg='arg')):
        with TestErrors.Error.wrap_error(ValueError, dest='exc', arg='arg'):
            raise err

    # Won't work with wrong error type.
    with br.raises(err):
        with TestErrors.Error.wrap_error(TypeError, dest='exc', arg='arg'):
            raise err

    # Multiple types can be used.
    with br.raises(TestErrors.Error(exc=err, arg='arg')):
        with TestErrors.Error.wrap_error((ValueError, TypeError), dest='exc', arg='arg'):
            raise err

    # dest=None means the exception will not be set for the context.
    with br.raises(TestErrors.Error(exc=None, arg='arg')):
        with TestErrors.Error.wrap_error(ValueError, dest=None, exc=None, arg='arg'):
            raise err

    # No exception should result if nothing is caught.
    with TestErrors.Error.wrap_error((ValueError, TypeError), dest='exc', arg='arg'):
        pass
