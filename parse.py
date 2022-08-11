import sys
from .lex import TokenType, Lexer
from .emit import Emitter

"""
The entire grammar for our Teeny Tiny programming language:

    program ::= {statement}
    statement ::= "PRINT" (expression | string) nl
        | "IF" comparison "THEN" nl {statement} "ENDIF" nl
        | "WHILE" comparison "REPEAT" nl {statement} "ENDWHILE" nl
        | "LABEL" ident nl
        | "GOTO" ident nl
        | "LET" ident "=" expression nl
        | "INPUT" ident nl
    comparison ::= expression (("==" | "!=" | ">" | ">=" | "<" | "<=") expression)+
    expression ::= term {( "-" | "+" ) term}
    term ::= unary {( "/" | "*" ) unary}
    unary ::= ["+" | "-"] primary
    primary ::= number | ident
    nl ::= '\n'+
"""


# Parser object keeps track of current token and checks if the code matches the grammar.
class Parser:
    """
    The `curTokeHasType` and `checkPeekToken` functions will let the parser decide which 
    grammar rule to apply next, given the current token or the next one.
    """

    def __init__(self, lexer: Lexer, emitter: Emitter):
        self.lexer = lexer
        self.emitter = emitter

        self.symbolsDeclared = set()  # Variables declared so far.
        self.labelsDeclared = set()  # Labels declared so far.
        self.labelsGotoed = set()  # Labels goto'ed so far.

        self.curToken = None
        self.peekToken = None
        
        # Call this twice to initialize curToken and peekToken.
        self.skipCurToken()
        self.skipCurToken()    

    # Return true if the current token matches.
    def curTokeHasType(self, kind):
        return kind == self.curToken.kind

    # Return true if the next token matches.
    # def peekTokenHasType(self, kind):
    #     return kind == self.peekToken.kind

    # Return true if the current token is a comparison operator.
    def curTokenIsComparisonOperator(self):
        return self.curTokeHasType(TokenType.GT) or self.curTokeHasType(TokenType.GTEQ) or \
            self.curTokeHasType(TokenType.LT) or self.curTokeHasType(TokenType.LTEQ) or \
            self.curTokeHasType(TokenType.EQEQ) or self.curTokeHasType(TokenType.NOTEQ)

    # Advances the current token.
    # If there is a requirement on the type of the current token, it must be satisfied before advancing.
    def skipCurToken(self, requiredType=None):
        """
        倒数第二次调用 self.skipCurToken() 之后：

            self.curToken = <second-to-last-token>
            self.peekToken = <EOF>
            
            self.lexer.curChar = EOF  # lexer.getToken() 最后会调用 lexer.skipCurChar()

        此时再次调用 lexer.getToken() 会得到第二个 <EOF>，或者说以后会一直得到 <EOF>，
        因为 lexer.curChar 会一直是 EOF。所以再次调用 self.skipCurToken() 之后会有：

            self.curToken = <EOF>
            self.peekToken = <EOF>

        此时 parser 的工作应该就要停了，亦即 parser 的终止条件应该是 if self.curToken == <EOF>
        """

        if requiredType and not self.curTokeHasType(requiredType):
            self.abort("Expected " + requiredType.name + ", got " + self.curToken.kind.name)
        
        self.curToken = self.peekToken
        self.peekToken = self.lexer.getToken()

    def abort(self, message):
        sys.exit("Error. " + message)

    # Production rules.

    # program ::= {statement}
    def program(self):
        # print("PROGRAM")
        self.emitter.headerLine("#include <stdio.h>")
        self.emitter.headerLine("int main(void){")

        # Since some newlines are required in our grammar, need to skip the excess.
        while self.curTokeHasType(TokenType.NEWLINE):
            self.skipCurToken()

        # Parse all the statements in the program.
        while not self.curTokeHasType(TokenType.EOF):
            self.statement()

        # Check that each label referenced in a GOTO is declared.
        for label in self.labelsGotoed:
            if label not in self.labelsDeclared:
                self.abort("Attempting to GOTO to undeclared label: " + label)

        # Wrap things up.
        self.emitter.emitLine("return 0;")
        self.emitter.emitLine("}")

    # statement ::= "PRINT" (expression | string) nl
    #     | "IF" comparison "THEN" nl {statement} "ENDIF" nl
    #     | "WHILE" comparison "REPEAT" nl {statement} "ENDWHILE" nl
    #     | "LABEL" ident nl
    #     | "GOTO" ident nl
    #     | "LET" ident "=" expression nl
    #     | "INPUT" ident nl
    def statement(self):
        # Check the first token to see what kind of statement this is. 
        
        # "PRINT" (expression | string)
        if self.curTokeHasType(TokenType.PRINT):
            # print("STATEMENT-PRINT")
            self.skipCurToken()

            if self.curTokeHasType(TokenType.STRING):
                # Simple string, so print it.
                self.emitter.emitLine(r'printf("' + self.curToken.text + r'\n");')
                self.skipCurToken()
            else:
                # Expect an expression and print the result as a float.
                self.emitter.emit(r'printf("%.2f\n", (float)(')
                self.expression()
                self.emitter.emitLine(r'));')
        # "IF" comparison "THEN" {statement} "ENDIF"
        elif self.curTokeHasType(TokenType.IF):
            # print("STATEMENT-IF")
            self.skipCurToken()
            self.emitter.emit("if(")
            self.comparison()

            self.skipCurToken(requiredType=TokenType.THEN)
            self.nl()
            self.emitter.emitLine("){")

            # Zero or more statements in the if-body.
            while not self.curTokeHasType(TokenType.ENDIF):
                self.statement()

            self.skipCurToken(requiredType=TokenType.ENDIF)
            self.emitter.emitLine("}")
        # "WHILE" comparison "REPEAT" {statement} "ENDWHILE"
        elif self.curTokeHasType(TokenType.WHILE):
            # print("STATEMENT-WHILE")
            self.skipCurToken()
            self.emitter.emit("while(")
            self.comparison()

            self.skipCurToken(requiredType=TokenType.REPEAT)
            self.nl()
            self.emitter.emitLine("){")

            # Zero or more statements in the loop body.
            while not self.curTokeHasType(TokenType.ENDWHILE):
                self.statement()

            self.skipCurToken(requiredType=TokenType.ENDWHILE)
            self.emitter.emitLine("}")
        # "LABEL" ident
        elif self.curTokeHasType(TokenType.LABEL):
            # print("STATEMENT-LABEL")
            self.skipCurToken()

            # Make sure this label doesn't already exist.
            if self.curToken.text in self.labelsDeclared:
                self.abort("Label already exists: " + self.curToken.text)
            self.labelsDeclared.add(self.curToken.text)

            self.emitter.emitLine(self.curToken.text + ":")
            self.skipCurToken(requiredType=TokenType.IDENT)
        # "GOTO" ident
        elif self.curTokeHasType(TokenType.GOTO):
            # print("STATEMENT-GOTO")
            self.skipCurToken()

            self.labelsGotoed.add(self.curToken.text)

            self.emitter.emitLine("goto " + self.curToken.text + ";")
            self.skipCurToken(requiredType=TokenType.IDENT)
        # "LET" ident "=" expression
        elif self.curTokeHasType(TokenType.LET):
            # print("STATEMENT-LET")
            self.skipCurToken()

            #  Check if ident exists in symbol table. If not, declare it.
            """
            Why emitter.headerLine()? Because the first time a variable is referenced in Teeny Tiny, 
            it should emit a variable declaration in C, and place it at the top of the main function 
            (this is an old C convention).
            """
            if self.curToken.text not in self.symbolsDeclared:
                self.symbolsDeclared.add(self.curToken.text)
                self.emitter.headerLine("float " + self.curToken.text + ";")

            self.emitter.emit(self.curToken.text + " = ")
            self.skipCurToken(requiredType=TokenType.IDENT)
            self.skipCurToken(requiredType=TokenType.EQ)

            self.expression()
            self.emitter.emitLine(";")
        # "INPUT" ident
        elif self.curTokeHasType(TokenType.INPUT):
            # print("STATEMENT-INPUT")
            self.skipCurToken()

            # If variable doesn't exist, declare it.
            # Similarly, emit a declaration to headline if the symbol does not exist
            if self.curToken.text not in self.symbolsDeclared:
                self.symbolsDeclared.add(self.curToken.text)
                self.emitter.headerLine("float " + self.curToken.text + ";")

            # Emit scanf but also validate the input. If invalid, set the variable to 0 and clear the input.
            """
            We could just emit 'scanf("%f", &foo);', but that won't handle invalid input, such as when 
            a user enters a letter. So we must also check if scanf returns 0. If it does, we clear the 
            input buffer and we set the input variable to 0.
            """
            self.emitter.emitLine("if(0 == scanf(\"%" + "f\", &" + self.curToken.text + ")) {")
            self.emitter.emitLine(self.curToken.text + " = 0;")
            self.emitter.emit("scanf(\"%")
            self.emitter.emitLine("*s\");")
            self.emitter.emitLine("}")
            self.skipCurToken(requiredType=TokenType.IDENT)
        # This is not a valid statement. Error!
        else:
            self.abort("Invalid statement at " + self.curToken.text + " (" + self.curToken.kind.name + ")")

        # Newline.
        # 不管你是何种类型的 statement，最后肯定是个 newline，所以这里肯定是要调用 nl() 一次的
        self.nl()

    # nl ::= '\n'+
    def nl(self):
        # print("NEWLINE")
		
        # Require at least one newline.
        self.skipCurToken(requiredType=TokenType.NEWLINE)
        # But we will allow extra newlines too, of course.
        while self.curTokeHasType(TokenType.NEWLINE):
            self.skipCurToken()

    # comparison ::= expression (("==" | "!=" | ">" | ">=" | "<" | "<=") expression)+
    def comparison(self):
        # print("COMPARISON")

        self.expression()
        # Must be at least one comparison operator and another expression.
        if self.curTokenIsComparisonOperator():
            self.emitter.emit(self.curToken.text)
            self.skipCurToken()
            self.expression()
        else:
            self.abort("Expected comparison operator at: " + self.curToken.text)

        # Can have 0 or more comparison operator and expressions.
        while self.curTokenIsComparisonOperator():
            self.emitter.emit(self.curToken.text)
            self.skipCurToken()
            self.expression()

    # expression ::= term {( "-" | "+" ) term}
    # 我们区分 expression 和 term 是因为 precedence (结合律的优先级)
    # 如果我们定义 expression ::= term {( "-" | "+" | "/" | "*") term} 的话，
    #   那么我们就无法处理类似 1+2*3 这样的算式
    def expression(self):
        # print("EXPRESSION")

        self.term()
        # Can have 0 or more +/- and expressions.
        while self.curTokeHasType(TokenType.PLUS) or self.curTokeHasType(TokenType.MINUS):
            self.emitter.emit(self.curToken.text)
            self.skipCurToken()
            self.term()

    # term ::= unary {( "/" | "*" ) unary}
    def term(self):
        # print("TERM")

        self.unary()
        # Can have 0 or more *// and expressions.
        while self.curTokeHasType(TokenType.ASTERISK) or self.curTokeHasType(TokenType.SLASH):
            self.emitter.emit(self.curToken.text)
            self.skipCurToken()
            self.unary()

    # unary ::= ["+" | "-"] primary
    def unary(self):
        # print("UNARY")

        # Optional unary +/-
        if self.curTokeHasType(TokenType.PLUS) or self.curTokeHasType(TokenType.MINUS):
            self.emitter.emit(self.curToken.text)
            self.skipCurToken()        
        self.primary()

    # primary ::= number | ident
    def primary(self):
        # print("PRIMARY (" + self.curToken.text + ")")

        if self.curTokeHasType(TokenType.NUMBER): 
            self.emitter.emit(self.curToken.text)
            self.skipCurToken()
        elif self.curTokeHasType(TokenType.IDENT):
            # Ensure the variable already exists.
            if self.curToken.text not in self.symbolsDeclared:
                self.abort("Referencing variable before assignment: " + self.curToken.text)

            self.emitter.emit(self.curToken.text)
            self.skipCurToken()
        else:
            # Error!
            self.abort("Unexpected token at " + self.curToken.text)