"""AST node classes for the Wyrm 2.3 interpreter."""


class Node:
    pass


class Program(Node):
    def __init__(self, statements):
        self.statements = statements


class NumberLit(Node):
    def __init__(self, value):
        self.value = value


class StringLit(Node):
    def __init__(self, value):
        self.value = value


class BoolLit(Node):
    def __init__(self, value):
        self.value = value


class NullLit(Node):
    pass


class ArrayLit(Node):
    def __init__(self, elements):
        self.elements = elements


class Identifier(Node):
    def __init__(self, name):
        self.name = name


class UnaryOp(Node):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class BinaryOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class LogicalOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class Assign(Node):
    def __init__(self, target, value, declared=False, const=False, owned=False):
        self.target = target  # Identifier or Index
        self.value = value
        self.declared = declared
        self.const = const
        self.owned = owned


class CompoundAssign(Node):
    def __init__(self, target, op, value):
        self.target = target
        self.op = op
        self.value = value


class Index(Node):
    def __init__(self, obj, index):
        self.obj = obj
        self.index = index


class Slice(Node):
    def __init__(self, obj, start, end):
        self.obj = obj
        self.start = start
        self.end = end


class IndexAssign(Node):
    def __init__(self, obj, index, value):
        self.obj = obj
        self.index = index
        self.value = value


class Call(Node):
    def __init__(self, callee, args):
        self.callee = callee
        self.args = args


class MethodCall(Node):
    def __init__(self, obj, method, args):
        self.obj = obj
        self.method = method
        self.args = args


class FuncDef(Node):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body


class Return(Node):
    def __init__(self, value):
        self.value = value


class Break(Node):
    pass


class Continue(Node):
    pass


class If(Node):
    def __init__(self, branches, else_body):
        # branches: list of (condition, body)
        self.branches = branches
        self.else_body = else_body


class DoTil(Node):
    def __init__(self, body, condition):
        self.body = body
        self.condition = condition


class UseStmt(Node):
    def __init__(self, module):
        self.module = module


class UnsafeBlock(Node):
    def __init__(self, body):
        self.body = body


class ArenaDecl(Node):
    def __init__(self, name, size):
        self.name = name
        self.size = size


class ExprStmt(Node):
    def __init__(self, expr):
        self.expr = expr
