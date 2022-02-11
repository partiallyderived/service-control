from enum import Enum
from unittest.mock import Mock

import pytest

import bobbeyreese as br
from bobbeyreese import KWErrors, KWError
from bobbeyreese.exceptions import KWErrorErrors, KWErrorError


def test_kw_error() -> None:
    # Test the functionality of KWError and ErrorContext.
    class TestKWError(KWError):
        @property
        def derived(self) -> int:
            return self.var1 + sum(int(val) for val in self.var2)

    class TestKWErrors(KWErrors[TestKWError]):
        CONTEXT1 = 'First context format'
        CONTEXT2 = ('Second Context ({ctx.name}) format: {var1} {", ".join(var2)} {derived}', ('var1', 'var2', 'var3'))
    assert KWErrorErrors.error_type() == KWErrorError
    assert TestKWErrors.error_type() == TestKWError

    exc1 = TestKWErrors.CONTEXT1()
    assert exc1.ctx is TestKWErrors.CONTEXT1
    assert str(exc1) == 'First context format'
    assert repr(exc1) == 'TestKWError(CONTEXT1)'

    with pytest.raises(AttributeError):
        # noinspection PyStatementEffect
        exc1._kwargs
    with pytest.raises(AttributeError):
        # noinspection PyStatementEffect
        exc1._msg
    with pytest.raises(AttributeError):
        # noinspection PyStatementEffect
        exc1.args

    exc2 = TestKWErrors.CONTEXT2(var1=3, var2=['1', '2', '3'], var3='asdf')
    assert exc2.ctx is TestKWErrors.CONTEXT2
    assert exc2.var1 == 3
    assert exc2.var2 == ['1', '2', '3']
    assert exc2.var3 == 'asdf'
    assert exc2.derived == 9
    with pytest.raises(AttributeError):
        # noinspection PyStatementEffect
        exc2.var4
    assert str(exc2) == 'Second Context (CONTEXT2) format: 3 1, 2, 3 9'
    assert repr(exc2) == "TestKWError(CONTEXT2, var1=3, var2=['1', '2', '3'], var3=asdf)"
    with br.raises(KWErrorErrors.MODIFICATION()):
        exc2.proxy = 5

    # Test __eq__.
    assert TestKWErrors.CONTEXT1() == TestKWErrors.CONTEXT1()
    assert (
        TestKWErrors.CONTEXT2(var1=1, var2=['1', '2'], var3='asdf') ==
        TestKWErrors.CONTEXT2(var1=1, var2=['1', '2'], var3='asdf')
    )
    assert (
        TestKWErrors.CONTEXT2(var1=1, var2=['1', '2'], var3='asdf') !=
        TestKWErrors.CONTEXT2(var1=2, var2=['1', '2'], var3='asdf')
    )
    assert (
        TestKWErrors.CONTEXT2(var1=1, var2=['1', '2'], var3='asdf') !=
        TestKWErrors.CONTEXT2(var1=1, var2=['1', '1'], var3='asdf')
    )

    with br.raises(KWErrorErrors.MISSING_ATTRS(context=TestKWErrors.CONTEXT2, missing={'var1', 'var3'})):
        TestKWErrors.CONTEXT2(var2=['1', '2', '3'])

    with br.raises(KWErrorErrors.UNRECOGNIZED_ATTRS(context=TestKWErrors.CONTEXT2, unrecognized={'var4', 'var5'})):
        TestKWErrors.CONTEXT2(var5=6, var1=3, var4='fdsa', var2=['1', '2', '3'], var3='asdf')

    # Right context.
    KWErrorError(KWErrorErrors.MODIFICATION)
    with br.raises(KWErrorErrors.ERR_MISMATCH(
        context=TestKWErrors.CONTEXT1, actual=TestKWError, expected=KWErrorError)
    ):
        # Wrong context.
        KWErrorError(TestKWErrors.CONTEXT1)

    # Catch each type parameter exception ErrorContext can raise.
    class NoTypeArgContext(KWErrors, Enum):
        IRRELEVANT = ''

    with br.raises(KWErrorErrors.NO_TYPE_ARG()):
        NoTypeArgContext.IRRELEVANT()

    class NonTypeTypeArgContext(KWErrors[int | str], Enum):
        IRRELEVANT = ''

    with br.raises(KWErrorErrors.NOT_TYPE(obj=int | str)):
        NonTypeTypeArgContext.IRRELEVANT()

    class NonKWErrorTypeArgContext(KWErrors[Exception], Enum):
        IRRELEVANT = ''

    with br.raises(KWErrorErrors.NOT_KW_ERROR(type=Exception)):
        NonKWErrorTypeArgContext.IRRELEVANT()


