from miniast import mini_ast, program_ast, type_ast, statement_ast, expression_ast, lvalue_ast
from typing import Dict, List, Optional, Any

class SymbolTable:
    # Simple scoped symbol table that supports nested scopes
    def __init__(self, parent=None):
        # creates symbols and stores parent nodes
        self.symbols: Dict[str, Any] = {}
        self.parent = parent
    
    def insert(self, name: str, info: Any) -> bool:
        #inserts info for name into the current scope, return false if name exists locally
        if name in self.symbols:
            return False
        self.symbols[name] = info
        return True
    
    def lookup(self, name: str) -> Optional[Any]:
        #Recursive lookup, returns symbol from current scope, or asks parent
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None
    
    def lookup_local(self, name: str) -> Optional[Any]:
        #only returns symbol from current scope
        return self.symbols.get(name)


class TypeInfo:
    #Thin wrapper around AST type objects used for runtime equality and comparison
    def __init__(self, type_obj):
        #store type object
        self.type_obj = type_obj
    
    def __eq__(self, other):
        #compares two TypeInfo instances
        if not isinstance(other, TypeInfo):
            return False
        return self.compare_types(self.type_obj, other.type_obj)
    
    @staticmethod
    # static compare method
    def compare_types(t1, t2) -> bool:
        if isinstance(t1, type_ast.IntType) and isinstance(t2, type_ast.IntType):
            return True
        if isinstance(t1, type_ast.BoolType) and isinstance(t2, type_ast.BoolType):
            return True
        if isinstance(t1, type_ast.StructType) and isinstance(t2, type_ast.StructType):
            return t1.name.id == t2.name.id
        if isinstance(t1, type_ast.ReturnTypeVoid) and isinstance(t2, type_ast.ReturnTypeVoid):
            return True
        return False
#Data containers used as entires stored in the symbol table

class FunctionInfo:
    def __init__(self, name: str, return_type, params: List[program_ast.Declaration], linenum: int):
        self.name = name
        self.return_type = return_type
        self.params = params
        self.linenum = linenum


class VariableInfo:
    def __init__(self, name: str, type_obj, linenum: int):
        self.name = name
        self.type_obj = type_obj
        self.linenum = linenum


class StructInfo:
    def __init__(self, name: str, fields: Dict[str, program_ast.Declaration], linenum: int):
        self.name = name
        self.fields = fields
        self.linenum = linenum


