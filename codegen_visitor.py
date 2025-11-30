from miniast import mini_ast, program_ast, type_ast, statement_ast, expression_ast, lvalue_ast
import re

class CodeGenVisitor(mini_ast.ASTVisitor):
    def __init__(self):
        self.output = []
        self.label_counter = 0
        self.local_offset_map = {}
        self.local_type_map = {}
        self.global_type_map = {}
        self.current_offset = 0
        self.current_function = None
        self.temp_reg_counter = 0
        self.struct_field_offsets = {}
        self.struct_field_types = {}
        self.struct_sizes = {}

    def emit(self, instruction):
        self.output.append(instruction)

    def peephole_optimize(self, instructions):
        optimized = []
        i = 0
        while i < len(instructions):
            curr = instructions[i].strip()
            next_instr = instructions[i + 1].strip() if i + 1 < len(instructions) else ""
            
            mv_same = re.match(r'mv\s+(\w+),\s+(\w+)$', curr)
            if mv_same and mv_same.group(1) == mv_same.group(2):
                i += 1
                continue
            
            j_match = re.match(r'j\s+(\w+)$', curr)
            label_match = re.match(r'(\w+):$', next_instr)
            if j_match and label_match and j_match.group(1) == label_match.group(1):
                i += 1
                continue
            
            sw_match = re.match(r'sw\s+(\w+),\s+(-?\d+\(\w+\))$', curr)
            lw_match = re.match(r'lw\s+(\w+),\s+(-?\d+\(\w+\))$', next_instr)
            if sw_match and lw_match:
                if sw_match.group(1) == lw_match.group(1) and sw_match.group(2) == lw_match.group(2):
                    optimized.append(instructions[i])
                    i += 2
                    continue

            optimized.append(instructions[i])
            i += 1
        
        return optimized

    def get_temp_reg(self):
        regs = ['t0', 't1', 't2', 't3', 't4', 't5', 't6']
        reg = regs[self.temp_reg_counter % len(regs)]
        self.temp_reg_counter += 1
        return reg

    def release_temp_reg(self):
        self.temp_reg_counter -= 1

    def get_label(self, prefix="L"):
        label = f"{prefix}{self.label_counter}"
        self.label_counter += 1
        return label

    def get_expr_type(self, expr):
        if isinstance(expr, expression_ast.IdentifierExpression):
            var_name = expr.id
            if var_name in self.local_type_map:
                return self.local_type_map[var_name]
            if var_name in self.global_type_map:
                return self.global_type_map[var_name]
            return None
        elif isinstance(expr, expression_ast.DotExpression):
            left_type = self.get_expr_type(expr.left)
            if left_type and left_type in self.struct_field_types:
                field_name = expr.id.id
                if field_name in self.struct_field_types[left_type]:
                    return self.struct_field_types[left_type][field_name]
            return None
        elif isinstance(expr, expression_ast.NewExpression):
            return expr.id.id
        elif isinstance(expr, expression_ast.InvocationExpression):
            func_name = expr.name.id
            if func_name in self.function_return_types:
                return self.function_return_types[func_name]
            return None
        return None

    def get_lvalue_type(self, lvalue):
        if isinstance(lvalue, lvalue_ast.LValueID):
            var_name = lvalue.id.id
            if var_name in self.local_type_map:
                return self.local_type_map[var_name]
            if var_name in self.global_type_map:
                return self.global_type_map[var_name]
            return None
        elif isinstance(lvalue, lvalue_ast.LValueDot):
            left_type = self.get_lvalue_type(lvalue.left)
            if left_type and left_type in self.struct_field_types:
                field_name = lvalue.id.id
                if field_name in self.struct_field_types[left_type]:
                    return self.struct_field_types[left_type][field_name]
            return None
        return None

    def visit_program(self, program: program_ast.Program):
        self.emit(".globl main")
        self.emit(".import berkeley_utils.s")
        self.emit(".import read_int.s")

        self.function_return_types = {}
        for func in program.functions:
            func_name = func.name.id
            ret_type = func.ret_type
            if isinstance(ret_type, type_ast.StructType):
                self.function_return_types[func_name] = ret_type.name.id
            else:
                self.function_return_types[func_name] = None

        if hasattr(program, 'types') and program.types:
            for type_decl in program.types:
                type_decl.accept(self)
        elif hasattr(program, 'type_declarations') and program.type_declarations:
            for type_decl in program.type_declarations:
                type_decl.accept(self)

        self.emit("\n.data")
        self.emit("input_file_ptr: .word")

        if program.declarations:
            for var in program.declarations:
                var_name = var.name.id
                self.emit(f"{var_name}: .word 0")
                if isinstance(var.type, type_ast.StructType):
                    self.global_type_map[var_name] = var.type.name.id
                else:
                    self.global_type_map[var_name] = None

        self.emit("\n.text")

        for func in program.functions:
            func.accept(self)

        self.output = self.peephole_optimize(self.output)
        return "\n".join(self.output)

    def visit_declaration(self, declaration: program_ast.Declaration):
        pass

    def visit_type_declaration(self, type_declaration: program_ast.TypeDeclaration):
        struct_name = type_declaration.name.id
        self.struct_field_offsets[struct_name] = {}
        self.struct_field_types[struct_name] = {}
        offset = 0
        for field in type_declaration.fields:
            field_name = field.name.id
            self.struct_field_offsets[struct_name][field_name] = offset
            if isinstance(field.type, type_ast.StructType):
                self.struct_field_types[struct_name][field_name] = field.type.name.id
            else:
                self.struct_field_types[struct_name][field_name] = None
            offset += 4
        self.struct_sizes[struct_name] = offset

    def visit_function(self, function: program_ast.Function):
        self.temp_reg_counter = 0
        func_name = function.name.id
        self.current_function = func_name

        self.emit(f"\n{func_name}:")

        if func_name == "main":
            self.emit("    lw t0, 4(a1)")
            self.emit("    la t1, input_file_ptr")
            self.emit("    sw t0, 0(t1)")

        num_locals = len(function.locals)
        num_params = len(function.params)
        total_stack_size = (num_locals + num_params) * 4 + 8

        self.emit(f"    addi sp, sp, -{total_stack_size}")
        self.emit(f"    sw ra, {total_stack_size - 4}(sp)")
        self.emit(f"    sw fp, {total_stack_size - 8}(sp)")
        self.emit(f"    addi fp, sp, {total_stack_size}")

        self.local_offset_map = {}
        self.local_type_map = {}
        current_offset = -8

        for i, param in enumerate(function.params):
            param_name = param.name.id
            current_offset -= 4
            self.local_offset_map[param_name] = current_offset
            if isinstance(param.type, type_ast.StructType):
                self.local_type_map[param_name] = param.type.name.id
            else:
                self.local_type_map[param_name] = None
            if i < 8:
                self.emit(f"    sw a{i}, {current_offset}(fp)")
            else:
                caller_stack_offset = (i - 8) * 4
                self.emit(f"    lw t0, {caller_stack_offset}(fp)")
                self.emit(f"    sw t0, {current_offset}(fp)")

        for local in function.locals:
            local_name = local.name.id
            current_offset -= 4
            self.local_offset_map[local_name] = current_offset
            if isinstance(local.type, type_ast.StructType):
                self.local_type_map[local_name] = local.type.name.id
            else:
                self.local_type_map[local_name] = None

        for statement in function.body:
            statement.accept(self)

        self.emit(f"\n{func_name}_epilog:")
        self.emit(f"    lw ra, {total_stack_size - 4}(sp)")
        self.emit(f"    lw fp, {total_stack_size - 8}(sp)")
        self.emit(f"    addi sp, sp, {total_stack_size}")
        if func_name == "main":
            self.emit("    li a0, 0")
            self.emit("    jal zero, exit")
        else:
            self.emit("    ret")

    def visit_int_type(self, int_type: type_ast.IntType):
        pass

    def visit_bool_type(self, bool_type: type_ast.BoolType):
        pass

    def visit_struct_type(self, struct_type: type_ast.StructType):
        pass

    def visit_return_type_real(self, return_type_real: type_ast.ReturnTypeReal):
        pass

    def visit_return_type_void(self, return_type_void: type_ast.ReturnTypeVoid):
        pass

    def visit_assignment_statement(self, assignment_statement: statement_ast.AssignmentStatement):
        self.temp_reg_counter = 0
        target = assignment_statement.target

        if isinstance(target, lvalue_ast.LValueID):
            assignment_statement.source.accept(self)
            var_name = target.id.id
            offset = self.local_offset_map.get(var_name)
            if offset is not None:
                self.emit(f"    sw a0, {offset}(fp)")
            else:
                self.emit(f"    la t0, {var_name}")
                self.emit(f"    sw a0, 0(t0)")
        elif isinstance(target, lvalue_ast.LValueDot):
            self.compute_lvalue_address(target)
            temp_addr = self.get_temp_reg()
            self.emit(f"    mv {temp_addr}, a0")
            assignment_statement.source.accept(self)
            self.emit(f"    sw a0, 0({temp_addr})")
            self.release_temp_reg()

    def compute_lvalue_address(self, lvalue):
        if isinstance(lvalue, lvalue_ast.LValueID):
            var_name = lvalue.id.id
            offset = self.local_offset_map.get(var_name)
            if offset is not None:
                self.emit(f"    lw a0, {offset}(fp)")
            else:
                self.emit(f"    la a0, {var_name}")
                self.emit(f"    lw a0, 0(a0)")
        elif isinstance(lvalue, lvalue_ast.LValueDot):
            if isinstance(lvalue.left, lvalue_ast.LValueID):
                var_name = lvalue.left.id.id
                offset = self.local_offset_map.get(var_name)
                if offset is not None:
                    self.emit(f"    lw a0, {offset}(fp)")
                else:
                    self.emit(f"    la a0, {var_name}")
                    self.emit(f"    lw a0, 0(a0)")
            else:
                self.compute_lvalue_address(lvalue.left)
                self.emit(f"    lw a0, 0(a0)")
            left_type = self.get_lvalue_type(lvalue.left)
            field_name = lvalue.id.id
            if left_type and left_type in self.struct_field_offsets:
                field_offset = self.struct_field_offsets[left_type].get(field_name, 0)
                if field_offset != 0:
                    self.emit(f"    addi a0, a0, {field_offset}")

    def get_struct_type(self, lvalue):
        return self.get_lvalue_type(lvalue)

    def visit_block_statement(self, block_statement: statement_ast.BlockStatement):
        for statement in block_statement.statements:
            statement.accept(self)

    def visit_conditional_statement(self, conditional_statement: statement_ast.ConditionalStatement):
        self.temp_reg_counter = 0
        else_label = self.get_label("else")
        end_label = self.get_label("endif")

        conditional_statement.guard.accept(self)

        self.emit(f"    beqz a0, {else_label}")

        conditional_statement.then_block.accept(self)

        self.emit(f"    j {end_label}")

        self.emit(f"{else_label}:")

        if conditional_statement.else_block:
            conditional_statement.else_block.accept(self)

        self.emit(f"{end_label}:")

    def visit_while_statement(self, while_statement: statement_ast.WhileStatement):
        self.temp_reg_counter = 0
        loop_start = self.get_label("while_start")
        loop_end = self.get_label("while_end")

        self.emit(f"{loop_start}:")

        while_statement.guard.accept(self)

        self.emit(f"    beqz a0, {loop_end}")

        while_statement.body.accept(self)

        self.emit(f"    j {loop_start}")

        self.emit(f"{loop_end}:")

    def visit_delete_statement(self, delete_statement: statement_ast.DeleteStatement):
        self.temp_reg_counter = 0
        delete_statement.expression.accept(self)
        self.emit("    jal ra, free")

    def visit_invocation_statement(self, invocation_statement: statement_ast.InvocationStatement):
        invocation_statement.expression.accept(self)

    def visit_println_statement(self, println_statement: statement_ast.PrintLnStatement):
        self.temp_reg_counter = 0
        println_statement.expression.accept(self)
        self.emit("    jal ra, print_int")
        self.emit("    li a0, 10")
        self.emit("    jal ra, print_char")

    def visit_print_statement(self, print_statement: statement_ast.PrintStatement):
        self.temp_reg_counter = 0
        print_statement.expression.accept(self)
        self.emit("    jal ra, print_int")

    def visit_return_empty_statement(self, return_empty_statement: statement_ast.ReturnEmptyStatement):
        self.emit(f"    j {self.current_function}_epilog")

    def visit_return_statement(self, return_statement: statement_ast.ReturnStatement):
        self.temp_reg_counter = 0
        if return_statement.expression:
            return_statement.expression.accept(self)
        self.emit(f"    j {self.current_function}_epilog")

    def visit_dot_expression(self, dot_expression: expression_ast.DotExpression):
        dot_expression.left.accept(self)
        left_type = self.get_expr_type(dot_expression.left)
        field_name = dot_expression.id.id
        if left_type and left_type in self.struct_field_offsets:
            field_offset = self.struct_field_offsets[left_type].get(field_name, 0)
            self.emit(f"    lw a0, {field_offset}(a0)")
        else:
            self.emit(f"    lw a0, 0(a0)")
        return "a0"

    def get_expression_struct_type(self, expr):
        return self.get_expr_type(expr)

    def visit_false_expression(self, false_expression: expression_ast.FalseExpression):
        self.emit("    li a0, 0")
        return "a0"

    def visit_true_expression(self, true_expression: expression_ast.TrueExpression):
        self.emit("    li a0, 1")
        return "a0"

    def visit_identifier_expression(self, identifier_expression: expression_ast.IdentifierExpression):
        var_name = identifier_expression.id
        offset = self.local_offset_map.get(var_name)
        if offset is not None:
            self.emit(f"    lw a0, {offset}(fp)")
        else:
            self.emit(f"    la a0, {var_name}")
            self.emit(f"    lw a0, 0(a0)")
        return "a0"

    def visit_new_expression(self, new_expression: expression_ast.NewExpression):
        struct_name = new_expression.id.id
        size = self.struct_sizes.get(struct_name, 4)
        self.emit(f"    li a0, {size}")
        self.emit("    jal ra, malloc")
        return "a0"

    def visit_null_expression(self, null_expression: expression_ast.NullExpression):
        self.emit("    li a0, 0")
        return "a0"

    def visit_read_expression(self, read_expression: expression_ast.ReadExpression):
        self.emit("    la a0, input_file_ptr")
        self.emit("    lw a0, 0(a0)")
        self.emit("    jal ra, read_int")
        return "a0"

    def visit_integer_expression(self, integer_expression: expression_ast.IntegerExpression):
        self.emit(f"    li a0, {integer_expression.value}")
        return "a0"

    def visit_invocation_expression(self, invocation_expression: expression_ast.InvocationExpression):
        func_name = invocation_expression.name.id
        args = invocation_expression.arguments
        num_args = len(args)

        if num_args == 0:
            self.emit(f"    jal ra, {func_name}")
            return "a0"

        num_stack_args = max(0, num_args - 8)
        
        self.emit(f"    addi sp, sp, -{num_args * 4}")
        
        for i, arg in enumerate(args):
            arg.accept(self)
            offset = (num_args - 1 - i) * 4
            self.emit(f"    sw a0, {offset}(sp)")

        for i in range(min(num_args, 8)):
            offset = (num_args - 1 - i) * 4
            self.emit(f"    lw a{i}, {offset}(sp)")

        if num_stack_args > 0:
            for i in range(num_stack_args):
                src_offset = (num_stack_args - 1 - i) * 4
                dst_offset = i * 4
                if src_offset != dst_offset:
                    self.emit(f"    lw t0, {src_offset}(sp)")
                    self.emit(f"    sw t0, {dst_offset}(sp)")
            cleanup = (num_args - num_stack_args) * 4
            self.emit(f"    addi sp, sp, {cleanup}")
        else:
            self.emit(f"    addi sp, sp, {num_args * 4}")

        self.emit(f"    jal ra, {func_name}")

        if num_stack_args > 0:
            self.emit(f"    addi sp, sp, {num_stack_args * 4}")

        return "a0"

    def visit_unary_expression(self, unary_expression: expression_ast.UnaryExpression):
        unary_expression.operand.accept(self)
        op = unary_expression.operator

        if op == expression_ast.Operator.MINUS:
            self.emit("    neg a0, a0")
        elif op == expression_ast.Operator.NOT:
            self.emit("    seqz a0, a0")

        return "a0"

    def visit_binary_expression(self, binary_expression: expression_ast.BinaryExpression):
        op = binary_expression.operator

        if op == expression_ast.Operator.AND:
            false_label = self.get_label("and_false")
            end_label = self.get_label("and_end")
            binary_expression.left.accept(self)
            self.emit(f"    beqz a0, {false_label}")
            binary_expression.right.accept(self)
            self.emit(f"    snez a0, a0")
            self.emit(f"    j {end_label}")
            self.emit(f"{false_label}:")
            self.emit("    li a0, 0")
            self.emit(f"{end_label}:")
            return "a0"

        if op == expression_ast.Operator.OR:
            true_label = self.get_label("or_true")
            end_label = self.get_label("or_end")
            binary_expression.left.accept(self)
            self.emit(f"    bnez a0, {true_label}")
            binary_expression.right.accept(self)
            self.emit(f"    snez a0, a0")
            self.emit(f"    j {end_label}")
            self.emit(f"{true_label}:")
            self.emit("    li a0, 1")
            self.emit(f"{end_label}:")
            return "a0"

        binary_expression.left.accept(self)
        temp_reg = self.get_temp_reg()
        self.emit(f"    mv {temp_reg}, a0")

        binary_expression.right.accept(self)

        if op == expression_ast.Operator.PLUS:
            self.emit(f"    add a0, {temp_reg}, a0")
        elif op == expression_ast.Operator.MINUS:
            self.emit(f"    sub a0, {temp_reg}, a0")
        elif op == expression_ast.Operator.TIMES:
            self.emit(f"    mul a0, {temp_reg}, a0")
        elif op == expression_ast.Operator.DIVIDE:
            self.emit(f"    div a0, {temp_reg}, a0")
        elif op == expression_ast.Operator.LT:
            self.emit(f"    slt a0, {temp_reg}, a0")
        elif op == expression_ast.Operator.LE:
            self.emit(f"    slt a0, a0, {temp_reg}")
            self.emit("    xori a0, a0, 1")
        elif op == expression_ast.Operator.GT:
            self.emit(f"    slt a0, a0, {temp_reg}")
        elif op == expression_ast.Operator.GE:
            self.emit(f"    slt a0, {temp_reg}, a0")
            self.emit("    xori a0, a0, 1")
        elif op == expression_ast.Operator.EQ:
            self.emit(f"    sub a0, {temp_reg}, a0")
            self.emit("    seqz a0, a0")
        elif op == expression_ast.Operator.NE:
            self.emit(f"    sub a0, {temp_reg}, a0")
            self.emit("    snez a0, a0")

        self.release_temp_reg()
        return "a0"

    def visit_lvalue_dot(self, lvalue_dot: lvalue_ast.LValueDot):
        pass

    def visit_lvalue_id(self, lvalue_id: lvalue_ast.LValueID):
        pass