def test_collect_errors() -> None:
    # Test that KWErrors.collect_errors can catch multiple exceptions while mapping values in a collection and raise its
    # own exception type with a keyword argument set to a mapping from any values for which the mapping function raised
    # an exception of the specified type to the raised exception.
    class TestKWError(KWError): pass

    class TestKWErrors(KWErrors[TestKWError]):
        CTX = 'msg', ('exceptions', 'val')

    err1 = ValueError()
    err2 = TypeError()
    m = Mock()
    side_effects = [err1, None, err2]
    m.side_effect = side_effects
    with br.raises(TestKWErrors.CTX(exceptions={'arg1': err1, 'arg3': err2}, val='val')):
        TestKWErrors.CTX.collect_errors(
            ('arg1', 'arg2', 'arg3'), m, (ValueError, TypeError), dest='exceptions', val='val'
        )

    # Exceptions raised which are not of the specified type will not be caught.
    m.side_effect = side_effects
    with br.raises(err2):
        TestKWErrors.CTX.collect_errors(('arg1', 'arg2', 'arg3'), m, ValueError, dest='exceptions', val='val')

    # dest=None means the exceptions mapping will not be set in the context.
    m.side_effect = side_effects
    with br.raises(TestKWErrors.CTX(exceptions={}, val='val')):
        TestKWErrors.CTX.collect_errors(
            ('arg1', 'arg2', 'arg3'), m, (ValueError, TypeError), dest=None, exceptions={}, val='val'
        )

    # Specifying key_fn allows us to choose how the resulting error mapping is constructed.
    m.side_effect = side_effects
    with br.raises(TestKWErrors.CTX(exceptions={'ARG1': err1, 'ARG3': err2}, val='val')):
        TestKWErrors.CTX.collect_errors(
            ('arg1', 'arg2', 'arg3'), m, (ValueError, TypeError), dest='exceptions', key_fn=str.upper, val='val'
        )

    # No exception should result if nothing is caught.
    m.side_effect = None
    TestKWErrors.CTX.collect_errors(('arg1', 'arg2', 'arg3'), m, (ValueError, TypeError), dest='exceptions', val='val')


def test_wrap() -> None:
    # Test that KWErrors.wrap can catch a particular KWErrors enum and raise its own exception type with the same
    # attributes.
    class TestKWError1(KWError): pass
    class TestKWError2(KWError): pass
    class TestKWError3(KWError): pass

    class TestKWErrors1(KWErrors[TestKWError1]):
        CTX1 = 'msg1', ('attr1', 'attr2')
        CTX1_2 = 'msg22', ('attr1', 'attr2')

    class TestKWErrors2(KWErrors[TestKWError2]):
        CTX2 = 'msg2', ('attr1', 'attr2', 'attr3')

    class TestKWErrors3(KWErrors[TestKWError3]):
        CTX3 = 'msg3', ('attr1', 'attr2')

    with br.raises(TestKWErrors2.CTX2(attr1=1, attr2=2, attr3=3)):
        with TestKWErrors2.CTX2.wrap(TestKWErrors1.CTX1, attr3=3):
            raise TestKWErrors1.CTX1(attr1=1, attr2=2)

    # Trying to wrap another exception won't work.
    with br.raises(TestKWErrors3.CTX3(attr1=1, attr2=2)):
        with TestKWErrors2.CTX2.wrap(TestKWErrors1.CTX1, attr3=3):
            raise TestKWErrors3.CTX3(attr1=1, attr2=2)

    # Same case with the same exception but a different context.
    with br.raises(TestKWErrors1.CTX1_2(attr1=1, attr2=2)):
        with TestKWErrors2.CTX2.wrap(TestKWErrors1.CTX1, attr3=3):
            raise TestKWErrors1.CTX1_2(attr1=1, attr2=2)

    # forward=False should result in no attributes being forwarded.
    with br.raises(TestKWErrors2.CTX2(attr1=1, attr2=2, attr3=3)):
        with TestKWErrors2.CTX2.wrap(TestKWErrors1.CTX1, forward=False, attr1=1, attr2=2, attr3=3):
            raise TestKWErrors1.CTX1(attr1=4, attr2=5)

    # Giving an iterable for forward should result in only those attributes being forwarded.
    with br.raises(TestKWErrors2.CTX2(attr1=1, attr2=5, attr3=3)):
        with TestKWErrors2.CTX2.wrap(TestKWErrors1.CTX1, forward={'attr2'}, attr1=1, attr3=3):
            raise TestKWErrors1.CTX1(attr1=4, attr2=5)

    # No exception should result if nothing is caught.
    with TestKWErrors2.CTX2.wrap(TestKWErrors1.CTX1, attr3=3):
        pass


def test_wrap_error() -> None:
    # Test that KWErrors.wrap_error can catch a specified exception type and set it as a destination attribute.
    class TestKWError(KWError): pass

    class TestKWErrors(KWErrors[TestKWError]):
        CTX = 'msg', ('exc', 'arg')

    err = ValueError()
    with br.raises(TestKWErrors.CTX(exc=err, arg='arg')):
        with TestKWErrors.CTX.wrap_error(ValueError, dest='exc', arg='arg'):
            raise err

    # Won't work with wrong error type.
    with br.raises(err):
        with TestKWErrors.CTX.wrap_error(TypeError, dest='exc', arg='arg'):
            raise err

    # Multiple types can be used.
    with br.raises(TestKWErrors.CTX(exc=err, arg='arg')):
        with TestKWErrors.CTX.wrap_error((ValueError, TypeError), dest='exc', arg='arg'):
            raise err

    # dest=None means the exception will not be set for the context.
    with br.raises(TestKWErrors.CTX(exc=None, arg='arg')):
        with TestKWErrors.CTX.wrap_error(ValueError, dest=None, exc=None, arg='arg'):
            raise err

    # No exception should result if nothing is caught.
    with TestKWErrors.CTX.wrap_error((ValueError, TypeError), dest='exc', arg='arg'):
        pass
