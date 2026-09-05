"""Wyrm v3.1.0 parser: recursive-descent parser producing the AST in ast.py.

Grammar mirrors compiler/wyrmc.wyr (self-hosted v3.1) with Structs & Methods,
gradual type annotations, arena allocation, and complete operator set.
"""

from .ast import (
    Program, NumberLit, StringLit, BoolLit, NullLit, ArrayLit, Identifier,
    UnaryOp, BinaryOp, LogicalOp, Assign, CompoundAssign, Index, Slice, IndexAssign,
    MemberAccess, MemberAssign, Call, MethodCall, FuncDef, StructDef, Return,
    Break, Continue, If, DoTil, UseStmt, UnsafeBlock, ArenaDecl, ExprStmt,
)


class ParseError(Exception):
    pass


COMPOUND_OPS = {"+=", "-=", "*=", "/=", "%="}
LOGICAL_KEYWORDS = {"and": "&&", "or": "||"}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # -- token helpers --------------------------------------------------
    def _cur(self):
        return self.tokens[self.pos]

    def _at_end(self):
        return self._cur().type == "EOF"

    def _advance(self):
        tok = self.tokens[self.pos]
        if not self._at_end():
            self.pos += 1
        return tok

    def _check(self, *types):
        return self._cur().type in types

    def _check_val(self, val):
        return self._cur().value == val

    def _expect(self, type_, msg=None):
        if self._cur().type != type_:
            raise ParseError(
                msg or f"Expected {type_} but got {self._cur().type} "
                       f"({self._cur().value!r}) at line {self._cur().line}"
            )
        return self._advance()

    # -- entry ------------------------------------------------------------
    def parse(self):
        statements = []
        while not self._at_end():
            statements.append(self._statement())
        return Program(statements)

    def _block(self):
        self._expect("LBRACE")
        stmts = []
        while not self._check("RBRACE") and not self._at_end():
            stmts.append(self._statement())
        self._expect("RBRACE")
        return stmts

    # -- statements ---------------------------------------------------
    def _statement(self):
        tok = self._cur()

        if tok.type == "USE":
            self._advance()
            parts = [str(self._advance().value)]
            while self._check("DOT"):
                self._advance()
                parts.append(str(self._advance().value))
            path = ".".join(parts) if len(parts) > 1 else parts[0]
            if self._check("SEMI"):
                self._advance()
            return UseStmt(path)

        if tok.type == "STRUCT":
            self._advance()
            name = self._expect("IDENT").value
            self._expect("LBRACE")
            fields = []
            field_types = {}
            methods = []
            while not self._check("RBRACE") and not self._at_end():
                if self._check("FN"):
                    methods.append(self._statement())
                    continue
                fname = self._expect("IDENT").value
                ftype = None
                if self._check("COLON"):
                    self._advance()
                    ftype = self._expect("IDENT").value
                fields.append(fname)
                if ftype:
                    field_types[fname] = ftype
                if self._check("COMMA") or self._check("SEMI"):
                    self._advance()
            self._expect("RBRACE")
            return StructDef(name, fields, methods, field_types)

        if tok.type == "FN":
            self._advance()
            name = self._expect("IDENT").value
            self._expect("LPAREN")
            params = []
            param_types = {}
            if not self._check("RPAREN"):
                while True:
                    if self._check("SELF"):
                        pname = self._advance().value
                    else:
                        pname = self._expect("IDENT").value
                    ptype = None
                    if self._check("COLON"):
                        self._advance()
                        ptype = self._expect("IDENT").value
                    params.append(pname)
                    if ptype:
                        param_types[pname] = ptype
                    if self._check("COMMA"):
                        self._advance()
                        continue
                    break
            self._expect("RPAREN")
            ret_type = None
            if self._check("COLON"):
                self._advance()
                ret_type = self._expect("IDENT").value
            elif self._check("OP") and self._cur().value == "->":
                self._advance()
                ret_type = self._expect("IDENT").value
            body = self._block()
            return FuncDef(name, params, body, param_types, ret_type)

        if tok.type in ("VAR", "DEC", "OWNED"):
            kind = tok.type
            self._advance()
            name = self._expect("IDENT").value
            type_annot = None
            if self._check("COLON"):
                self._advance()
                type_annot = self._expect("IDENT").value
            self._expect_op("=")
            value = self._expression()
            if self._check("SEMI"):
                self._advance()
            return Assign(Identifier(name), value, declared=True,
                          const=(kind == "DEC"), owned=(kind == "OWNED"),
                          type_annot=type_annot)

        if tok.type == "ARENA":
            self._advance()
            name = self._expect("IDENT").value
            self._expect("LPAREN")
            size = self._expression()
            self._expect("RPAREN")
            if self._check("SEMI"):
                self._advance()
            return ArenaDecl(name, size)

        if tok.type == "IF":
            return self._if_statement()

        if tok.type in ("REPEAT", "DO"):
            self._advance()
            body = self._block()
            self._expect("TIL")
            paren = self._check("LPAREN")
            if paren:
                self._advance()
            cond = self._expression()
            if paren:
                self._expect("RPAREN")
            if self._check("SEMI"):
                self._advance()
            return DoTil(body, cond)

        if tok.type == "UNSAFE":
            self._advance()
            body = self._block()
            return UnsafeBlock(body)

        if tok.type == "RETURN":
            self._advance()
            value = None
            if not self._check("RBRACE", "SEMI", "EOF"):
                value = self._expression()
            if self._check("SEMI"):
                self._advance()
            return Return(value)

        if tok.type == "BREAK":
            self._advance()
            if self._check("SEMI"):
                self._advance()
            return Break()

        if tok.type == "CONTINUE":
            self._advance()
            if self._check("SEMI"):
                self._advance()
            return Continue()

        # assignment / member-assign / index-assign / compound-assign / bare expression
        expr = self._expression()

        if self._check("OP") and self._cur().value == "=":
            self._advance()
            value = self._expression()
            if self._check("SEMI"):
                self._advance()
            if isinstance(expr, Index):
                return IndexAssign(expr.obj, expr.index, value)
            if isinstance(expr, MemberAccess):
                return MemberAssign(expr.obj, expr.member, value)
            if isinstance(expr, Identifier):
                return Assign(expr, value)
            raise ParseError("Invalid assignment target")

        if self._check("OP") and self._cur().value in COMPOUND_OPS:
            op = self._advance().value
            value = self._expression()
            if self._check("SEMI"):
                self._advance()
            return CompoundAssign(expr, op[0], value)

        if self._check("SEMI"):
            self._advance()
        return ExprStmt(expr)

    def _if_statement(self):
        self._expect("IF")
        cond = self._expression()
        then_body = self._block()
        branches = [(cond, then_body)]
        else_body = []
        while self._check("ELIF"):
            self._advance()
            elif_cond = self._expression()
            elif_body = self._block()
            branches.append((elif_cond, elif_body))
        if self._check("ELSE"):
            self._advance()
            else_body = self._block()
        return If(branches, else_body)

    # -- expressions (precedence climbing) -----------------------------
    def _expect_op(self, value):
        if not (self._check("OP") and self._cur().value == value):
            raise ParseError(
                f"Expected operator {value!r} but got {self._cur().value!r} "
                f"at line {self._cur().line}"
            )
        return self._advance()

    def _expression(self):
        return self._logical_or()

    def _logical_or(self):
        node = self._logical_and()
        while (self._check("OR")) or (self._check("OP") and self._cur().value == "||"):
            self._advance()
            right = self._logical_and()
            node = LogicalOp("||", node, right)
        return node

    def _logical_and(self):
        node = self._equality()
        while (self._check("AND")) or (self._check("OP") and self._cur().value == "&&"):
            self._advance()
            right = self._equality()
            node = LogicalOp("&&", node, right)
        return node

    def _equality(self):
        node = self._comparison()
        while self._check("OP") and self._cur().value in ("==", "!="):
            op = self._advance().value
            right = self._comparison()
            node = BinaryOp(op, node, right)
        return node

    def _comparison(self):
        node = self._addition()
        while self._check("OP") and self._cur().value in ("<", ">", "<=", ">="):
            op = self._advance().value
            right = self._addition()
            node = BinaryOp(op, node, right)
        return node

    def _addition(self):
        node = self._multiplication()
        while self._check("OP") and self._cur().value in ("+", "-"):
            op = self._advance().value
            right = self._multiplication()
            node = BinaryOp(op, node, right)
        return node

    def _multiplication(self):
        node = self._power()
        while self._check("OP") and self._cur().value in ("*", "/", "%", "//"):
            op = self._advance().value
            right = self._power()
            node = BinaryOp(op, node, right)
        return node

    def _power(self):
        node = self._unary()
        if self._check("OP") and self._cur().value == "**":
            self._advance()
            right = self._power()
            node = BinaryOp("**", node, right)
        return node

    def _unary(self):
        if self._check("NOT") or (self._check("OP") and self._cur().value in ("!", "-", "+")):
            op = self._advance().value
            operand = self._unary()
            return UnaryOp(op, operand)
        return self._postfix()

    def _postfix(self):
        node = self._primary()
        while True:
            if self._check("LPAREN") and isinstance(node, Identifier):
                self._advance()
                args = []
                if not self._check("RPAREN"):
                    while True:
                        args.append(self._expression())
                        if self._check("COMMA"):
                            self._advance()
                            continue
                        break
                self._expect("RPAREN")
                node = Call(node.name, args)
                continue
            if self._check("LBRACKET"):
                self._advance()
                if self._check("COLON"):
                    self._advance()
                    end = None
                    if not self._check("RBRACKET"):
                        end = self._expression()
                    self._expect("RBRACKET")
                    node = Slice(node, None, end)
                    continue
                first = self._expression()
                if self._check("COLON"):
                    self._advance()
                    end = None
                    if not self._check("RBRACKET"):
                        end = self._expression()
                    self._expect("RBRACKET")
                    node = Slice(node, first, end)
                    continue
                self._expect("RBRACKET")
                node = Index(node, first)
                continue
            if self._check("DOT"):
                self._advance()
                member_name = self._expect("IDENT").value
                if self._check("LPAREN"):
                    self._advance()
                    args = []
                    if not self._check("RPAREN"):
                        while True:
                            args.append(self._expression())
                            if self._check("COMMA"):
                                self._advance()
                                continue
                            break
                    self._expect("RPAREN")
                    node = MethodCall(node, member_name, args)
                else:
                    node = MemberAccess(node, member_name)
                continue
            break
        return node

    def _primary(self):
        tok = self._cur()

        if tok.type == "INT":
            self._advance()
            return NumberLit(int(tok.value))
        if tok.type == "FLOAT":
            self._advance()
            return NumberLit(float(tok.value))
        if tok.type == "STRING":
            self._advance()
            return StringLit(tok.value)
        if tok.type == "TRUE":
            self._advance()
            return BoolLit(True)
        if tok.type == "FALSE":
            self._advance()
            return BoolLit(False)
        if tok.type == "NULL":
            self._advance()
            return NullLit()
        if tok.type == "SELF":
            self._advance()
            return Identifier("self")
        if tok.type == "IDENT":
            self._advance()
            return Identifier(tok.value)
        if tok.type == "LBRACKET":
            self._advance()
            elems = []
            if not self._check("RBRACKET"):
                while True:
                    elems.append(self._expression())
                    if self._check("COMMA"):
                        self._advance()
                        continue
                    break
            self._expect("RBRACKET")
            return ArrayLit(elems)
        if tok.type == "LPAREN":
            self._advance()
            expr = self._expression()
            self._expect("RPAREN")
            return expr

        raise ParseError(
            f"Unexpected token {tok.type} ({tok.value!r}) at line {tok.line} col {tok.col}"
        )
