import sys
from antlr4 import *
from MiniLexer import MiniLexer
from MiniParser import MiniParser
from mini_ast_visitor import MiniToASTVisitor
from pretty_print_ast_visitor import PPASTVisitor
from static_semantic_ast_visitor import StaticSemanticASTVisitor
from codegen_visitor import CodeGenVisitor
import argparse

def main(argv):
    parser = argparse.ArgumentParser(description='Mini compiler')
    parser.add_argument('input_file', help='Input .mini file')
    parser.add_argument('-p', '--prettyprint', action='store_true', 
                        help='Pretty print the AST')
    parser.add_argument('-s', '--symbols', action='store_true',
                        help='Print symbol tables (for debugging)')
    
    args = parser.parse_args(argv[1:])
    
    input_stream = FileStream(args.input_file)
    lexer = MiniLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = MiniParser(stream)
    program_ctx = parser.program()

    if parser.getNumberOfSyntaxErrors() > 0:
        print("Syntax errors.")
        return
    
    print("Parse successful.")
    
    mini_ast_visitor = MiniToASTVisitor()
    mini_ast = mini_ast_visitor.visitProgram(program_ctx)

    if args.prettyprint:
        pp_visitor = PPASTVisitor()
        pp_str = pp_visitor.pretty_print(mini_ast)
        print(pp_str, end="")

    visitor = StaticSemanticASTVisitor()
    errors = visitor.analyze(mini_ast)

    if errors == 0:
        codegen = CodeGenVisitor()
        assembly = codegen.visit_program(mini_ast)

        assembly_output = args.input_file.replace('.mini', '.s')
        
        with open(assembly_output, 'w') as f:
            f.write(assembly)

        print(f"Assembly code generated in {assembly_output}")

if __name__ == '__main__':
    main(sys.argv)