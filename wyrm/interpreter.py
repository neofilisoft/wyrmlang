"""Wyrm 2.3 tree-walking interpreter.

Designed to run inside Pyodide in the browser. Because `input()` needs to
await a JS-side prompt, the whole interpreter is written with async
functions; a synchronous host (e.g. CPython on the command line) can drive
it with asyncio.run(), and Pyodide can `await` it directly since Pyodide's
webloop supports top-level await of coroutines.
"""

from .ast import (
    Program, NumberLit, StringLit, BoolLit, NullLit, ArrayLit, Identifier,
    UnaryOp, BinaryOp, LogicalOp, Assign, CompoundAssign, Index, Slice, IndexAssign,
    Call, MethodCall, FuncDef, Return, Break, Continue, If, DoTil, UseStmt,
    UnsafeBlock, ArenaDecl, ExprStmt,
)
from .environment import Environment, WyrmRuntimeError


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class WyrmFunction:
    __slots__ = ("name", "params", "body", "closure")

    def __init__(self, name, params, body, closure):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure


class Arena:
    """Simplified arena stand-in: browser sandbox has no raw memory, so
    arena/alloc/unsafe/malloc are modeled as an in-memory list-backed
    allocator purely for program-visible behavior (values, not addresses)."""

    def __init__(self, size):
        self.size = size
        self.used = 0
        self.blocks = []

    def alloc(self, n):
        if self.used + n > self.size:
            raise WyrmRuntimeError("Arena out of memory")
        block = [0] * n
        self.blocks.append(block)
        self.used += n
        return block

    def reset(self):
        self.used = 0
        self.blocks = []


def wyrm_type_name(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, WyrmFunction):
        return "function"
    return "object"


