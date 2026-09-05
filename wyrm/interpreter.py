"""Wyrm v3.1.0 tree-walking interpreter.

Designed to run inside Pyodide in the browser. Supports async input(),
Structs & Methods, Gradual Static Typing annotations, Standard Library
modules (std.json, std.yaml, std.collections), and Arena memory allocators.
"""

import json
from .ast import (
    Program, NumberLit, StringLit, BoolLit, NullLit, ArrayLit, Identifier,
    UnaryOp, BinaryOp, LogicalOp, Assign, CompoundAssign, Index, Slice, IndexAssign,
    MemberAccess, MemberAssign, Call, MethodCall, FuncDef, StructDef, Return,
    Break, Continue, If, DoTil, UseStmt, UnsafeBlock, ArenaDecl, ExprStmt,
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
    __slots__ = ("name", "params", "body", "closure", "param_types", "return_type")

    def __init__(self, name, params, body, closure, param_types=None, return_type=None):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.param_types = param_types or {}
        self.return_type = return_type


class WyrmStructDef:
    __slots__ = ("name", "fields", "methods", "field_types")

    def __init__(self, name, fields, methods, field_types=None):
        self.name = name
        self.fields = fields
        self.methods = {m.name: m for m in methods}
        self.field_types = field_types or {}


class WyrmStructInstance:
    __slots__ = ("struct_def", "fields")

    def __init__(self, struct_def, fields):
        self.struct_def = struct_def
        self.fields = fields

    def get_field(self, name):
        if name in self.fields:
            return self.fields[name]
        raise WyrmRuntimeError(f"Field '{name}' not found on struct '{self.struct_def.name}'")

    def set_field(self, name, value):
        self.fields[name] = value

    def __repr__(self):
        f_str = ", ".join(f"{k}: {wyrm_repr(v)}" for k, v in self.fields.items())
        return f"{self.struct_def.name}{{{f_str}}}"


class Arena:
    """Arena memory allocator for linear allocation and bulk reset."""

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
        return None


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
    if isinstance(v, dict):
        return "map"
    if isinstance(v, WyrmStructInstance):
        return v.struct_def.name
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
    if isinstance(v, dict):
        entries = [f'"{k}": {wyrm_repr(val)}' for k, val in v.items()]
        return "{" + ", ".join(entries) + "}"
    if isinstance(v, WyrmStructInstance):
        return repr(v)
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
    if isinstance(v, (str, list, dict)):
        return len(v) > 0
    return True


# -- Pure Python YAML Helper ------------------------------------------

def simple_yaml_parse(text):
    """Simple block-style YAML parser supporting key-value, lists, and numbers."""
    lines = text.strip().splitlines()
    result = {}
    current_key = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            parts = line.split(":", 1)
            k = parts[0].strip()
            val_str = parts[1].strip()
            if val_str == "":
                current_key = k
                result[k] = []
            else:
                current_key = None
                if val_str.lower() == "true":
                    result[k] = True
                elif val_str.lower() == "false":
                    result[k] = False
                elif val_str.lower() in ("null", "~"):
                    result[k] = None
                else:
                    try:
                        result[k] = int(val_str) if "." not in val_str else float(val_str)
                    except ValueError:
                        result[k] = val_str.strip('"').strip("'")
        elif line.startswith("-") and current_key is not None:
            item = line[1:].strip().strip('"').strip("'")
            try:
                item_val = int(item) if "." not in item else float(item)
            except ValueError:
                item_val = item
            result[current_key].append(item_val)
    return result


def simple_yaml_encode(obj):
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, list):
                lines.append(f"{k}:")
                for item in v:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
    return "\n".join(lines)


# -- Interpreter ------------------------------------------------------