class StaticSemanticASTVisitor(mini_ast.ASTVisitor):
    def __init__(self):
        self.errors: List[str] = [] # collects error messages
        self.global_scope = SymbolTable() # symbol table, swithces to current scope when entering functions
        self.current_scope = self.global_scope
        self.struct_table: Dict[str, StructInfo] = {} # registry of struct delcarations
        self.current_function: Optional[FunctionInfo] = None # used for checks inside functions
        self.has_main = False # flag to check if main function is present
    
    def analyze(self, program: program_ast.Program) -> int:
        # entry point for analysis, calls accept on the program node
        program.accept(self)
        for error in self.errors:
            print(error)
        print(f"ERRORS FOUND {len(self.errors)}")
        return len(self.errors)
    
    def add_error(self, message: str, linenum: int):
        self.errors.append(f"ERROR. {message} #{linenum}")
    
    def get_type_string(self, type_obj) -> str:
        if isinstance(type_obj, type_ast.IntType):
            return "int"
        elif isinstance(type_obj, type_ast.BoolType):
            return "bool"
        elif isinstance(type_obj, type_ast.StructType):
            return f"struct {type_obj.name.id}"
        elif isinstance(type_obj, type_ast.ReturnTypeVoid):
            return "void"
        else:
            return "unknown"
    
    def visit_program(self, program: program_ast.Program):
        # First pass: register struct types. If struct name is duplicates, require error
        # Second pass: call visit_type_declaration for each typ eto validate fields and populate StructInfo
        # Third pass: process top level variable declarations
        # Fourth pass: declare funcitons into the global scope
        # Fifth pass: call accept(self) for each function
        # If no main found, add error
        # Functions are first insereted into the global scope
        for type_decl in program.types:
            struct_name = type_decl.name.id
            if struct_name in self.struct_table:
                self.add_error(f"Struct '{struct_name}' already declared", type_decl.linenum)
            else:
                self.struct_table[struct_name] = StructInfo(struct_name, {}, type_decl.linenum)
        
        for type_decl in program.types:
            type_decl.accept(self)
        
        for decl in program.declarations:
            decl.accept(self)
        
        for func in program.functions:
            func_name = func.name.id
            if self.global_scope.lookup_local(func_name):
                self.add_error(f"Function '{func_name}' already declared", func.linenum)
            else:
                func_info = FunctionInfo(func_name, func.ret_type, func.params, func.linenum)
                self.global_scope.insert(func_name, func_info)
                
                if func_name == "main":
                    self.has_main = True
                    if len(func.params) != 0:
                        self.add_error("main() must take no arguments", func.linenum)
                    if not isinstance(func.ret_type, type_ast.IntType):
                        self.add_error("main() must return int", func.linenum)
        
        for func in program.functions:
            func.accept(self)
        
        if not self.has_main:
            self.add_error("Program must have a main() function", 1)
    
    def visit_type_declaration(self, type_decl: program_ast.TypeDeclaration):
        # For a struct type declaration, populate its fields in the struct table
        # If a field name is duplicate, add error
        # Stores the built strucutre into corresponding StructInfo in struct_table
        struct_name = type_decl.name.id
        struct_info = self.struct_table[struct_name]
        
        field_dict = {}
        for field in type_decl.fields:
            field_name = field.name.id
            if field_name in field_dict:
                self.add_error(f"Field '{field_name}' already declared in struct '{struct_name}'", field.linenum)
            else:
                field_dict[field_name] = field
        
        struct_info.fields = field_dict
    
    def visit_declaration(self, decl: program_ast.Declaration):
        # Handles top-level and local variable declarations
        # If variable name is duplicate in current scope, add error
        # Inserts variable into current scope
        var_name = decl.name.id
        
        if self.current_scope.lookup_local(var_name):
            self.add_error(f"Variable '{var_name}' already declared in this scope", decl.linenum)
            return
        
        var_info = VariableInfo(var_name, decl.type, decl.linenum)
        self.current_scope.insert(var_name, var_info)
    
    def visit_function(self, func: program_ast.Function):
        # Sets up a fresh scope for the function
        # Retreives the function info from the global scope
        # Processes parameters, checking for duplicates and inserting into current scope
        # Processes local variable declarations, checking for duplicates with parameters and inserting into current scope
        # Processes each statement in the function body
        # Restores the current scope to global scope after processing
        # Resets current function to None
        func_name = func.name.id
        
        self.current_scope = SymbolTable(self.global_scope)
        self.current_function = self.global_scope.lookup(func_name)
        
        param_names = set()
        for param in func.params:
            param_name = param.name.id
            if param_name in param_names:
                self.add_error(f"Parameter '{param_name}' already declared", param.linenum)
            else:
                param_names.add(param_name)
                var_info = VariableInfo(param_name, param.type, param.linenum)
                self.current_scope.insert(param_name, var_info)
        
        for local in func.locals:
            local_name = local.name.id
            if local_name in param_names:
                self.add_error(f"Local variable '{local_name}' cannot redeclare parameter", local.linenum)
            else:
                local.accept(self)
        
        for stmt in func.body:
            stmt.accept(self)
        
        self.current_scope = self.global_scope
        self.current_function = None
    
    def visit_int_type(self, int_type: type_ast.IntType):
        return TypeInfo(int_type)
    
    def visit_bool_type(self, bool_type: type_ast.BoolType):
        return TypeInfo(bool_type)
    
    def visit_struct_type(self, struct_type: type_ast.StructType):
        return TypeInfo(struct_type)
    
    def visit_return_type_real(self, return_type_real: type_ast.ReturnTypeReal):
        return return_type_real.type_.accept(self)
    
    def visit_return_type_void(self, return_type_void: type_ast.ReturnTypeVoid):
        return TypeInfo(return_type_void)
    
    def visit_assignment_statement(self, stmt: statement_ast.AssignmentStatement):
        #Gets target and source types
        # If either is None, skip further checks
        target_type = stmt.target.accept(self)
        source_type = stmt.source.accept(self)
        
        if target_type and source_type:
            if isinstance(stmt.source, expression_ast.NullExpression):
                if not isinstance(target_type.type_obj, type_ast.StructType):
                    self.add_error("null can only be assigned to struct types", stmt.linenum)
            elif not target_type == source_type:
                self.add_error(
                    f"Type mismatch in assignment: cannot assign {self.get_type_string(source_type.type_obj)} to {self.get_type_string(target_type.type_obj)}",
                    stmt.linenum
                )
    
    def visit_block_statement(self, stmt: statement_ast.BlockStatement):

        for s in stmt.statements:
            s.accept(self)
    
    def visit_conditional_statement(self, stmt: statement_ast.ConditionalStatement):
        # Both requrie the guard to be boolean
        guard_type = stmt.guard.accept(self)
        if guard_type and not isinstance(guard_type.type_obj, type_ast.BoolType):
            self.add_error("if statement guard must be boolean", stmt.linenum)
        
        stmt.then_block.accept(self)
        if stmt.else_block:
            stmt.else_block.accept(self)
    
    def visit_while_statement(self, stmt: statement_ast.WhileStatement):
        guard_type = stmt.guard.accept(self)
        if not guard_type or not isinstance(guard_type.type_obj, type_ast.BoolType):
            self.add_error("while statement guard must be boolean", stmt.linenum)
        
        stmt.body.accept(self)
    
    def visit_delete_statement(self, stmt: statement_ast.DeleteStatement):
        expr_type = stmt.expression.accept(self)
        if expr_type and not isinstance(expr_type.type_obj, type_ast.StructType):
            self.add_error("delete requires a struct type", stmt.linenum)
    
    def visit_invocation_statement(self, stmt: statement_ast.InvocationStatement):
        # Looks up function in global scope, checks arity, verifies function existence
        stmt.expression.accept(self)
    
    def visit_println_statement(self, stmt: statement_ast.PrintLnStatement):
        expr_type = stmt.expression.accept(self)
        if not expr_type or not isinstance(expr_type.type_obj, type_ast.IntType):
            self.add_error("print statement requires int argument", stmt.linenum)
    
    def visit_print_statement(self, stmt: statement_ast.PrintStatement):
        expr_type = stmt.expression.accept(self)
        if not expr_type or not isinstance(expr_type.type_obj, type_ast.IntType):
            self.add_error("print statement requires int argument", stmt.linenum)
    
    def visit_return_statement(self, stmt: statement_ast.ReturnStatement):
        if not self.current_function:
            return
        
        expr_type = stmt.expression.accept(self) if stmt.expression else None
        
        if isinstance(self.current_function.return_type, type_ast.ReturnTypeVoid):
            if expr_type:
                self.add_error(f"Function '{self.current_function.name}' with void return type cannot return a value", stmt.linenum)
        else:
            if not expr_type:
                self.add_error(
                    f"Function '{self.current_function.name}' must return a value of type {self.get_type_string(self.current_function.return_type)}",
                    stmt.linenum
                )
            else:
                expected_type = TypeInfo(self.current_function.return_type)
                # Allow null to be returned for struct types
                if isinstance(stmt.expression, expression_ast.NullExpression):
                    if not isinstance(self.current_function.return_type, type_ast.StructType):
                        self.add_error(
                            f"Cannot return null for non-struct type {self.get_type_string(self.current_function.return_type)}",
                            stmt.linenum
                        )
                elif not expr_type == expected_type:
                    self.add_error(
                        f"Return type mismatch: expected {self.get_type_string(self.current_function.return_type)}, got {self.get_type_string(expr_type.type_obj)}",
                        stmt.linenum
                    )

    def visit_return_empty_statement(self, stmt: statement_ast.ReturnEmptyStatement):
        if self.current_function and not isinstance(self.current_function.return_type, type_ast.ReturnTypeVoid):
            self.add_error(
                f"Function '{self.current_function.name}' must return a value of type {self.get_type_string(self.current_function.return_type)}",
                stmt.linenum
            )
        
    def visit_dot_expression(self, expr: expression_ast.DotExpression):
        left_type = expr.left.accept(self)
        
        if not left_type:
            return None
        
        if not isinstance(left_type.type_obj, type_ast.StructType):
            self.add_error("Dot operator requires struct type", expr.linenum)
            return None
        
        struct_name = left_type.type_obj.name.id
        if struct_name not in self.struct_table:
            return None
        
        struct_info = self.struct_table[struct_name]
        field_name = expr.id.id
        
        if field_name not in struct_info.fields:
            self.add_error(f"Struct '{struct_name}' has no field '{field_name}'", expr.linenum)
            return None
        
        field = struct_info.fields[field_name]
        return TypeInfo(field.type)
    
    def visit_false_expression(self, expr: expression_ast.FalseExpression):
        return TypeInfo(type_ast.BoolType())
    
    def visit_true_expression(self, expr: expression_ast.TrueExpression):
        return TypeInfo(type_ast.BoolType())
    
    def visit_identifier_expression(self, expr: expression_ast.IdentifierExpression):
        var_name = expr.id
        var_info = self.current_scope.lookup(var_name)
        
        if not var_info:
            self.add_error(f"Variable '{var_name}' not declared", expr.linenum)
            return None
        
        if isinstance(var_info, VariableInfo):
            return TypeInfo(var_info.type_obj)
        
        self.add_error(f"'{var_name}' is not a variable", expr.linenum)
        return None
    
    def visit_new_expression(self, expr: expression_ast.NewExpression):
        struct_name = expr.id.id
        
        if struct_name not in self.struct_table:
            self.add_error(f"Struct type '{struct_name}' not defined", expr.linenum)
            return None
        
        return TypeInfo(type_ast.StructType(expr.linenum, expr.id))
    
    def visit_null_expression(self, expr: expression_ast.NullExpression):
        return TypeInfo(type_ast.StructType(expr.linenum, expression_ast.IdentifierExpression(expr.linenum, "__null__")))
    
    def visit_read_expression(self, expr: expression_ast.ReadExpression):
        return TypeInfo(type_ast.IntType())
    
    def visit_integer_expression(self, expr: expression_ast.IntegerExpression):
        return TypeInfo(type_ast.IntType())
    
    def visit_invocation_expression(self, expr: expression_ast.InvocationExpression):
        # Lookup function by name in global scope
        # Check arugment count equals parameter count

        func_name = expr.name.id
        func_info = self.global_scope.lookup(func_name)
        
        if not func_info:
            self.add_error(f"Function '{func_name}' not declared", expr.linenum)
            return None
        
        if not isinstance(func_info, FunctionInfo):
            self.add_error(f"'{func_name}' is not a function", expr.linenum)
            return None
        
        if len(expr.arguments) != len(func_info.params):
            self.add_error(
                f"Function '{func_name}' expects {len(func_info.params)} arguments, got {len(expr.arguments)}",
                expr.linenum
            )
            return TypeInfo(func_info.return_type)
        
        for i, (arg, param) in enumerate(zip(expr.arguments, func_info.params)):
            arg_type = arg.accept(self)
            param_type = TypeInfo(param.type)
            
            if arg_type and not arg_type == param_type:
                if not (isinstance(arg, expression_ast.NullExpression) and isinstance(param.type, type_ast.StructType)):
                    self.add_error(
                        f"Argument {i+1} to '{func_name}': expected {self.get_type_string(param.type)}, got {self.get_type_string(arg_type.type_obj)}",
                        expr.linenum
                    )
        
        return TypeInfo(func_info.return_type)
    
    def visit_unary_expression(self, expr: expression_ast.UnaryExpression):
        operand_type = expr.operand.accept(self)
        
        if not operand_type:
            return None
        
        if expr.operator == expression_ast.Operator.NOT:
            if not isinstance(operand_type.type_obj, type_ast.BoolType):
                self.add_error("! operator requires boolean operand", expr.linenum)
            return TypeInfo(type_ast.BoolType())
        elif expr.operator == expression_ast.Operator.MINUS:
            if not isinstance(operand_type.type_obj, type_ast.IntType):
                self.add_error("- operator requires int operand", expr.linenum)
            return TypeInfo(type_ast.IntType())
        
        return None
    
    def visit_binary_expression(self, expr: expression_ast.BinaryExpression):
        left_type = expr.left.accept(self)
        right_type = expr.right.accept(self)
        
        if not left_type or not right_type:
            return None
        
        op = expr.operator
        
        if op in [expression_ast.Operator.TIMES, expression_ast.Operator.DIVIDE,
                expression_ast.Operator.PLUS, expression_ast.Operator.MINUS]:
            left_ok = isinstance(left_type.type_obj, type_ast.IntType)
            right_ok = isinstance(right_type.type_obj, type_ast.IntType)
            if not (left_ok and right_ok):
                self.add_error(f"Operator {op.value} requires int operands", expr.linenum)
            return TypeInfo(type_ast.IntType())
        
        elif op in [expression_ast.Operator.LT, expression_ast.Operator.LE,
                    expression_ast.Operator.GT, expression_ast.Operator.GE]:
            left_ok = isinstance(left_type.type_obj, type_ast.IntType)
            right_ok = isinstance(right_type.type_obj, type_ast.IntType)
            if not (left_ok and right_ok):
                self.add_error(f"Operator {op.value} requires int operands", expr.linenum)
                return None 
            return TypeInfo(type_ast.BoolType())
        
        elif op in [expression_ast.Operator.EQ, expression_ast.Operator.NE]:
            left_is_int = isinstance(left_type.type_obj, type_ast.IntType)
            right_is_int = isinstance(right_type.type_obj, type_ast.IntType)
            left_is_struct = isinstance(left_type.type_obj, type_ast.StructType)
            right_is_struct = isinstance(right_type.type_obj, type_ast.StructType)
            
            left_is_null = isinstance(expr.left, expression_ast.NullExpression)
            right_is_null = isinstance(expr.right, expression_ast.NullExpression)
            
            if left_is_int and right_is_int:
                pass
            elif (left_is_struct or left_is_null) and (right_is_struct or right_is_null):
                if not (left_is_null or right_is_null):
                    pass
            else:
                self.add_error(f"Operator {op.value} requires matching types (int or struct)", expr.linenum)
            
            return TypeInfo(type_ast.BoolType())
        
        elif op in [expression_ast.Operator.AND, expression_ast.Operator.OR]:
            left_ok = isinstance(left_type.type_obj, type_ast.BoolType)
            right_ok = isinstance(right_type.type_obj, type_ast.BoolType)
            if not (left_ok and right_ok):
                self.add_error(f"Operator {op.value} requires boolean operands", expr.linenum)
            return TypeInfo(type_ast.BoolType())
        
        return None
    
    def visit_lvalue_dot(self, lvalue: lvalue_ast.LValueDot):
        left_type = lvalue.left.accept(self)
        
        if not left_type:
            return None
        
        if not isinstance(left_type.type_obj, type_ast.StructType):
            self.add_error("Dot operator requires struct type", lvalue.linenum)
            return None
        
        struct_name = left_type.type_obj.name.id
        if struct_name not in self.struct_table:
            return None
        
        struct_info = self.struct_table[struct_name]
        field_name = lvalue.id.id
        
        if field_name not in struct_info.fields:
            self.add_error(f"Struct '{struct_name}' has no field '{field_name}'", lvalue.linenum)
            return None
        
        field = struct_info.fields[field_name]
        return TypeInfo(field.type)
    
    def visit_lvalue_id(self, lvalue: lvalue_ast.LValueID):
        var_name = lvalue.id.id
        var_info = self.current_scope.lookup(var_name)
        
        if not var_info:
            self.add_error(f"Variable '{var_name}' not declared", lvalue.linenum)
            return None
        
        if isinstance(var_info, VariableInfo):
            return TypeInfo(var_info.type_obj)
        
        self.add_error(f"'{var_name}' is not a variable", lvalue.linenum)
        return None