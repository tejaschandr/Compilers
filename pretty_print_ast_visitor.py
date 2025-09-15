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

    def _ident_text(self, ident: expression_ast.IdentifierExpression) -> str:
        return ident.id

    def visit_program(self, program: program_ast.Program):
        for type in program.types:
            type.accept(self)
            self.line()

        for declaration in program.declarations:
            declaration.accept(self)

        if program.functions and (program.types or program.declarations):
            self.line()

        for func in program.functions:
            func.accept(self)
            self.line()

        return self.out()

    def visit_declaration(self, declaration: program_ast.Declaration):
        type = declaration.type.accept(self)
        name = self._ident_text(declaration.name)
        self.line(f"{type} {name};")

    def visit_type_declaration(self, type_declaration: program_ast.TypeDeclaration):
        name = self._ident_text(type_declaration.name)
        self.line(f"struct {name} {{")
        self.indent()
        for field in type_declaration.fields:
            type = field.type.accept(self)
            fname = self._ident_text(field.name)
            self.line(f"{type} {fname};")
        self.dedent()
        self.line("};")

    def visit_function(self, function: program_ast.Function):
        functionName = self._ident_text(function.name)
        returnType = function.ret_type
        if isinstance(returnType, (type_ast.IntType, type_ast.BoolType, type_ast.StructType, type_ast.ReturnTypeReal, type_ast.ReturnTypeVoid)):
            returnText = returnType.accept(self)
        else:
            returnText = "void" if returnType is None else str(returnType.accept(self))
        params = []
        for p in function.params:
            pty = p.type.accept(self)
            pname = self._ident_text(p.name)
            params.append(f"{pty} {pname}")
        decl_text = "(" + ", ".join(params) + ")"

        self.line(f"fun {functionName}{decl_text} {returnText} {{")
        self.indent()

        for l in function.locals:
            l.accept(self)

        for stmt in function.body:
            stmt.accept(self)
            
        self.dedent()
        self.line("}")

    def visit_int_type(self, int_type: type_ast.IntType):
        return "int"

    def visit_bool_type(self, boll_type: type_ast.BoolType):
        return "bool"

    def visit_struct_type(self, struct_type: type_ast.StructType):
        return f"struct {self._ident_text(struct_type.name)}"

    def visit_return_type_real(self, return_type_real: type_ast.ReturnTypeReal):
        return return_type_real.type_.accept(self)

    def visit_return_type_void(self, return_type_void: type_ast.ReturnTypeVoid):
        return "void"

    def visit_block_statement(self, block_statement: statement_ast.BlockStatement):
        self.line("{")
        self.indent()
        for s in block_statement.statements:
            s.accept(self)
        self.dedent()
        self.line("}")

    def visit_assignment_statement(self, assignment_satement: statement_ast.AssignmentStatement):
        lhs = assignment_satement.target.accept(self)
        rhs = assignment_satement.source.accept(self)
        self.line(f"{lhs} = {rhs};")

    def visit_print_statement(self, print_statement: statement_ast.PrintStatement):
        e = print_statement.expression.accept(self)
        self.line(f"print {e};")

    def visit_println_statement(self, println_statement: statement_ast.PrintLnStatement):
        e = println_statement.expression.accept(self)
        self.line(f"println {e};")

    def visit_conditional_statement(self, conditional_statement: statement_ast.ConditionalStatement):
        condition = conditional_statement.guard.accept(self)
        self.line(f"if ({condition})")
        conditional_statement.then_block.accept(self)
        if conditional_statement.else_block is not None:
            self.line("else")
            conditional_statement.else_block.accept(self)

    def visit_while_statement(self, while_statement: statement_ast.WhileStatement):
        cond = while_statement.guard.accept(self)
        self.line(f"while ({cond})")
        while_statement.body.accept(self)

    def visit_delete_statement(self, delete_statement: statement_ast.DeleteStatement):
        e = delete_statement.expression.accept(self)
        self.line(f"delete {e};")

    def visit_invocation_statement(self, invocation_statement: statement_ast.InvocationStatement):
        call = invocation_statement.expression.accept(self)
        self.line(f"{call};")

    def visit_return_empty_statement(self, return_empty_statement: statement_ast.ReturnEmptyStatement):
        self.line("return;")

    def visit_return_statement(self, return_statement: statement_ast.ReturnStatement):
        e = return_statement.expression.accept(self)
        self.line(f"return {e};")

    def visit_identifier_expression(self, identifier_expression: expression_ast.IdentifierExpression):
        return identifier_expression.id

    def visit_integer_expression(self, integer_expression: expression_ast.IntegerExpression):
        return str(integer_expression.value)

    def visit_true_expression(self, true_expression: expression_ast.TrueExpression):
        return "true"

    def visit_false_expression(self, false_expression: expression_ast.FalseExpression):
        return "false"

    def visit_null_expression(self, null_expression: expression_ast.NullExpression):
        return "null"

    def visit_new_expression(self, new_expression: expression_ast.NewExpression):
        return f"new {self._ident_text(new_expression.id)}"

    def visit_read_expression(self, read_expression: expression_ast.ReadExpression):
        return "read"

    def visit_invocation_expression(self, invocation_expression: expression_ast.InvocationExpression):
        functionName = self._ident_text(invocation_expression.name)
        args = ", ".join(arg.accept(self) for arg in invocation_expression.arguments)
        return f"{functionName}({args})"

    def visit_unary_expression(self, unary_expression: expression_ast.UnaryExpression):
        operator = unary_expression.operator.value
        inner = unary_expression.operand
        inner_text = inner.accept(self)
        if isinstance(inner, (expression_ast.BinaryExpression, expression_ast.UnaryExpression)):
            inner_text = f"({inner_text})"
        return f"{operator}{inner_text}"

    def visit_binary_expression(self, binary_expression: expression_ast.BinaryExpression):
        operator = binary_expression.operator.value
        left = binary_expression.left.accept(self)
        right = binary_expression.right.accept(self)

        if isinstance(binary_expression.left, expression_ast.BinaryExpression):
            left = f"({left})"
        if isinstance(binary_expression.right, expression_ast.BinaryExpression):
            right = f"({right})"

        return f"{left} {operator} {right}"

    def visit_dot_expression(self, dot_expression: expression_ast.DotExpression):
        base = dot_expression.left.accept(self)
        field = self._ident_text(dot_expression.id)
        return f"{base}.{field}"
    
    def visit_lvalue_dot(self, lvalue_dot: lvalue_ast.LValueDot):
        base = lvalue_dot.left.accept(self)
        field = self._ident_text(lvalue_dot.id)
        return f"{base}.{field}"

    def visit_lvalue_id(self, lvalue_id: lvalue_ast.LValueID):
        return self._ident_text(lvalue_id.id)