class Interpreter:
    def __init__(self, output=None, input_fn=None):
        self.globals = Environment()
        self._output = output or (lambda s: None)
        self._input_fn = input_fn
        self.modules_loaded = set()
        self._init_stdlib()

    def write(self, s):
        self._output(s)

    def _init_stdlib(self):
        # Always available built-in functions
        for name, fn in BUILTINS.items():
            self.globals.declare(name, fn)

    def load_module(self, mod_name):
        if mod_name in self.modules_loaded:
            return
        self.modules_loaded.add(mod_name)

        if mod_name == "std.json":
            self.globals.declare("json_parse", lambda args: json.loads(args[0]))
            self.globals.declare("json_encode", lambda args: json.dumps(args[0], separators=(',', ':')))
            self.globals.declare("json_pretty", lambda args: json.dumps(args[0], indent=int(args[1]) if len(args) > 1 else 2))

        elif mod_name == "std.yaml":
            self.globals.declare("yaml_parse", lambda args: simple_yaml_parse(args[0]))
            self.globals.declare("yaml_encode", lambda args: simple_yaml_encode(args[0]))

        elif mod_name == "std.collections":
            self.globals.declare("map_new", lambda args: {})
            self.globals.declare("map_set", lambda args: args[0].__setitem__(args[1], args[2]))
            self.globals.declare("map_get", lambda args: args[0].get(args[1], None))
            self.globals.declare("map_has", lambda args: args[1] in args[0])
            self.globals.declare("map_len", lambda args: len(args[0]))
            self.globals.declare("set_new", lambda args: set())
            self.globals.declare("set_add", lambda args: args[0].add(args[1]))
            self.globals.declare("set_has", lambda args: args[1] in args[0])

        elif mod_name in ("std.sdl", "std.ffi", "std.thread"):
            # Browser sandbox stubs to avoid runtime crashes
            pass

    async def run(self, program: Program):
        env = self.globals
        # First pass: hoist function & struct definitions
        for stmt in program.statements:
            if isinstance(stmt, FuncDef):
                env.declare(stmt.name, WyrmFunction(stmt.name, stmt.params, stmt.body, env, stmt.param_types, stmt.return_type))
            elif isinstance(stmt, StructDef):
                env.declare(stmt.name, WyrmStructDef(stmt.name, stmt.fields, stmt.methods, stmt.field_types))

        # Execute top-level statements
        for stmt in program.statements:
            if isinstance(stmt, (FuncDef, StructDef)):
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
            if node.declared:
                env.declare(node.target.name, value, const=node.const)
            else:
                env.set(node.target.name, value)
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
                if isinstance(obj, dict):
                    obj[idx] = result
                elif isinstance(obj, list):
                    obj[int(idx)] = result
            elif isinstance(node.target, MemberAccess):
                obj = await self.eval(node.target.obj, env)
                if isinstance(obj, WyrmStructInstance):
                    obj.set_field(node.target.member, result)
                elif isinstance(obj, dict):
                    obj[node.target.member] = result
            return

        if t is IndexAssign:
            obj = await self.eval(node.obj, env)
            idx = await self.eval(node.index, env)
            value = await self.eval(node.value, env)
            if isinstance(obj, dict):
                obj[idx] = value
                return
            if isinstance(obj, list):
                i = int(idx)
                if i < 0:
                    i += len(obj)
                if i < 0 or i >= len(obj):
                    raise WyrmRuntimeError(f"Index {idx} out of range")
                obj[i] = value
                return
            raise WyrmRuntimeError("Cannot index-assign a non-array / non-map value")

        if t is MemberAssign:
            obj = await self.eval(node.obj, env)
            val = await self.eval(node.value, env)
            if isinstance(obj, WyrmStructInstance):
                obj.set_field(node.member, val)
                return
            if isinstance(obj, dict):
                obj[node.member] = val
                return
            raise WyrmRuntimeError(f"Cannot set field '{node.member}' on type {wyrm_type_name(obj)}")

        if t is FuncDef:
            env.declare(node.name, WyrmFunction(node.name, node.params, node.body, env, node.param_types, node.return_type))
            return

        if t is StructDef:
            env.declare(node.name, WyrmStructDef(node.name, node.fields, node.methods, node.field_types))
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
            self.load_module(node.module)
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

        if t is MemberAccess:
            obj = await self.eval(node.obj, env)
            if isinstance(obj, WyrmStructInstance):
                return obj.get_field(node.member)
            if isinstance(obj, dict):
                return obj.get(node.member, None)
            raise WyrmRuntimeError(f"Cannot access member '{node.member}' on type {wyrm_type_name(obj)}")

        if t is Call:
            return await self.call_named(node.callee, node.args, env)

        if t is MethodCall:
            obj = await self.eval(node.obj, env)
            args = [await self.eval(a, env) for a in node.args]
            return await self._call_method(obj, node.method, args)

        raise WyrmRuntimeError(f"Unknown expression node: {t}")

    def _do_index(self, obj, idx):
        if isinstance(obj, dict):
            return obj.get(idx, None)
        if isinstance(obj, (list, str)):
            i = int(idx)
            if i < 0:
                i += len(obj)
            if i < 0 or i >= len(obj):
                raise WyrmRuntimeError(f"Index {idx} out of range")
            return obj[i]
        raise WyrmRuntimeError(f"Cannot index value of type {wyrm_type_name(obj)}")

    async def _call_method(self, obj, method_name, args):
        if isinstance(obj, WyrmStructInstance):
            if method_name not in obj.struct_def.methods:
                raise WyrmRuntimeError(f"Method '{method_name}' not found on struct '{obj.struct_def.name}'")
            fn_def = obj.struct_def.methods[method_name]
            call_env = Environment(self.globals)
            call_env.declare("self", obj)
            # Map parameters: if first param is "self", match subsequent params
            param_names = fn_def.params[1:] if (fn_def.params and fn_def.params[0] == "self") else fn_def.params
            for i, pname in enumerate(param_names):
                call_env.declare(pname, args[i] if i < len(args) else None)
            try:
                await self.exec_block(fn_def.body, call_env)
            except ReturnSignal as r:
                return r.value
            return None

        if isinstance(obj, Arena):
            if method_name == "alloc":
                return obj.alloc(int(args[0]))
            if method_name == "reset":
                return obj.reset()
            raise WyrmRuntimeError(f"Unknown arena method '{method_name}'")

        raise WyrmRuntimeError(f"Cannot call method '{method_name}' on {wyrm_type_name(obj)}")

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

        # Struct constructor
        if env.has(name):
            val = env.get(name)
            if isinstance(val, WyrmStructDef):
                field_vals = {}
                for i, fname in enumerate(val.fields):
                    field_vals[fname] = args[i] if i < len(args) else None
                return WyrmStructInstance(val, field_vals)
            if isinstance(val, WyrmFunction):
                return await self.call_function(val, args)
            if callable(val):
                return val(args)

        builtin = BUILTINS.get(name)
        if builtin is not None:
            return builtin(args)

        raise WyrmRuntimeError(f"Undefined function or struct '{name}'")

    async def call_function(self, fn: WyrmFunction, args):
        call_env = Environment(fn.closure)
        for i, pname in enumerate(fn.params):
            call_env.declare(pname, args[i] if i < len(args) else None)
        try:
            await self.exec_block(fn.body, call_env)
        except ReturnSignal as r:
            return r.value
        return None


