from VirtualMachine import VirtualMachine
import types
import inspect


class Function:
    __slots__ = (
        "func_code",
        "func_name",
        "func_defaults",
        "func_globals",
        "func_locals",
        "func_dict",
        "func_closure",
        "__name__",
        "__dict__",
        "__doc__",
        "_vm",
        "_func",
    )

    def __init__(self, name, code, globs, default, closure, vm) -> None:
        self.func_code = code
        self.func_name = self.__name__ = name or code.co_name
        self.func_globals = globs
        self.func_defaults = default
        self.func_closure = closure
        self._vm: VirtualMachine = vm
        self.func_locals = self._vm.frame.f_locals
        self.__dict__ = {}
        self.__doc__ = code.co_consts[0] if code.co_consts else None
        kw = {"argdefs": self.func_defaults}
        if closure:
            kw["closure"] = self.func_globals
        self._func = types.FunctionType(code, globs, **kw)

    def __call__(self, *args, **kwargs):
        call_args = inspect.getcallargs(self._func, *args, **kwargs)

        frame = self._vm.make_frame(self.func_code, call_args, self.func_globals)
        return self._vm.run_code(frame)


def make_cell(value):
    fn = (lambda x: lambda: x)(value)
    return fn.__closure__[0]
