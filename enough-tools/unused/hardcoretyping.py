class _TypeAssignments:
    cache: Final[dict[BaseType, _TypeAssignments]] = {}

    type_args: dict[TypeParam, TypeArg]
    free_params: OrderedSet[TypeParam]
    tuple_args: TypeArgList | None
    generic: bool
    relabeled_params: dict[TypeParam, TypeParam]

    @staticmethod
    def get(typ: BaseType) -> _TypeAssignments:
        if typ in _TypeAssignments.cache:
            return _TypeAssignments.cache[typ]
        else:
            return _TypeAssignments(typ)

    def __init__(self, typ: StdGenericType | None = None) -> None:
        self.type_args = {}
        self.free_params = OrderedSet()
        self.tuple_args = None
        self.relabeled_params = {}
        self.generic = False
        if typ and typ is not object:
            origin, args = _type_arg_split(typ)
            if origin in _DEFAULT_PARAMS:
                self.free_params |= _DEFAULT_PARAMS[origin]
            else:
                if issubclass(typ, Generic):

                for base in _orig_bases(origin):
                    self.merge(self.get(base))
            if args is not None:
                self.cache[origin] = self.copy()
                self.supply_args(args)
            self.cache[typ] = self

    def __getitem__(self, args: TypeArgList) -> _TypeAssignments:
        # Get the result of parameterizing these assignments with the given type arguments.
        cpy = self.copy()
        cpy.supply_args(args)
        return cpy

    def calc_deps(self, param_to_args: dict[TypeParam, list[TypeArg]]) -> dict[TypeParam, set[TypeParam]]:
        # Create a mapping from each constrained type parameter to the other constrained type parameter it depends on.
        param_deps = {}
        for param, values in param_to_args.items():
            # For each constrained parameter, populate its dependency set with the constrained parameters that appear in
            # any of its values.
            deps = set()
            for value in values:
                for p in _get_parameters(value):
                    resolved = self.resolve(p)
                    if resolved in param_to_args:
                        # Save time by excluding free parameters, which of course have no dependencies.
                        deps.add(p)
            param_deps[param] = deps
        return param_deps

    def collect_args(self, other: _TypeAssignments) -> dict[TypeParam, list[TypeArg]]:
        # Collect, in the course of merging, all arguments given to type parameters which have not been relabeled, but
        # which will include type arguments that have been relabeled *to* that parameter.

        # This will contain every parameter that resolves to itself.
        resolve_to_self = []
        param_to_args = {}
        for param in self.free_params:
            resolved = self.resolve(param)
            if resolved == param:
                resolve_to_self.append(param)
            for obj in (self, other):
                # We need to get all values for param in self and other and add them to the list of values for the
                # resolved parameter that need to be checked for consistency.
                if value := obj.type_args.get(param) is not None:
                    param_to_args.setdefault(resolved, []).append(value)

        # The current free parameters are those which resolve to themselves and are not in param_to_args, which contains
        # the constrained parameters.
        self.free_params = OrderedSet(p for p in resolve_to_self if p not in param_to_args)
        return param_to_args

    def copy(self) -> _TypeAssignments:
        # Create a copy of self.
        cpy = _TypeAssignments()
        cpy.type_args = self.type_args.copy()
        cpy.free_params = self.free_params.copy()
        cpy.tuple_args = self.tuple_args  # Immutable tuple of immutable elements.
        cpy.relabeled_params = self.relabeled_params.copy()
        return cpy

    def get_arg(self, param: TypeParam) -> TypeArg | None:
        # Get the argument supplied to the given type parameter, or UNSET if no value has been supplied.
        return self.type_args.get(param)

    def merge(self, other: _TypeAssignments) -> None:
        # Merge the state of type parameter assignments of self and other.

        # Temporarily, this will contain more than just free parameters.
        self.free_params |= other.free_params
        self.merge_labels(other)
        param_to_args = self.collect_args(other)
        param_deps = self.calc_deps(param_to_args)

        # Merge the values of each parameter in topological order.
        # Keep track of what variables we've inferred along the way.
        inferred = OrderedSet()
        for stage in br.dag_stages(param_deps):
            for param in stage:
                self.merge_param_args(param, param_to_args[param], inferred)
        self.merge_tuple_args(other, inferred)
        # Now, substitute all inferred parameters in reverse order. That way, they are prevented from substituting
        # arguments which themselves have inferred parameters.
        for inferred_param in reversed(inferred):
            self.sub_params(inferred_param)
        # Now do the same for all other parameters.
        for param in self.type_args:
            if param not in inferred:
                self.sub_params(param)
        # At last, the merging is complete.

    def merge_args(self, arg1: TypeArg, arg2: TypeArg, inferred: OrderedSet[TypeParam]) -> TypeArg:
        # Merge two type arguments into a single consistent type argument, possibly inferring the arguments to type
        # parameters in the process.
        param, arg = self.param_and_arg(arg1, arg2)
        if param:
            return self.merge_param_with(param, arg, inferred)
        return self.merge_non_params(arg1, arg2, inferred)

    def merge_labels(self, other: _TypeAssignments) -> None:
        # Relabel all relabeled params in other for self.
        for param1, param2 in other.relabeled_params.items():
            self.relabel(param1, param2, False)

    def merge_non_params(self, arg1: BaseType, arg2: BaseType, inferred: OrderedSet[TypeParam]) -> BaseType:
        # Merge two arguments which are not type parameters (but may be parameterized with type parameters).
        origin1, args1 = _type_arg_split(arg1)
        origin2, args2 = _type_arg_split(arg2)
        if origin1 is not origin2:
            # Different types (no attempt is made to reconcile them, i.e. via covariance).
            ...
        if args1 is None and args2 is None:
            # No type args given, return the non-generic origin.
            return origin1
        if args1 is None or args2 is None:
            # Type args given for one but not the other.
            ...
        if len(args1) != len(args2):
            # Unequal length of type arg lists.
            ...
        new_args = tuple(self.merge_args(x, y, inferred) for x, y in zip(args1, args2))
        # noinspection PyUnresolvedReferences
        return origin1[new_args]

    def merge_param_args(self, param: TypeParam, args: list[TypeParam], inferred: OrderedSet[TypeParam]) -> None:
        # Merge the collected arguments for a parameter, which must be consistent.
        self.type_args[param] = functools.reduce(lambda x, y: self.merge_args(x, y, inferred), args)

    def merge_param_with(self, param: TypeParam, arg: TypeArg, inferred: OrderedSet[TypeParam]) -> TypeArg:
        # Merge the given type parameter with the given argument, if both are unset, and return the result. The result
        # will be a type parameter if and only if param was previously a free parameter and arg is None.
        resolved = self.get_arg(param)
        param_val = self.type_args.get(resolved)
        if param_val is not None:
            if arg is None:
                result = param_val
            else:
                result = self.merge_args(param_val, arg, inferred)
        elif arg is not None:
            result = arg
        else:
            # It was and remains a free param.
            return resolved
        # Otherwise, set the new value and return it.
        self.type_args[resolved] = result
        if resolved in self.free_params:
            # Remember that we inferred the value of this parameter.
            inferred.add(resolved)
            self.free_params.remove(resolved)
        return result

    def merge_tuple_args(self, other: _TypeAssignments, inferred: OrderedSet[TypeParam]) -> None:
        # Merge the tuple type arguments of self and other.
        if self.tuple_args is None:
            self.tuple_args = other.tuple_args
        elif other.tuple_args is not None:
            [self.merge_args(x, y, inferred) for x, y in zip(self.tuple_args, other.tuple_args)]

    def param_and_arg(self, arg1: TypeArg, arg2: TypeArg) -> tuple[TypeParam | None, TypeArg | None]:
        # Detect whether at least one of arg1 and arg2 is a type parameter.
        if _is_param(arg1):
            if _is_param(arg2):
                if type(arg1) != type(arg2):
                    # One is a type var and the other is a param spec.
                    ...
                # They parameters need to be equal, relabel one of them (unless they turn out to be equal).
                arg = self.get_arg(arg2)
                self.relabel(arg1, arg2, True)
                return arg1, self.get_arg(arg)
            else:
                return arg1, arg2
        elif _is_param(arg2):
            return arg2, arg1
        return None, None

    def relabel(self, param1: TypeParam, param2: TypeParam, pop_arg: bool) -> None:
        # Relabel a type parameter in the course of merging type arguments.
        # Relabel the later parameters in free_params to the earlier ones for consistency reasons.
        from_param, to_param = self.resolve(param1), self.resolve(param2)
        if from_param == to_param:
            return
        if from_param in self.free_params:
            if to_param in self.free_params:
                if self.free_params.index(from_param) < self.free_params.index(to_param):
                    from_param, to_param = param2, param1
                self.free_params.remove(from_param)
        self.relabeled_params[from_param] = to_param
        if pop_arg:
            self.type_args.pop(from_param, None)

    def resolve(self, param: TypeParam) -> TypeParam:
        # Resolve the actual type parameter for a parameter that may have been relabeled.
        params_to_remap = []
        while param in self.relabeled_params:
            params_to_remap.append(param)
            param = self.relabeled_params[param]
        for p in params_to_remap:
            # Give these parameters a more efficient route to their resolution.
            self.relabeled_params[p] = param
        return param

    def sub_params(self, param: TypeParam) -> None:
        # Substitute all constrained variables appearing in the argument of param.
        arg = self.type_args[param]
        params = (self.get_arg(p) if p in self.type_args else p for p in _get_parameters(arg))
        if params:
            self.type_args[param] = arg[params]

    def supply_args(self, args: TypeArgList) -> None:
        # Give arguments for the remaining free parameters in self.
        if len(args) != len(self.free_params):
            ...
        self.free_params.clear()
        param_to_arg = dict(zip(self.free_params, args))
        for param in self.type_args:
            arg = self.type_args[param]
            params = tuple(param_to_arg[p] for p in _get_parameters(arg))
            self.type_args[param] = arg[params]