# -- builtins ----------------------------------------------------------

def _b_len(args):
    v = args[0]
    if isinstance(v, (list, str, dict)):
        return len(v)
    raise WyrmRuntimeError("len() expects an array, string, or map")


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
    return round(args[0])


def _b_pow(args):
    return args[0] ** args[1]


def _b_append(args):
    if not isinstance(args[0], list):
        raise WyrmRuntimeError("append() expects a list as first argument")
    args[0].append(args[1])
    return None


def _b_pop(args):
    if not isinstance(args[0], list):
        raise WyrmRuntimeError("pop() expects a list as first argument")
    if not args[0]:
        raise WyrmRuntimeError("pop() from empty list")
    return args[0].pop()


def _b_split(args):
    s = wyrm_str(args[0])
    sep = wyrm_str(args[1]) if len(args) > 1 else " "
    return s.split(sep)


def _b_join(args):
    sep = wyrm_str(args[0])
    arr = args[1]
    if not isinstance(arr, list):
        raise WyrmRuntimeError("join() expects array as second argument")
    return sep.join(wyrm_str(e) for e in arr)


def _b_trim(args):
    return wyrm_str(args[0]).strip()


def _b_upper(args):
    return wyrm_str(args[0]).upper()


def _b_lower(args):
    return wyrm_str(args[0]).lower()


def _b_contains(args):
    return wyrm_str(args[1]) in wyrm_str(args[0])


def _b_replace(args):
    return wyrm_str(args[0]).replace(wyrm_str(args[1]), wyrm_str(args[2]))


def _b_starts_with(args):
    return wyrm_str(args[0]).startswith(wyrm_str(args[1]))


def _b_ends_with(args):
    return wyrm_str(args[0]).endswith(wyrm_str(args[1]))


def _b_char_at(args):
    s = wyrm_str(args[0])
    idx = int(args[1])
    return s[idx] if 0 <= idx < len(s) else ""


def _b_ord_val(args):
    s = wyrm_str(args[0])
    return ord(s[0]) if s else 0


def _b_chr_val(args):
    return chr(int(args[0]))


def _b_to_bytes(args):
    s = wyrm_str(args[0])
    return [b for b in s.encode("utf-8")]


def _b_from_bytes(args):
    arr = args[0]
    return bytes(arr).decode("utf-8", errors="replace")


def _b_read_file(args):
    path = wyrm_str(args[0])
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _b_write_file(args):
    path = wyrm_str(args[0])
    content = wyrm_str(args[1])
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False


def _b_malloc(args):
    return [0] * int(args[0])


def _b_free(args):
    return None


def _b_realloc(args):
    ptr = args[0]
    new_size = int(args[1])
    if isinstance(ptr, list):
        if len(ptr) < new_size:
            ptr.extend([0] * (new_size - len(ptr)))
        else:
            del ptr[new_size:]
        return ptr
    return [0] * new_size


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
    "read_file": _b_read_file,
    "write_file": _b_write_file,
    "malloc": _b_malloc,
    "free": _b_free,
    "realloc": _b_realloc,
}
