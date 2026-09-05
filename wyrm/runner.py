import sys
import io
import re
import asyncio
from wyrm.lexer import Lexer, LexError
from wyrm.parser import Parser, ParseError
from wyrm.environment import WyrmRuntimeError
from wyrm.async_interpreter import AsyncInterpreter

_js_handler = None

def setup(js_handler):
    global _js_handler
    _js_handler = js_handler

async def _py_input_coro(prompt):
    if _js_handler is not None:
        result = await _js_handler(prompt)
        return str(result)
    return ""

def format_visual_error(e, code):
    msg = str(e)
    lines = code.splitlines()
    m = re.search(r"line\s+(\d+)(?:\s+col\s+(\d+))?", msg, re.IGNORECASE)
    if m:
        line_num = int(m.group(1))
        col_num = int(m.group(2)) if m.group(2) else 1
        snippet = lines[line_num - 1] if 0 <= line_num - 1 < len(lines) else ""
        pointer = " " * max(0, col_num - 1) + "^"
        err_code = (
            "error[E0002]" if isinstance(e, ParseError)
            else ("error[E0001]" if isinstance(e, LexError) else "error[E0003]")
        )
        parts = [
            f"{err_code}: {msg}",
            f"  --> main.wyr:{line_num}:{col_num}",
            "   |",
            f"{line_num:2d} | {snippet}",
            f"   | {pointer}"
        ]
        return "\n".join(parts)
    return f"error[E0003]: {type(e).__name__}: {msg}"

async def run_async(code):
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    ok = True
    err = ""
    try:
        interp = AsyncInterpreter(input_coro=_py_input_coro)
        tokens = Lexer(code).tokenize()
        ast_nodes = Parser(tokens).parse()
        await interp.execute(ast_nodes)
    except Exception as e:
        ok = False
        err = format_visual_error(e, code)
    finally:
        sys.stdout = old_stdout
    return {"ok": ok, "output": buf.getvalue(), "error": err}
