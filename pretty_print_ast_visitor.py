from miniast import mini_ast, program_ast, type_ast, statement_ast, expression_ast, lvalue_ast

class PPASTVisitor(mini_ast.ASTVisitor):
 
    def __init__(self):
        self._buf: list[str] = []
        self._indent_level = 0
        self._indent_str = "    "

    def line(self, s: str = ""):
        self._buf.append(self._indent_str * self._indent_level + s + "\n")

    def indent(self):
        self._indent_level += 1

    def dedent(self):
        if self._indent_level > 0:
            self._indent_level -= 1

    def out(self) -> str:
        return "".join(self._buf)

    def pretty_print(self, root: mini_ast.MiniASTNode) -> str:
        self._buf.clear()
        self._indent_level = 0
        self.line("AST created:")
        root.accept(self)
        return self.out()

    def _ident_text(self, ident: expression_ast.IdentifierExpression) -> str:
        return ident.id

    def _type_to_str(self, t) -> str:
        if isinstance(t, type_ast.IntType): return "int"
        if isinstance(t, type_ast.BoolType): return "bool"
        if isinstance(t, type_ast.StructType): return f"struct {self._ident_text(t.name)}"
        if isinstance(t, type_ast.ReturnTypeVoid): return "void"
        if isinstance(t, type_ast.ReturnTypeReal): return self._type_to_str(t.type_)
        prev_buf, prev_lvl = self._buf, self._indent_level
        self._buf, self._indent_level = [], 0
        t.accept(self)
        s = "".join(self._buf).strip().splitlines()[0] if self._buf else str(t)
        self._buf, self._indent_level = prev_buf, prev_lvl
        return s

    def visit_program(self, program: program_ast.Program):
        self.line("Program")
        self.indent()

        if program.types:
            self.line("Types")
            self.indent()
            for ty_decl in program.types:
                ty_decl.accept(self)
            self.dedent()

        if program.declarations:
            self.line("Declarations")
            self.indent()
            for decl in program.declarations:
                decl.accept(self)
            self.dedent()

        if program.functions:
            self.line("Functions")
            self.indent()
            for func in program.functions:
                func.accept(self)
            self.dedent()

        self.dedent()
        return self.out()

    def visit_type_declaration(self, td: program_ast.TypeDeclaration):
        self.line(f"TypeDeclaration: {self._ident_text(td.name)}")
        if td.fields:
            self.indent()
            self.line("Fields")
            self.indent()
            for field in td.fields:
                ty = self._type_to_str(field.type)
                self.line(f"Declaration: {ty} '{self._ident_text(field.name)}'")
            self.dedent()
            self.dedent()

    def visit_int_type(self, _t: type_ast.IntType):
        self.line("IntType")

    def visit_bool_type(self, _t: type_ast.BoolType):
        self.line("BoolType")

    def visit_struct_type(self, t: type_ast.StructType):
        self.line(f"StructType: {self._ident_text(t.name)}")

    def visit_return_type_real(self, r: type_ast.ReturnTypeReal):
        self.line(f"Return Type: {self._type_to_str(r.type_)}")

    def visit_return_type_void(self, _r: type_ast.ReturnTypeVoid):
        self.line("Return Type: void")

    def visit_declaration(self, d: program_ast.Declaration):
        ty = self._type_to_str(d.type)
        self.line(f"Declaration: {ty} {self._ident_text(d.name)}")

    def visit_function(self, f: program_ast.Function):
        self.line(f"Function: {self._ident_text(f.name)}")
        self.indent()

        self.line("Parameters:")
        self.indent()
        if not f.params:
            self.line("(none)")
        else:
            for p in f.params:
                self.line(f"Param: {self._type_to_str(p.type)} '{self._ident_text(p.name)}'")
        self.dedent()

        self.line(f"Return Type: {self._type_to_str(f.ret_type)}")

        if f.locals:
            self.line("Locals")
            self.indent()
            for loc in f.locals:
                loc.accept(self)
            self.dedent()

        self.line("Body")
        self.indent()
        for stmt in f.body:
            stmt.accept(self)
        self.dedent()

        self.dedent()

    def visit_block_statement(self, b: statement_ast.BlockStatement):
        self.line("Block")
        self.indent()
        for s in b.statements:
            s.accept(self)
        self.dedent()

    def visit_assignment_statement(self, s: statement_ast.AssignmentStatement):
        self.line("Assignment")
        self.indent()
        self.line("Target")
        self.indent(); s.target.accept(self); self.dedent()
        self.line("Source")
        self.indent(); s.source.accept(self); self.dedent()
        self.dedent()

    def visit_print_statement(self, s: statement_ast.PrintStatement):
        self.line("Print")
        self.indent()
        s.expression.accept(self)
        self.dedent()

    def visit_println_statement(self, s: statement_ast.PrintLnStatement):
        self.line("PrintLn")
        self.indent()
        s.expression.accept(self)
        self.dedent()

    def visit_conditional_statement(self, s: statement_ast.ConditionalStatement):
        self.line("ConditionalExpression")
        self.indent()
        self.line("Guard")
        self.indent(); s.guard.accept(self); self.dedent()
        self.line("ThenBlock")
        self.indent(); s.then_block.accept(self); self.dedent()
        if s.else_block is not None:
            self.line("ElseBlock")
            self.indent(); s.else_block.accept(self); self.dedent()
        self.dedent()

    def visit_while_statement(self, s: statement_ast.WhileStatement):
        self.line("While")
        self.indent()
        self.line("Guard")
        self.indent(); s.guard.accept(self); self.dedent()
        self.line("Body")
        self.indent(); s.body.accept(self); self.dedent()
        self.dedent()

    def visit_delete_statement(self, s: statement_ast.DeleteStatement):
        self.line("Delete")
        self.indent()
        s.expression.accept(self)
        self.dedent()

    def visit_invocation_statement(self, s: statement_ast.InvocationStatement):
        self.line("Invocation")
        self.indent()
        s.expression.accept(self)
        self.dedent()

    def visit_return_empty_statement(self, _s: statement_ast.ReturnEmptyStatement):
        self.line("Return")

    def visit_return_statement(self, s: statement_ast.ReturnStatement):
        self.line("Return")
        self.indent()
        s.expression.accept(self)
        self.dedent()

    def visit_identifier_expression(self, e: expression_ast.IdentifierExpression):
        self.line(f"Id: {e.id}")

    def visit_integer_expression(self, e: expression_ast.IntegerExpression):
        self.line(f"Integer: {e.value}")

    def visit_true_expression(self, _e: expression_ast.TrueExpression):
        self.line("Bool: true")

    def visit_false_expression(self, _e: expression_ast.FalseExpression):
        self.line("Bool: false")

    def visit_null_expression(self, _e: expression_ast.NullExpression):
        self.line("Null")

    def visit_new_expression(self, e: expression_ast.NewExpression):
        self.line(f"New struct: {self._ident_text(e.id)}")

    def visit_read_expression(self, _e: expression_ast.ReadExpression):
        self.line("Read")

    def visit_invocation_expression(self, e: expression_ast.InvocationExpression):
        self.line("Call")
        self.indent()
        self.line(f"Name: {self._ident_text(e.name)}")
        self.line("Args")
        self.indent()
        for arg in e.arguments:
            arg.accept(self)
        self.dedent()
        self.dedent()

    def visit_unary_expression(self, e: expression_ast.UnaryExpression):
        self.line(f"Unary")
        self.indent()
        self.line(f"Operator: {e.operator.value}")
        self.line("Operand")
        self.indent(); e.operand.accept(self); self.dedent()
        self.dedent()

    def visit_binary_expression(self, e: expression_ast.BinaryExpression):
        self.line("BinaryExpression")
        self.indent()
        self.line(f"Operator: {e.operator.value}")
        self.line("Left")
        self.indent(); e.left.accept(self); self.dedent()
        self.line("Right")
        self.indent(); e.right.accept(self); self.dedent()
        self.dedent()

    def visit_dot_expression(self, e: expression_ast.DotExpression):
        self.line("DotExpression")
        self.indent()
        self.line("Left")
        self.indent(); e.left.accept(self); self.dedent()
        self.line(f"Id: {self._ident_text(e.id)}")
        self.dedent()

    def visit_lvalue_dot(self, v: lvalue_ast.LValueDot):
        self.line("LValue (LvalueDot)")
        self.indent()
        self.line("Base")
        self.indent(); v.left.accept(self); self.dedent()
        self.line(f"Field: {self._ident_text(v.id)}")
        self.dedent()

    def visit_lvalue_id(self, v: lvalue_ast.LValueID):
        self.line(f"LValue (LvalueId): {self._ident_text(v.id)}")
