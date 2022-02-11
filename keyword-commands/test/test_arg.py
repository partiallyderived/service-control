import enough as br

from keywordcommands import Arg
from keywordcommands.exceptions import ArgInitContext


def test_init() -> None:
    # Test that Arg.__init__ raises an exception is "name" is not a valid word.
    # This should succeed.
    arg = Arg('Arg 1', 'arg1')
    assert arg.description == 'Arg 1'
    assert arg.name == 'arg1'

    # As should this.
    Arg('Arg 2', 'arg-2')

    # This should fail.
    with br.raises(ArgInitContext.MalformedName(name='arg#')):
        Arg('Arg 3', 'arg#')

    # As should this.
    with br.raises(ArgInitContext.MalformedName(name='arg_4')):
        Arg('Arg 4', 'arg_4')
