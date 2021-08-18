from dataclasses import dataclass
import enum
import sys


class TokenType(enum.Enum):
    EOF = -1
    NEWLINE = 0
    NUMBER = 1
    IDENT = 2  # identifiers
    STRING = 3

    # Keywords.
    LABEL = 101
    GOTO = 102
    PRINT = 103
    INPUT = 104
    LET = 105
    IF = 106
    THEN = 107
    ENDIF = 108
    WHILE = 109
    REPEAT = 110
    ENDWHILE = 111

    # Operators.
    EQ = 201
    PLUS = 202
    MINUS = 203
    ASTERISK = 204
    SLASH = 205
    EQEQ = 206
    NOTEQ = 207
    LT = 208
    LTEQ = 209
    GT = 210
    GTEQ = 211


@dataclass
class Token:
    text: str  # The token's actual text. Used for identifiers, strings, and numbers.
    kind: TokenType  # The TokenType that this token is classified as.

    @staticmethod
    def mapTextToKeywordType(tokenText):
        """
        这里注意 enum 的术语：
            
        - TokenType 是一个 enum (class)
        - TokenType.EOF 是这个 enum 的一个 member
            - EOF 是这个 enum member 的 name
            - -1 是这个 enum member 的 value

        API 上有：

        - `EOF.name` 返回一个 string "EOF"
        - `EOF.value` 返回它被赋的 value

        所以这个函数的逻辑是：
        
        - 给定一个 tokenText，去 match TokenType 的 name，如果 match 上了，并且这个 TokenType 是 keyword，则返回这个 TokenType；
        - 如果没有 match 或者 TokenType 不是 keyword，则返回 None

        判断 TokenType 是不是 keyword 的逻辑：

        - (非常简单粗暴) 就是我们故意把 keyword 的 value 都设置成 100 到 200 之间， value 在这个区间的 TokenType 都是 keyword
        """
        for kind in TokenType:
            # Relies on all keyword enum values being 1XX.
            if kind.name == tokenText and kind.value >= 100 and kind.value < 200:
                return kind
        return None


