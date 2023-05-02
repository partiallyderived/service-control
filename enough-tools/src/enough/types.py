from typing import TypeVar

# Unconstrained type vars.
A = TypeVar('A')
A1 = TypeVar('A1')
A2 = TypeVar('A2')

# Covariant unconstrained type vars.
AP = TypeVar('AP')
AP1 = TypeVar('AP1')
AP2 = TypeVar('AP2')

# Contravariant unconstrained type vars.
AM = TypeVar('AM')
AM1 = TypeVar('AM1')
AM2 = TypeVar('AM2')

# Object type vars.
T = TypeVar('T', bound=object)
T1 = TypeVar('T1', bound=object)
T2 = TypeVar('T2', bound=object)
T3 = TypeVar('T3', bound=object)
T4 = TypeVar('T4', bound=object)
T5 = TypeVar('T5', bound=object)
T6 = TypeVar('T6', bound=object)

# Covariant object type vars.
TP = TypeVar('TP', bound=object, covariant=True)
TP1 = TypeVar('TP1', bound=object, covariant=True)
TP2 = TypeVar('TP2', bound=object, covariant=True)

# Contravariant object type vars.
TM = TypeVar('TM', bound=object, contravariant=True)
TM1 = TypeVar('TM1', bound=object, contravariant=True)
TM2 = TypeVar('TM2', bound=object, contravariant=True)

# Additional object type vars whose names may be more suitable depending on the
# context.
# Object type vars for "keys".
K = TypeVar('K', bound=object)
K1 = TypeVar('K1', bound=object)
K2 = TypeVar('K2', bound=object)

# Covariant "key" type vars (note that key type vars are usually invariant or
# contravariant).
KP = TypeVar('KP', bound=object, covariant=True)
KP1 = TypeVar('KP1', bound=object, covariant=True)
KP2 = TypeVar('KP2', bound=object, covariant=True)

# Contravariant "key" type vars.
KM = TypeVar('KM', bound=object, contravariant=True)
KM1 = TypeVar('KM1', bound=object, contravariant=True)
KM2 = TypeVar('KM2', bound=object, contravariant=True)

# Object type vars for "values".
V = TypeVar('V', bound=object)
V1 = TypeVar('V1', bound=object)
V2 = TypeVar('V2', bound=object)
V3 = TypeVar('V3', bound=object)
V4 = TypeVar('V4', bound=object)
V5 = TypeVar('V5', bound=object)
V6 = TypeVar('V6', bound=object)

# Covariant "value" type vars.
VP = TypeVar('VP', bound=object, covariant=True)
VP1 = TypeVar('VP1', bound=object, covariant=True)
VP2 = TypeVar('VP2', bound=object, covariant=True)

# Contravariant "value" type vars (note that value type vars are typically
# invariant or covariant).
VM = TypeVar('VM', bound=object, contravariant=True)
VM1 = TypeVar('VM1', bound=object, contravariant=True)
VM2 = TypeVar('VM2', bound=object, contravariant=True)

# Exception type vars.
E = TypeVar('E', bound=Exception)
E1 = TypeVar('E1', bound=Exception)
E2 = TypeVar('E2', bound=Exception)

# Covariant Exception type vars.
EP = TypeVar('EP', bound=Exception, covariant=True)
EP1 = TypeVar('EP1', bound=Exception, covariant=True)
EP2 = TypeVar('EP2', bound=Exception, covariant=True)

# Contravariant Exception type vars.
EM = TypeVar('EM', bound=Exception, contravariant=True)
EM1 = TypeVar('EM1', bound=Exception, contravariant=True)
EM2 = TypeVar('EM2', bound=Exception, contravariant=True)

#: Type of values that can be caught in an except clause.
Catchable = BaseException | tuple[BaseException, ...]

#: Type of values that can be in a JSON.
JSONType = int | float | str | list['JSONType'] | dict[str, 'JSONType'] | None


class Sentinel:
    """Represents a sentinel object. Has no additional methods or properties."""