def wyrm_str(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return f"{v:.1f}"
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(wyrm_repr(e) for e in v) + "]"
    return str(v)


def wyrm_repr(v):
    if isinstance(v, str):
        return '"' + v + '"'
    return wyrm_str(v)


def is_truthy(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return len(v) > 0
    if isinstance(v, list):
        return len(v) > 0
    return True


class Interpreter:
    def __init__(self, output=None, input_fn=None):
        """output: callable(str) -> None, called for each print().
        input_fn: async callable(prompt:str) -> str, called for input()."""
        self.globals = Environment()
        self._output = output or (lambda s: None)
        self._input_fn = input_fn
        self.modules_loaded = set()

    def write(self, s):
        self._output(s)

    async def run(self, program: Program):
        env = self.globals
        # First pass: hoist function definitions so calls can appear before
        # their textual definition (matches C-like forward reference).
        for stmt in program.statements:
            if isinstance(stmt, FuncDef):
                env.declare(stmt.name, WyrmFunction(stmt.name, stmt.params, stmt.body, env))

        # Execute top-level statements in order (functions already hoisted,
        # skip re-declaring but still allow other top-level side effects).
        for stmt in program.statements:
            if isinstance(stmt, FuncDef):
                continue
            await self.exec_stmt(stmt, env)

        if env.has("main"):
            main_fn = env.get("main")
            if isinstance(main_fn, WyrmFunction):
                await self.call_function(main_fn, [])

    # -- statement execution -------------------------------------------
    async def exec_block(self, stmts, env):
        for stmt in stmts:
            await self.exec_stmt(stmt, env)

    async def exec_stmt(self, node, env):
        t = type(node)

        if t is ExprStmt:
            await self.eval(node.expr, env)
            return

        if t is Assign:
            value = await self.eval(node.value, env)
            env.declare(node.target.name, value, const=node.const) if node.declared else env.set(node.target.name, value)
            return

        if t is CompoundAssign:
            cur = await self.eval(node.target, env)
            rhs = await self.eval(node.value, env)
            result = self._apply_binop(node.op, cur, rhs)
            if isinstance(node.target, Identifier):
                env.set(node.target.name, result)
            elif isinstance(node.target, Index):
                obj = await self.eval(node.target.obj, env)
                idx = await self.eval(node.target.index, env)
                obj[int(idx)] = result
            return

        if t is IndexAssign:
            obj = await self.eval(node.obj, env)
            idx = await self.eval(node.index, env)
            value = await self.eval(node.value, env)
            if not isinstance(obj, list):
                raise WyrmRuntimeError("Cannot index-assign a non-array value")
            i = int(idx)
            if i < 0:
                i += len(obj)
            if i < 0 or i >= len(obj):
                raise WyrmRuntimeError(f"Index {idx} out of range")
            obj[i] = value
            return

        if t is FuncDef:
            env.declare(node.name, WyrmFunction(node.name, node.params, node.body, env))
            return

        if t is If:
            for cond, body in node.branches:
                if is_truthy(await self.eval(cond, env)):
                    await self.exec_block(body, Environment(env))
                    return
            if node.else_body:
                await self.exec_block(node.else_body, Environment(env))
            return

        if t is DoTil:
            while True:
                loop_env = Environment(env)
                try:
                    await self.exec_block(node.body, loop_env)
                except BreakSignal:
                    break
                except ContinueSignal:
                    pass
                if is_truthy(await self.eval(node.condition, env)):
                    break
            return

        if t is Return:
            value = await self.eval(node.value, env) if node.value is not None else None
            raise ReturnSignal(value)

        if t is Break:
            raise BreakSignal()

        if t is Continue:
            raise ContinueSignal()

        if t is UnsafeBlock:
            await self.exec_block(node.body, Environment(env))
            return

        if t is ArenaDecl:
            size = await self.eval(node.size, env)
            env.declare(node.name, Arena(int(size)))
            return

        if t is UseStmt:
            # Browser sandbox has no filesystem; modules are a no-op here
            # (matches "playground" scope — real multi-file builds happen
            # via the native wyrmc toolchain).
            self.modules_loaded.add(node.module)
            return

        raise WyrmRuntimeError(f"Unknown statement node: {t}")

    # -- expression evaluation ------------------------------------------
    async def eval(self, node, env):
        t = type(node)

        if t is NumberLit:
            return node.value
        if t is StringLit:
            return node.value
        if t is BoolLit:
            return node.value
        if t is NullLit:
            return None
        if t is ArrayLit:
            return [await self.eval(e, env) for e in node.elements]
        if t is Identifier:
            return env.get(node.name)

        if t is UnaryOp:
            val = await self.eval(node.operand, env)
            if node.op in ("!", "not"):
                return not is_truthy(val)
            if node.op == "-":
                return -val
            if node.op == "+":
                return +val
            raise WyrmRuntimeError(f"Unknown unary operator {node.op}")

        if t is LogicalOp:
            left = await self.eval(node.left, env)
            if node.op == "||":
                if is_truthy(left):
                    return left
                return await self.eval(node.right, env)
            else:  # &&
                if not is_truthy(left):
                    return left
                return await self.eval(node.right, env)

        if t is BinaryOp:
            left = await self.eval(node.left, env)
            right = await self.eval(node.right, env)
            return self._apply_binop(node.op, left, right)

        if t is Index:
            obj = await self.eval(node.obj, env)
            idx = await self.eval(node.index, env)
            return self._do_index(obj, idx)

        if t is Slice:
            obj = await self.eval(node.obj, env)
            start = int(await self.eval(node.start, env)) if node.start is not None else None
            end = int(await self.eval(node.end, env)) if node.end is not None else None
            if not isinstance(obj, (list, str)):
                raise WyrmRuntimeError(f"Cannot slice value of type {wyrm_type_name(obj)}")
            return obj[start:end]

        if t is Call:
            return await self.call_named(node.callee, node.args, env)

        if t is MethodCall:
            obj = env.get(node.obj.name) if isinstance(node.obj, Identifier) else await self.eval(node.obj, env)
            args = [await self.eval(a, env) for a in node.args]
            return self._call_method(obj, node.method, args)

        raise WyrmRuntimeError(f"Unknown expression node: {t}")

    def _do_index(self, obj, idx):
        if isinstance(obj, (list, str)):
            i = int(idx)
            if i < 0:
                i += len(obj)
            if i < 0 or i >= len(obj):
                raise WyrmRuntimeError(f"Index {idx} out of range")
            return obj[i]
        raise WyrmRuntimeError(f"Cannot index value of type {wyrm_type_name(obj)}")

    def _call_method(self, obj, method, args):
        if isinstance(obj, Arena):
            if method == "alloc":
                return obj.alloc(int(args[0]))
            if method == "reset":
                obj.reset()
                return None
            raise WyrmRuntimeError(f"Unknown arena method '{method}'")
        raise WyrmRuntimeError(f"Cannot call method '{method}' on {wyrm_type_name(obj)}")

    def _apply_binop(self, op, left, right):
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return wyrm_str(left) + wyrm_str(right) if not (isinstance(left, str) and isinstance(right, str)) else left + right
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise WyrmRuntimeError("Division by zero")
            result = left / right
            if isinstance(left, int) and isinstance(right, int) and left % right == 0:
                return left // right
            return result
        if op == "//":
            if right == 0:
                raise WyrmRuntimeError("Division by zero")
            return left // right
        if op == "%":
            if right == 0:
                raise WyrmRuntimeError("Modulo by zero")
            return left % right
        if op == "**":
            return left ** right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        raise WyrmRuntimeError(f"Unknown binary operator {op}")

    # -- calls -----------------------------------------------------------
    async def call_named(self, name, arg_nodes, env):
        args = [await self.eval(a, env) for a in arg_nodes]

        if name == "print":
            self.write(" ".join(wyrm_str(a) for a in args) + "\n")
            return None

        if name == "input":
            prompt = args[0] if args else ""
            if self._input_fn is None:
                raise WyrmRuntimeError("input() is not available in this environment")
            return await self._input_fn(wyrm_str(prompt))

        builtin = BUILTINS.get(name)
        if builtin is not None:
            return builtin(args)

        if env.has(name):
            fn = env.get(name)
            if isinstance(fn, WyrmFunction):
                return await self.call_function(fn, args)
            raise WyrmRuntimeError(f"'{name}' is not a function")

        raise WyrmRuntimeError(f"Undefined function '{name}'")

    async def call_function(self, fn: WyrmFunction, args):
        call_env = Environment(fn.closure)
        for i, pname in enumerate(fn.params):
            call_env.declare(pname, args[i] if i < len(args) else None)
        try:
            await self.exec_block(fn.body, call_env)
        except ReturnSignal as r:
            return r.value
        return None


# -- builtins (synchronous; input/print handled specially above) --------

def _b_len(args):
    v = args[0]
    if isinstance(v, (list, str)):
        return len(v)
    raise WyrmRuntimeError("len() expects an array or string")


def _b_str(args):
    return wyrm_str(args[0])


def _b_int(args):
    v = args[0]
    if isinstance(v, str):
        return int(v.strip())
    return int(v)


def _b_float(args):
    v = args[0]
    if isinstance(v, str):
        return float(v.strip())
    return float(v)


def _b_type(args):
    return wyrm_type_name(args[0])


def _b_abs(args):
    return abs(args[0])


def _b_max(args):
    if len(args) == 1 and isinstance(args[0], list):
        return max(args[0])
    return max(args)


def _b_min(args):
    if len(args) == 1 and isinstance(args[0], list):
        return min(args[0])
    return min(args)


def _b_round(args):
    if len(args) > 1:
        return round(args[0], int(args[1]))
    return round(args[0])


def _b_pow(args):
    return args[0] ** args[1]


def _b_append(args):
    arr, val = args[0], args[1]
    if not isinstance(arr, list):
        raise WyrmRuntimeError("append() expects an array")
    arr.append(val)
    return arr


def _b_pop(args):
    arr = args[0]
    if not isinstance(arr, list):
        raise WyrmRuntimeError("pop() expects an array")
    if not arr:
        raise WyrmRuntimeError("pop() from empty array")
    if len(args) > 1:
        return arr.pop(int(args[1]))
    return arr.pop()


def _b_split(args):
    s, sep = args[0], args[1]
    return s.split(sep)


def _b_join(args):
    sep, lst = args[0], args[1]
    return sep.join(wyrm_str(x) if not isinstance(x, str) else x for x in lst)


def _b_trim(args):
    return args[0].strip()


def _b_upper(args):
    return args[0].upper()


def _b_lower(args):
    return args[0].lower()


def _b_contains(args):
    s, sub = args[0], args[1]
    if isinstance(s, list):
        return sub in s
    return sub in s


def _b_replace(args):
    s, old, new = args[0], args[1], args[2]
    return s.replace(old, new)


def _b_starts_with(args):
    return args[0].startswith(args[1])


def _b_ends_with(args):
    return args[0].endswith(args[1])


def _b_char_at(args):
    s, i = args[0], int(args[1])
    if i < 0 or i >= len(s):
        raise WyrmRuntimeError(f"Index {i} out of range")
    return s[i]


def _b_ord_val(args):
    return ord(args[0])


def _b_chr_val(args):
    return chr(int(args[0]))


def _b_to_bytes(args):
    return [ord(c) for c in args[0]]


def _b_from_bytes(args):
    return "".join(chr(int(b)) for b in args[0])


def _b_malloc(args):
    n = int(args[0])
    return [0] * n


def _b_free(args):
    return None


def _b_realloc(args):
    arr, n = args[0], int(args[1])
    if not isinstance(arr, list):
        raise WyrmRuntimeError("realloc() expects a pointer-like array")
    if n >= len(arr):
        return arr + [0] * (n - len(arr))
    return arr[:n]


BUILTINS = {
    "len": _b_len,
    "str": _b_str,
    "int": _b_int,
    "float": _b_float,
    "type": _b_type,
    "abs": _b_abs,
    "max": _b_max,
    "min": _b_min,
    "round": _b_round,
    "pow": _b_pow,
    "append": _b_append,
    "pop": _b_pop,
    "split": _b_split,
    "join": _b_join,
    "trim": _b_trim,
    "upper": _b_upper,
    "lower": _b_lower,
    "contains": _b_contains,
    "replace": _b_replace,
    "starts_with": _b_starts_with,
    "ends_with": _b_ends_with,
    "char_at": _b_char_at,
    "ord_val": _b_ord_val,
    "chr_val": _b_chr_val,
    "to_bytes": _b_to_bytes,
    "from_bytes": _b_from_bytes,
    "malloc": _b_malloc,
    "free": _b_free,
    "realloc": _b_realloc,
}
