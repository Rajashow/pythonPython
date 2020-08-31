class Interpreter:
    def __init__(self) -> None:
        self.stack = []
        self.environment = {}

    def STORE_NAME(self, name):
        self.environment[name] = self.stack.pop()

    def LOAD_NAME(self, name):
        self.stack.append(self.environment[name])

    def LOAD_VALUE(self, value):
        self.stack.append(value)

    def PRINT_ANSWER(self):
        print(self.stack.pop())

    def ADD_TWO_VALUES(self):
        v2, v1 = self.stack.pop(), self.stack.pop()
        self.stack.append(v1 + v2)

    def execute(self, what_to_execute):
        instructions = what_to_execute["instructions"]
        for each_step in instructions:
            instruction, argument = each_step
            argument = self.parse_argument(instruction, argument, what_to_execute)
            bytecode_method = getattr(self, instruction)
            if argument is None:
                bytecode_method()
            else:
                bytecode_method(argument)


what_to_execute = {
    "instructions": [
        ("LOAD_VALUE", 0),
        ("STORE_NAME", 0),
        ("LOAD_VALUE", 1),
        ("STORE_NAME", 1),
        ("LOAD_NAME", 0),
        ("LOAD_NAME", 1),
        ("ADD_TWO_VALUES", None),
        ("PRINT_ANSWER", None),
    ],
    "numbers": [1, 2],
    "names": ["a", "b"],
}
interpreter = Interpreter()
interpreter.execute(what_to_execute)
