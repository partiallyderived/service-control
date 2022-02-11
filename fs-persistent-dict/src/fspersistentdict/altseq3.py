from collections.abc import MutableSequence

from enough import T


class MutableSeq(MutableSequence[T]):
    def _get_idxs(self, idxs: range) -> MutableSequence[T]:
        match idxs.step > 0, abs(idxs.step) == 1:
            case True, True:
                return self._get_idxs_(idxs.start, idxs.stop)
            case True, False:
                return self._get_idxs_s(idxs)
            case False, True:
                return self._get_idxs_r(idxs.start, idxs.stop)
            case False, False:
                return self._get_idxs_sr(idxs)
            case _:
                raise AssertionError('Unreachable code.')
