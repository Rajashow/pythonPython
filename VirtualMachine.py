from block import Block
from frame import Frame
from function import Function
import dis
import operator
import sys


class VirtualMachine:
    UNARY_OPERATORS = {
        "POSITIVE": operator.pos,
        "NEGATIVE": operator.neg,
        "NOT": operator.not_,
        "CONVERT": repr,
        "INVERT": operator.invert,
    }
    BINARY_OPERATORS = {
        "POWER": pow,
        "MULTIPLY": operator.mul,
        "FLOOR_DIVIDE": operator.floordiv,
        "TRUE_DIVIDE": operator.truediv,
        "MODULO": operator.mod,
        "ADD": operator.add,
        "SUBTRACT": operator.sub,
        "SUBSCR": operator.getitem,
        "LSHIFT": operator.lshift,
        "RSHIFT": operator.rshift,
        "AND": operator.and_,
        "XOR": operator.xor,
        "OR": operator.or_,
    }
    COMPARE_OPERATORS = (
        operator.lt,
        operator.le,
        operator.eq,
        operator.ne,
        operator.gt,
        operator.ge,
        lambda x, y: x in y,
        lambda x, y: x not in y,
        lambda x, y: x is y,
        lambda x, y: x is not y,
        lambda x, y: issubclass(x, Exception) and issubclass(x, y),
    )

    def byte_LOAD_CONST(self, const):
        self.push(const)

    def byte_POP_TOP(self):
        self.pop()

    def byte_LOAD_NAME(self, name):
        frame = self.frame
        if name in frame.f_locals:
            val = frame.f_locals[name]
        elif name in frame.f_globals:
            val = frame.f_globals[name]
        elif name in frame.f_builtins:
            val = frame.f_builtins[name]
        else:
            raise NameError("name '%s' is not defined" % name)
        self.push(val)

    def byte_STORE_NAME(self, name):
        self.frame.f_locals[name] = self.pop()

    def byte_LOAD_FAST(self, name):
        if name in self.frame.f_locals:
            val = self.frame.f_locals[name]
        else:
            raise UnboundLocalError(
                "local variable '%s' referenced before assignment" % name
            )
        self.push(val)

    def byte_STORE_FAST(self, name):
        self.frame.f_locals[name] = self.pop()

    def byte_LOAD_GLOBAL(self, name):
        f = self.frame
        if name in f.f_globals:
            val = f.f_globals[name]
        elif name in f.f_builtins:
            val = f.f_builtins[name]
        else:
            raise NameError("global name '%s' is not defined" % name)
        self.push(val)

    def unaryOperator(self, op):
        x = self.pop()
        self.push(VirtualMachine.UNARY_OPERATORS[op](x))

    def binaryOperator(self, op):
        x, y = self.popn(2)
        self.push(VirtualMachine.BINARY_OPERATORS[op](x, y))

    def byte_COMPARE_OP(self, opnum):
        x, y = self.popn(2)
        self.push(VirtualMachine.COMPARE_OPERATORS[opnum](x, y))

    def byte_LOAD_ATTR(self, attr):
        obj = self.pop()
        val = getattr(obj, attr)
        self.push(val)

    def byte_STORE_ATTR(self, name):
        val, obj = self.popn(2)
        setattr(obj, name, val)

    def byte_BUILD_LIST(self, count):
        elts = self.popn(count)
        self.push(elts)

    def byte_BUILD_MAP(self, size):
        self.push({})

    def byte_STORE_MAP(self):
        the_map, val, key = self.popn(3)
        the_map[key] = val
        self.push(the_map)

    def byte_LIST_APPEND(self, count):
        val = self.pop()
        the_list = self.frame.stack[-count]  # peek
        the_list.append(val)

    def byte_JUMP_FORWARD(self, jump):
        self.jump(jump)

    def byte_JUMP_ABSOLUTE(self, jump):
        self.jump(jump)

    def byte_POP_JUMP_IF_TRUE(self, jump):
        val = self.pop()
        if val:
            self.jump(jump)

    def byte_POP_JUMP_IF_FALSE(self, jump):
        val = self.pop()
        if not val:
            self.jump(jump)

    def byte_SETUP_LOOP(self, dest):
        self.push_block("loop", dest)

    def byte_GET_ITER(self):
        self.push(iter(self.pop()))

    def byte_FOR_ITER(self, jump):
        iterobj = self.top()
        try:
            v = next(iterobj)
            self.push(v)
        except StopIteration:
            self.pop()
            self.jump(jump)

    def byte_BREAK_LOOP(self):
        return "break"

    def byte_POP_BLOCK(self):
        self.pop_block()

    def byte_MAKE_FUNCTION(self, argc):
        name = self.pop()
        code = self.pop()
        defaults = self.popn(argc)
        globs = self.frame.f_globals
        fn = Function(name, code, globs, defaults, None, self)
        self.push(fn)

    def byte_CALL_FUNCTION(self, arg):
        _lenKw, lenPos = divmod(arg, 256)  # KWargs not supported here
        posargs = self.popn(lenPos)

        func = self.pop()
        _frame = self.frame
        retval = func(*posargs)
        self.push(retval)

    def byte_RETURN_VALUE(self):
        self.return_value = self.pop()
        return "return"

    def jump(self, jump):
        self.frame.f_lasti = jump

    def top(self):
        return self.frame.stack[-1]

    def pop(self):
        return self.frame.stack.pop()

    def push(self, *values):
        self.frame.stack.extend(values)

    def popn(self, n):
        if n:
            return_val = self.frame.stack[-n:]
            self.frame.stack[-n:] = []
            return return_val
        return []

    def push_frame(self, frame):
        self.frames.append(frame)
        self.frame = frame

    def pop_frame(self):
        return_value = self.frames.pop()
        if self.frames:
            self.frame = self.frames[-1]
        else:
            self.frame = None
        return return_value

    def push_block(self, b_type, handler=None):
        stack_height = len(self.frame.stack)
        self.frame.block_stack.append(Block(b_type, handler, stack_height))

    def pop_block(self):
        return self.frame.block_stack.pop()

    def unwind_block(self, block):
        if block.type == "except-handler":
            offest = 3  # expection contain a type,value, traceback
        else:
            offest = 0
        while len(self.frame.stack) > block.level + offest:
            self.pop()
        if block.type == "except-handler":
            traceback, value, exctype = self.popn(3)
            self.last_exception = exctype, value, traceback

    def manage_block_stack(self, why):
        frame = self.frame
        block = frame.block_stack[-1]
        if block.type == "loop" and why == "continue":
            self.jump(self.return_value)
            why = None
            return why
        self.pop_block()
        self.unwind_block(block)

        if block.type == "loop" and why == "break":
            why = None
            self.jump(block.handler)
            return why

        if block.type in ("setup-except", "finally",) and why == "exception":
            self.push_block("except-handler")
            assert self.last_exception is not None
            exctype, value, traceback = self.last_exception
            self.push(traceback, value, exctype)
            self.push(traceback, value, exctype)  # need to push it twice
            why = None
            self.jump(block.handler)
            return None
        elif block.type == "finally":
            if why in ("return", "continue"):
                self.push(self.return_value)
            self.push(why)
            why = None
            self.jump(block.handler)
            return why
        return why

    def __init__(self) -> None:
        self.frames = []
        self.frame = None
        self.return_value = None
        self.last_exception = None

    def run_code(self, code, global_names=None, local_names=None):
        frame = self.make_frame(
            code=code, global_names=global_names, local_names=local_names
        )
        self.run_frame(frame)

    def make_frame(self, code, call_args={}, global_names=None, local_names=None):
        if global_names is not None and local_names is not None:
            local_names = global_names
        elif self.frames:
            global_names = self.frame.global_names
            local_names = {}
        else:
            global_names = local_names = {
                "__builtins__": "__builtins__",
                "__name__": "__main__",
                "__doc__": None,
                "__package": None,
            }
        local_names.update(call_args)
        frame = Frame(code, global_names, local_names, self.frame)
        return frame

    def parse_byte_and_args(self):
        f = self.frame
        opoffset = f.last_instruction
        byteCode = f.code_ob.co_code[opoffset]
        f.last_instruction += 1
        byte_name = dis.opname[byteCode]
        if byteCode >= dis.HAVE_ARGUMENT:
            arg = f.code_obj.co_code[f.last_instruction : f.last_instruction + 2]
            f.last_instruction += 2
            arg_val = arg[0] + (arg[-1] * 256)
            if byteCode in dis.hasconst:
                arg = f.code_obj.co_consts[arg_val]
            elif byteCode in dis.hasname:
                arg = f.code_obj.co_names[arg_val]
            elif byteCode in dis.haslocal:
                arg = f.code_obj.co_varnames[arg_val]
            elif byteCode in dis.hasjrel:  # relative jump
                arg = f.last_instruction + arg_val
            else:
                arg = arg_val
            argument = [arg]
        else:
            argument = []

        return byte_name, argument

    def dispatch(self, byte_name, argument):
        why = None
        try:
            bytecode_fn = getattr(self, f"byte_{byte_name}", None)
            if bytecode_fn is None:
                if byte_name.startswith("UNARY_"):
                    self.unaryOperator(byte_name[6:])
                elif byte_name.startswith("BINARY_"):
                    self.binaryOperator(byte_name[7:])
                else:
                    raise ValueError(
                        f"Virtual Machine Error: unsupported bytecode type:{byte_name}"
                    )
            else:
                why = bytecode_fn(*argument)
        except:
            self.last_reception = sys.exc_info()[:2] + (None,)
            why = "excpetion"
        return why

    def run_frame(self, frame):
        self.push_frame(frame)
        why = None
        while not why:
            byte_name, arguments = self.parse_byte_and_args()
            why = self.dispatch(byte_name, arguments)
            while why and frame.block_stack:
                why = self.manage_block_stack(why)

        self.pop_frame()
        if why == "exception":
            assert self.last_exception is not None
            exc, val, tb = self.last_exception
            e = exc(val)
            e.__traceback__ = tb
            raise e
        return self.return_value