class Lexer:
    EOF = '\0'  # Use \0 as EOF.
    NEWLINE = '\n'
    HASHMARK = '#'
    WHITESPACE = set([' ', '\t', '\r'])
    DOUBLEQUOTE = r'"'

    def __init__(self, source):
        # Source code to lex as a string.
        # Append a newline to simplify lexing/parsing the last token/statement.
        self.source = source + self.NEWLINE
        # Current character in the string.
        self.curChar = ''
        # Current position in the string.
        self.curPos = -1

        # Proceed to the 1st character.
        # 所以前面 curPos = -1 相当于是个 dummy head
        self.skipCurChar()

    # Process the next character.
    def skipCurChar(self):
        self.curPos += 1

        if self.curPos >= len(self.source):
            self.curChar = self.EOF
        else:
            self.curChar = self.source[self.curPos]

    # Return the lookahead character.
    # 注意 skipCurChar() 是更新 curChar 和 curPos，不返回任何值
    # 但 peek() 是返回 source[curPos+1]，并不更新 curChar 和 curPos
    def peek(self):
        if self.curPos + 1 >= len(self.source):
            return self.EOF
        else:
            return self.source[self.curPos+1]

    # Invalid token found, print error message and exit.
    def abort(self, message):
        sys.exit("Lexing error. " + message)

    # Skip whitespace except newlines, which we will use to indicate the end of a statement.
    def skipWhitespace(self):
        while self.curChar in self.WHITESPACE:
            self.skipCurChar()

    # Skip comments in the code.
    def skipComment(self):
        if self.curChar == self.HASHMARK:
            while self.curChar != self.NEWLINE:
                self.skipCurChar()

    # Return the token starting from curChar.
    def getToken(self):
        self.skipWhitespace()
        self.skipComment()

        token = None

        # Check the first character of this token to see if we can decide what it is.
        # If it is a multiple character operator (e.g., !=), number, identifier, or keyword then we will process the rest.
        if self.curChar == '+':
            token = Token(self.curChar, TokenType.PLUS)
        elif self.curChar == '-':
            token = Token(self.curChar, TokenType.MINUS)
        elif self.curChar == '*':
            token = Token(self.curChar, TokenType.ASTERISK)
        elif self.curChar == '/':
            token = Token(self.curChar, TokenType.SLASH)
        elif self.curChar == self.NEWLINE:
            token = Token(self.curChar, TokenType.NEWLINE)
        elif self.curChar == self.EOF:
            token = Token(self.curChar, TokenType.EOF)
        elif self.curChar == '=':
            # Check whether this is token is = or ==
            if self.peek() == '=':
                lastChar = self.curChar
                self.skipCurChar()
                token = Token(lastChar + self.curChar, TokenType.EQEQ)
            else:
                token = Token(self.curChar, TokenType.EQ)
        elif self.curChar == '>':
            # Check whether this is token is > or >=
            if self.peek() == '=':
                lastChar = self.curChar
                self.skipCurChar()
                token = Token(lastChar + self.curChar, TokenType.GTEQ)
            else:
                token = Token(self.curChar, TokenType.GT)
        elif self.curChar == '<':
                # Check whether this is token is < or <=
                if self.peek() == '=':
                    lastChar = self.curChar
                    self.skipCurChar()
                    token = Token(lastChar + self.curChar, TokenType.LTEQ)
                else:
                    token = Token(self.curChar, TokenType.LT)
        elif self.curChar == '!':
            # Check whether this is token is !=
            if self.peek() == '=':
                lastChar = self.curChar
                self.skipCurChar()
                token = Token(lastChar + self.curChar, TokenType.NOTEQ)
            else:
                self.abort("Expected !=, got !" + self.peek())
        elif self.curChar == self.DOUBLEQUOTE:
            # Get characters between double quotations.
            # 我们假设了字符串只能用双引号
            self.skipCurChar()
            startPos = self.curPos

            while self.curChar != self.DOUBLEQUOTE:  # 循环至 ending double quote
                # Don't allow special characters in the string. 
                # No escape characters, newlines, tabs, or %.
                # We will be using C's printf on this string.
                if self.curChar == '\r' or self.curChar == '\n' or self.curChar == '\t' or self.curChar == '\\' or self.curChar == '%':
                    self.abort("Illegal character in string.")
                
                self.skipCurChar()

            # startPos 是 starting quote 后的第一个字符 (should be included)
            # curPos 是 ending quote (should be excluded)
            token = Token(self.source[startPos : self.curPos], TokenType.STRING)
        elif self.curChar.isdigit():
            # Leading character is a digit, so this must be a number.
            # Get all consecutive digits and decimal if there is one.
            startPos = self.curPos

            while self.peek().isdigit():
                self.skipCurChar()

            if self.peek() == '.':  # Found decimal
                self.skipCurChar()

                # Must have at least one digit after decimal.
                if not self.peek().isdigit(): 
                    self.abort("Illegal character in number.")
                while self.peek().isdigit():
                    self.skipCurChar()

            # startPos 是最高位 digit (should be included)
            # curPos 是最低位 digit (should be included)
            token = Token(self.source[startPos : self.curPos+1], TokenType.NUMBER)
        elif self.curChar.isalpha():
            # Leading character is a letter, so this must be an identifier or a keyword.
            # Get all consecutive alpha numeric characters.
            startPos = self.curPos
            while self.peek().isalnum():
                self.skipCurChar()

            # startPos 是 identifier 第一个字符 (should be included)
            # curPos 是 identifier 最后一个字符 (should be included)
            tokenText = self.source[startPos : self.curPos+1]

            # Check if the token text is a keyword
            keywordType = Token.mapTextToKeywordType(tokenText)
            if keywordType == None:  # the token is an identifier
                token = Token(tokenText, TokenType.IDENT)
            else:   # the token is a keyword with type being `keywordType`
                token = Token(tokenText, keywordType)
        else:
            # Unknown token!
            self.abort("Unknow token: " + self.curChar)

        self.skipCurChar()

        return token
