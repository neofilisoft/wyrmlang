"""Wyrm Language Interpreter (browser playground build)."""

__version__ = "2.3"
__author__ = "Neofilisoft"

from .lexer import Lexer, LexError
from .parser import Parser, ParseError
from .interpreter import Interpreter
from .environment import WyrmRuntimeError


async def run_source(source, output=None, input_fn=None):
    """Tokenize, parse, and run Wyrm source. Raises LexError, ParseError,
    or WyrmRuntimeError on failure; caller (script.js) catches and reports."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    interp = Interpreter(output=output, input_fn=input_fn)
    await interp.run(program)
