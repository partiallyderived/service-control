from collections.abc import Iterator, Mapping


class AttrMap(Mapping[str, object]):
    """Mapping which acts as a wrapper around an object, using ``getattr`` for
    that object in order to implement ``__getitem__``.
    """
    #: The wrapped object.
    wrapped: object

    def __init__(self, obj: object) -> None:
        """Initialize this map with an object to wrap.

        :param obj: Object to wrap.
        """
        self.wrapped = obj

    def __getitem__(self, attr: str) -> object:
        """Gets the value of the requested attribute in ``self.wrapped``.

        :param attr: Name of the attribute to get.
        :return: The resulting value.
        :raise KeyError: If `getattr(self.wrapped, attr)` raises an
            ``AttributeError``.
        """
        try:
            return getattr(self.wrapped, attr)
        except AttributeError as e:
            raise KeyError(*e.args)

    def __iter__(self) -> Iterator[str]:
        """Returns an iterator over the attributes of ``self.wrapped``. Uses
        ``dir``, results will not be accurate when ``dir`` is inaccurate.

        :return: An iterator over the attributes of ``self.wrapped``.
        """
        return iter(dir(self.wrapped))

    def __len__(self) -> int:
        """Gets the number of attributes of ``self.wrapped``. Uses ``dir``,
        results will not be accurate when ``dir`` is inaccurate.

        :return: The number of attributes of ``self.wrapped``.
        """
        return len(dir(self.wrapped))
