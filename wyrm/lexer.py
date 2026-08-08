"""Wyrm 2.3 lexer.

Tokenizes Wyrm source into a flat token list. Mirrors the tokenizer behavior
used by the self-hosted compiler (compiler/wyrmc.wyr): // line comments,
/// doc comments, /* */ block comments, double- and single-quoted strings
with backslash escapes, numbers (int/float), identifiers/keywords, and
operators/punctuation including compound assignment and comparison ops.
"""

KEYWORDS = {
    "use", "fn", "var", "dec", "owned", "arena", "if", "elif", "else",
    "repeat", "do", "til", "unsafe", "return", "break", "continue",
    "and", "or", "not", "true", "false", "null",
}

# Longest-match-first operator table.
OPERATORS = [
    "&&", "||", "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "%=",
    "**", "//",
    "!", "<", ">", "+", "-", "*", "/", "%", "=",
]

PUNCT = {"(": "LPAREN", ")": "RPAREN", "{": "LBRACE", "}": "RBRACE",
          "[": "LBRACKET", "]": "RBRACKET", ",": "COMMA", ";": "SEMI",
          ".": "DOT", ":": "COLON"}


class LexError(Exception):
    pass


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type_, value, line, col):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, L{self.line})"


class Lexer:
    def __init__(self, source):
        self.src = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.n = len(source)

    def _peek(self, off=0):
        p = self.pos + off
        return self.src[p] if p < self.n else ""

    def _advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self):
        tokens = []
        at_line_start = True  # true at file start and right after a newline
        while self.pos < self.n:
            ch = self._peek()

            # whitespace (newlines are not emitted as tokens, but they do
            # reset the "start of line" flag used to disambiguate `//` as
            # comment-start vs the floor-division operator, matching the
            # native lexer: `//` only opens a comment at the start of a
            # logical line)
            if ch in " \t\r":
                self._advance()
                continue
            if ch == "\n":
                self._advance()
                at_line_start = True
                continue

            # comments: `//`, `///` only begin a comment when they appear
            # at the start of a line. Mid-line `//` is the floor-division
            # operator (see compiler/lexer/lexer.cpp skip_comment call site).
            if ch == "/" and self._peek(1) == "/" and at_line_start:
                while self.pos < self.n and self._peek() != "\n":
                    self._advance()
                continue
            if ch == "/" and self._peek(1) == "*":
                start_line = self.line
                self._advance(); self._advance()
                closed = False
                while self.pos < self.n:
                    if self._peek() == "*" and self._peek(1) == "/":
                        self._advance(); self._advance()
                        closed = True
                        break
                    self._advance()
                if not closed:
                    raise LexError(f"Unterminated block comment starting at line {start_line}")
                continue

            # strings
            if ch == '"' or ch == "'":
                quote = ch
                start_line, start_col = self.line, self.col
                self._advance()
                buf = []
                closed = False
                while self.pos < self.n:
                    c = self._peek()
                    if c == quote:
                        self._advance()
                        closed = True
                        break
                    if c == "\n":
                        break
                    if c == "\\":
                        self._advance()
                        esc = self._peek()
                        mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\",
                                   '"': '"', "'": "'"}
                        if esc in mapping:
                            buf.append(mapping[esc])
                            self._advance()
                        else:
                            buf.append("\\")
                    else:
                        buf.append(c)
                        self._advance()
                if not closed:
                    raise LexError(f"Unterminated string literal at line {start_line} col {start_col}")
                tokens.append(Token("STRING", "".join(buf), start_line, start_col))
                at_line_start = False
                continue

            # numbers
            if ch.isdigit():
                start_line, start_col = self.line, self.col
                buf = []
                while self.pos < self.n and self._peek().isdigit():
                    buf.append(self._advance())
                is_float = False
                if self._peek() == "." and self._peek(1).isdigit():
                    is_float = True
                    buf.append(self._advance())
                    while self.pos < self.n and self._peek().isdigit():
                        buf.append(self._advance())
                text = "".join(buf)
                tokens.append(Token("FLOAT" if is_float else "INT", text, start_line, start_col))
                at_line_start = False
                continue

            # identifiers / keywords
            if ch.isalpha() or ch == "_":
                start_line, start_col = self.line, self.col
                buf = []
                while self.pos < self.n and (self._peek().isalnum() or self._peek() == "_"):
                    buf.append(self._advance())
                text = "".join(buf)
                if text in KEYWORDS:
                    tokens.append(Token(text.upper(), text, start_line, start_col))
                else:
                    tokens.append(Token("IDENT", text, start_line, start_col))
                at_line_start = False
                continue

            # operators (longest match first)
            matched = False
            for op in OPERATORS:
                if self.src.startswith(op, self.pos):
                    start_line, start_col = self.line, self.col
                    for _ in op:
                        self._advance()
                    tokens.append(Token("OP", op, start_line, start_col))
                    matched = True
                    break
            if matched:
                at_line_start = False
                continue

            # punctuation
            if ch in PUNCT:
                start_line, start_col = self.line, self.col
                self._advance()
                tokens.append(Token(PUNCT[ch], ch, start_line, start_col))
                at_line_start = False
                continue

            raise LexError(f"Unexpected character {ch!r} at line {self.line} col {self.col}")

        tokens.append(Token("EOF", None, self.line, self.col))
        return tokens
