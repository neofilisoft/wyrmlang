"""Thin adapter exposing the interface the browser playground (script.js)
expects: `AsyncInterpreter(input_coro=...)` with an `await .execute(ast)`
method that prints via built-in `print()` (captured by redirecting
sys.stdout, as script.js does with io.StringIO).

The real evaluator lives in interpreter.py; this module just adapts calling
conventions so script.js doesn't need to change its boot sequence.
"""

import sys

from .ast import Program
from .interpreter import Interpreter


class AsyncInterpreter:
    def __init__(self, input_coro=None):
        # script.js redirects sys.stdout to an io.StringIO before calling
        # execute(), so writing through print() naturally lands there.
        self._interp = Interpreter(output=self._write, input_fn=input_coro)

    def _write(self, s):
        sys.stdout.write(s)

    async def execute(self, ast_nodes):
        program = ast_nodes if isinstance(ast_nodes, Program) else Program(ast_nodes)
        await self._interp.run(program)
