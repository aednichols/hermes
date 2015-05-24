import sys
import os
import re
import base64
import argparse
from collections import OrderedDict
# Common Code #
def parse_tree_string(parsetree, indent=None, b64_source=True, indent_level=0):
    indent_str = (' ' * indent * indent_level) if indent else ''
    if isinstance(parsetree, ParseTree):
        children = [parse_tree_string(child, indent, b64_source, indent_level+1) for child in parsetree.children]
        if indent is None or len(children) == 0:
            return '{0}({1}: {2})'.format(indent_str, parsetree.nonterminal, ', '.join(children))
        else:
            return '{0}({1}:\n{2}\n{3})'.format(
                indent_str,
                parsetree.nonterminal,
                ',\n'.join(children),
                indent_str
            )
    elif isinstance(parsetree, Terminal):
        return indent_str + parsetree.dumps(b64_source=b64_source)
def ast_string(ast, indent=None, b64_source=True, indent_level=0):
    indent_str = (' ' * indent * indent_level) if indent else ''
    next_indent_str = (' ' * indent * (indent_level+1)) if indent else ''
    if isinstance(ast, Ast):
        children = OrderedDict([(k, ast_string(v, indent, b64_source, indent_level+1)) for k, v in ast.attributes.items()])
        if indent is None:
            return '({0}: {1})'.format(
                ast.name,
                ', '.join('{0}={1}'.format(k, v) for k, v in children.items())
            )
        else:
            return '({0}:\n{1}\n{2})'.format(
                ast.name,
                ',\n'.join(['{0}{1}={2}'.format(next_indent_str, k, v) for k, v in children.items()]),
                indent_str
            )
    elif isinstance(ast, list):
        children = [ast_string(element, indent, b64_source, indent_level+1) for element in ast]
        if indent is None or len(children) == 0:
            return '[{0}]'.format(', '.join(children))
        else:
            return '[\n{1}\n{0}]'.format(
                indent_str,
                ',\n'.join(['{0}{1}'.format(next_indent_str, child) for child in children]),
            )
    elif isinstance(ast, Terminal):
        return ast.dumps(b64_source=b64_source)
class Terminal:
  def __init__(self, id, str, source_string, resource, line, col):
      self.__dict__.update(locals())
  def getId(self):
      return self.id
  def ast(self):
      return self
  def dumps(self, b64_source=True, **kwargs):
      source_string = base64.b64encode(self.source_string.encode('utf-8')).decode('utf-8') if b64_source else self.source_string
      return '<{resource}:{line}:{col} {terminal} "{source}">'.format(
          resource=self.resource,
          line=self.line,
          col=self.col,
          terminal=self.str,
          source=source_string
      )
  def __str__(self):
      return self.dumps()
class NonTerminal():
  def __init__(self, id, str):
    self.__dict__.update(locals())
    self.list = False
  def __str__(self):
    return self.str
class AstTransform:
  pass
class AstTransformSubstitution(AstTransform):
  def __init__(self, idx):
    self.__dict__.update(locals())
  def __repr__(self):
    return '$' + str(self.idx)
  def __str__(self):
    return self.__repr__()
class AstTransformNodeCreator(AstTransform):
  def __init__( self, name, parameters ):
    self.__dict__.update(locals())
  def __repr__( self ):
    return self.name + '( ' + ', '.join(['%s=$%s' % (k,str(v)) for k,v in self.parameters.items()]) + ' )'
  def __str__(self):
    return self.__repr__()
class AstList(list):
  def ast(self):
      retval = []
      for ast in self:
          retval.append(ast.ast())
      return retval
  def dumps(self, indent=None, b64_source=True):
      args = locals()
      del args['self']
      return ast_string(self, **args)
class ParseTree():
  def __init__(self, nonterminal):
      self.__dict__.update(locals())
      self.children = []
      self.astTransform = None
      self.isExpr = False
      self.isNud = False
      self.isPrefix = False
      self.isInfix = False
      self.nudMorphemeCount = 0
      self.isExprNud = False # true for rules like _expr := {_expr} + {...}
      self.listSeparator = None
      self.list = False
  def add(self, tree):
      self.children.append( tree )
  def ast(self):
      if self.list == True:
          r = AstList()
          if len(self.children) == 0:
              return r
          end = max(0, len(self.children) - 1)
          for child in self.children[:end]:
              if isinstance(child, Terminal) and self.listSeparator is not None and child.id == self.listSeparator.id:
                  continue
              r.append(child.ast())
          r.extend(self.children[end].ast())
          return r
      elif self.isExpr:
          if isinstance(self.astTransform, AstTransformSubstitution):
              return self.children[self.astTransform.idx].ast()
          elif isinstance(self.astTransform, AstTransformNodeCreator):
              parameters = OrderedDict()
              for name, idx in self.astTransform.parameters.items():
                  if idx == '$':
                      child = self.children[0]
                  elif isinstance(self.children[0], ParseTree) and \
                       self.children[0].isNud and \
                       not self.children[0].isPrefix and \
                       not self.isExprNud and \
                       not self.isInfix:
                      if idx < self.children[0].nudMorphemeCount:
                          child = self.children[0].children[idx]
                      else:
                          index = idx - self.children[0].nudMorphemeCount + 1
                          child = self.children[index]
                  elif len(self.children) == 1 and not isinstance(self.children[0], ParseTree) and not isinstance(self.children[0], list):
                      return self.children[0]
                  else:
                      child = self.children[idx]
                  parameters[name] = child.ast()
              return Ast(self.astTransform.name, parameters)
      else:
          if isinstance(self.astTransform, AstTransformSubstitution):
              return self.children[self.astTransform.idx].ast()
          elif isinstance(self.astTransform, AstTransformNodeCreator):
              parameters = OrderedDict()
              for name, idx in self.astTransform.parameters.items():
                  parameters[name] = self.children[idx].ast()
              return Ast(self.astTransform.name, parameters)
          elif len(self.children):
              return self.children[0].ast()
          else:
              return None
  def dumps(self, indent=None, b64_source=True):
      args = locals()
      del args['self']
      return parse_tree_string(self, **args)
class Ast():
    def __init__(self, name, attributes):
        self.__dict__.update(locals())
    def attr(self, attr):
        return self.attributes[attr]
    def dumps(self, indent=None, b64_source=True):
        args = locals()
        del args['self']
        return ast_string(self, **args)
class SyntaxError(Exception):
    def __init__(self, message):
        self.__dict__.update(locals())
    def __str__(self):
        return self.message
class TokenStream(list):
    def __init__(self, arg=[]):
        super().__init__(arg)
        self.index = 0
    def advance(self):
        self.index += 1
        return self.current()
    def last(self):
        return self[-1]
    def current(self):
        try:
            return self[self.index]
        except IndexError:
            return None
class DefaultSyntaxErrorHandler:
    def __init__(self):
        self.errors = []
    def _error(self, string):
        error = SyntaxError(string)
        self.errors.append(error)
        return error
    def unexpected_eof(self):
        return self._error("Error: unexpected end of file")
    def excess_tokens(self):
        return self._error("Finished parsing without consuming all tokens.")
    def unexpected_symbol(self, nonterminal, actual_terminal, expected_terminals, rule):
        return self._error("Unexpected symbol (line {line}, col {col}) when parsing parse_{nt}.  Expected {expected}, got {actual}.".format(
            line=actual_terminal.line,
            col=actual_terminal.col,
            nt=nonterminal,
            expected=', '.join(expected_terminals),
            actual=actual_terminal
        ))
    def no_more_tokens(self, nonterminal, expected_terminal, last_terminal):
        return self._error("No more tokens.  Expecting " + expected_terminal)
    def invalid_terminal(self, nonterminal, invalid_terminal):
        return self._error("Invalid symbol ID: {} ({})".format(invalid_terminal.id, invalid_terminal.string))
    def unrecognized_token(self, string, line, col):
        lines = string.split('\n')
        bad_line = lines[line-1]
        return self._error('Unrecognized token on line {}, column {}:\n\n{}\n{}'.format(
            line, col, bad_line, ''.join([' ' for x in range(col-1)]) + '^'
        ))
class ParserContext:
  def __init__(self, tokens, errors):
    self.__dict__.update(locals())
    self.nonterminal_string = None
    self.rule_string = None
# Parser Code #
terminals = {
    0: 'lbrace',
    1: 'identifier',
    2: 'rparen',
    3: 'stack_push',
    4: 'mode',
    5: 'code',
    6: 'nonterminal_reference',
    7: 'partials',
    8: 'null',
    9: 'pipe',
    10: 'action',
    11: 'expr_rule_hint',
    12: 'colon',
    13: 'infix_rule_hint',
    14: 'expression_divider',
    15: 'comma',
    16: 'right',
    17: 'no_group',
    18: 'parser_expression',
    19: 'integer',
    20: 'rbrace',
    21: 'lexer',
    22: 'asterisk',
    23: 'regex_enum',
    24: 'nonterminal',
    25: 'langle',
    26: 'parser',
    27: 'lsquare',
    28: 'arrow',
    29: 'dash',
    30: 'mixfix_rule_hint',
    31: 'lparen',
    32: 'left',
    33: 'rsquare',
    34: 'equals',
    35: 'unary',
    36: 'regex_partial',
    37: 'll1_rule_hint',
    38: 'grammar',
    39: 'terminal',
    40: 'regex',
    41: 'prefix_rule_hint',
    42: 'language',
    43: 'code_start',
    44: 'rangle',
    45: 'string',
    'lbrace': 0,
    'identifier': 1,
    'rparen': 2,
    'stack_push': 3,
    'mode': 4,
    'code': 5,
    'nonterminal_reference': 6,
    'partials': 7,
    'null': 8,
    'pipe': 9,
    'action': 10,
    'expr_rule_hint': 11,
    'colon': 12,
    'infix_rule_hint': 13,
    'expression_divider': 14,
    'comma': 15,
    'right': 16,
    'no_group': 17,
    'parser_expression': 18,
    'integer': 19,
    'rbrace': 20,
    'lexer': 21,
    'asterisk': 22,
    'regex_enum': 23,
    'nonterminal': 24,
    'langle': 25,
    'parser': 26,
    'lsquare': 27,
    'arrow': 28,
    'dash': 29,
    'mixfix_rule_hint': 30,
    'lparen': 31,
    'left': 32,
    'rsquare': 33,
    'equals': 34,
    'unary': 35,
    'regex_partial': 36,
    'll1_rule_hint': 37,
    'grammar': 38,
    'terminal': 39,
    'regex': 40,
    'prefix_rule_hint': 41,
    'language': 42,
    'code_start': 43,
    'rangle': 44,
    'string': 45,
}
# table[nonterminal][terminal] = rule
table = [
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 85, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 82, -1, -1, -1, -1, -1, -1, -1, -1, 83, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 82, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 7, -1, -1, 6, -1, -1, -1, -1, 7, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 12, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 71, -1, -1, -1, -1, -1, -1, 79, 71, -1, -1, -1, -1, -1, -1, -1, -1, 80, -1, 71, -1, -1, -1, 71, -1, 80, -1, 71, -1, -1, -1, -1, -1, -1, -1, -1, 71, -1, 71, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 36, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 113, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, 58, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 72, -1, -1, -1, -1, -1, -1, -1, 75, -1, 75, -1, -1, -1, -1, -1, -1, -1, -1, 75, -1, -1, -1, 72, -1, -1, -1, 75, -1, -1, 75, -1, -1, -1, -1, -1, 75, -1, 72, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 90, -1, -1, 89, -1, -1, -1, -1, -1, 90, -1, -1, -1, -1, -1, -1, -1, 90, -1, -1, 90, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 98, -1, -1, -1, -1, -1, -1, 99, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 20, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 19, -1, -1, -1, -1, -1],
    [-1, -1, 42, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 41, -1, -1, -1, -1, 42, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 39, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, 22, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 53, 53, 53, 53, -1, -1, 53, 53, -1, 53, -1, -1, -1, -1, -1, -1, 52, -1, -1, 53, -1, -1, 53, -1, -1, -1, 52, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 53, 53, -1, -1, 53, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 65, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 101, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 100, -1, -1, 102, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, 116, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 115, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1, -1, 2, 1, -1, -1, -1, -1, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 17, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 64, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 61, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 88, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 88, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 23, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, 9, -1, -1, 9, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 10, -1, -1, 9, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 9, -1, -1, 9, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 97, -1, -1, -1, -1, -1, -1, 97, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, 14, -1, -1, 15, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 13, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 13, -1, -1, 16, -1, -1],
    [-1, 78, -1, -1, -1, -1, -1, -1, -1, 78, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 78, -1, -1, -1, 78, -1, -1, -1, 78, -1, -1, -1, -1, -1, -1, -1, -1, 78, -1, 78, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 95, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, 117, -1, -1, -1, -1, -1, 114, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 114, -1, -1, -1, -1, 114, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 114, -1, -1, -1, -1, -1, 114],
    [-1, 118, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, 8, -1, -1, 8, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 11, -1, -1, 8, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 8, -1, -1, 8, -1, -1],
    [45, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 93, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 91, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 92, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, 123, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 122, -1, -1, -1, -1, 119, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 120, -1, -1, -1, -1, -1, 121],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 60, -1, -1, -1, -1, -1, -1, -1, 59, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 106, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 87, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 86, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 107, 110, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 5, -1, -1, 5, -1, -1, -1, -1, 5, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 24, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 31, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, 77, -1, 77, -1, -1, 77, -1, -1, -1, -1, -1, 77, -1, -1, -1, -1, -1, -1, -1, 76, -1, -1, 77, -1, -1, -1, -1, -1, 77, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 49, -1, 50, -1, -1, -1, -1, 57, -1, 51, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 46, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 54, -1, -1, -1, -1, -1, -1],
    [-1, 32, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 35, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, 68, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 69, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 69, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 63, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 67, -1, -1, -1, -1, -1, -1, -1, 67, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 67, -1, -1, -1, 67, -1, -1, -1, 67, -1, -1, -1, -1, -1, -1, -1, -1, 67, -1, 67, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 81, -1, -1, -1, -1, -1, -1, -1, -1, 84, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 81, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 4, -1, -1, -1, -1, -1, -1, -1],
    [-1, 105, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 104, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 103, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 0, -1, 3, 0, -1, -1, -1, -1, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, 48, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 47, -1, -1, -1, -1, -1, -1],
    [-1, -1, 109, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 108, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 44, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 28, -1, 28, 29, -1, -1, 29, 28, -1, 28, -1, -1, -1, -1, -1, -1, -1, -1, -1, 29, -1, -1, 29, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 28, 29, -1, -1, 29, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 66, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 94, -1, -1, -1, -1, -1, -1, -1, -1, -1, 94, -1, -1, -1, -1, -1, -1, -1, -1, 94, -1, -1, -1, 94, -1, -1, -1, 94, -1, -1, 94, -1, -1, -1, -1, -1, -1, -1, 94, -1, -1, -1, -1, -1, -1],
    [-1, 27, -1, 27, 30, -1, -1, 30, 27, -1, 27, -1, -1, -1, -1, -1, -1, -1, -1, -1, 30, -1, -1, 30, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 27, 30, -1, -1, 30, -1, -1],
    [-1, 73, -1, -1, -1, -1, -1, -1, -1, 74, -1, 74, -1, -1, -1, -1, -1, -1, -1, -1, 74, -1, -1, -1, 73, -1, -1, -1, 74, -1, -1, 74, -1, -1, -1, -1, -1, 74, -1, 73, -1, -1, -1, -1, -1, -1],
    [-1, 33, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 34, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 40, 43, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 43, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 56, -1, -1, -1, -1, -1, -1, -1, -1, -1, 55, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 111, -1, -1, -1, -1, 112, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [25, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 26, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, 38, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 38, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 37, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 96, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1],
    [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 21, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 18, -1, -1, -1, -1, -1],
]
nonterminal_first = {
    46: [18],
    47: [31, 11, -1],
    48: [18, 26, 21],
    49: [21],
    50: [24, 1, 26, 28, 18, 39, 8, 9, -1],
    51: [23],
    52: [1],
    53: [4],
    54: [24, 1, 39, -1],
    55: [14, -1],
    56: [29, 22],
    57: [40, -1],
    58: [15, -1],
    59: [1],
    60: [7],
    61: [27, 17, -1],
    62: [26],
    63: [35, 32, 16],
    64: [15, -1],
    65: [18, 26, 21, -1],
    66: [43],
    67: [37, -1],
    68: [31, 11],
    69: [40],
    70: [23, 4, 40, 7, 43, -1],
    71: [29, 22],
    72: [40, 7, 43, 4, 23],
    73: [24, 1, 28, 39, -1],
    74: [14],
    75: [19, 24, 8, 39, 45, -1],
    76: [1],
    77: [23, 4, 40, 7, 43, -1],
    78: [0],
    79: [30, 13, 41],
    80: [24, 8, 39, 45, 19],
    81: [18, 26],
    82: [28],
    83: [31, -1],
    84: [1, -1],
    85: [18, 26, 21],
    86: [40, 23],
    87: [28, -1],
    88: [1, 3, 10, 39, 8],
    89: [39],
    90: [1, -1],
    91: [9, -1],
    92: [37, -1],
    93: [24, 1, 28, 9, 39, -1],
    94: [31, 11, -1],
    95: [38],
    96: [1, 39, 24],
    97: [18, 26, 21, -1],
    98: [39, -1],
    99: [15, -1],
    100: [31],
    101: [1, 3, 39, 8, 10, -1],
    102: [37],
    103: [24, 1, 39, -1],
    104: [1, 3, 39, 8, 10, -1],
    105: [24, 1, 39, -1],
    106: [1, -1],
    107: [1, -1],
    108: [27, 17],
    109: [1, 6],
    110: [0, -1],
    111: [31, -1],
    112: [31],
    113: [40, -1],
}
nonterminal_follow = {
    46: [26, 37, 18, 21, 20],
    47: [20],
    48: [26, 21, 20, 18],
    49: [26, 21, 20, 18],
    50: [37, 20],
    51: [4, 40, 7, 20, 43, 23],
    52: [15, 2],
    53: [4, 40, 7, 20, 43, 23],
    54: [37, 28, 20, 9, 31, 11],
    55: [20, 28, 31, 11],
    56: [12],
    57: [20],
    58: [2, 20],
    59: [1, 20],
    60: [4, 40, 7, 20, 43, 23],
    61: [1, 2, 3, 4, 8, 7, 10, 39, 40, 20, 43, 23],
    62: [26, 37, 18, 21, 20],
    63: [2],
    64: [2],
    65: [20],
    66: [4, 40, 7, 20, 43, 23],
    67: [20],
    68: [31, 11, 20],
    69: [40, 20],
    70: [20],
    71: [2],
    72: [40, 7, 20, 43, 4, 23],
    73: [9, 37, 20],
    74: [20, 28, 31, 11],
    75: [2],
    76: [1, 28, 9, 31, 11, 37, 39, 20, 24],
    77: [20],
    78: [28],
    79: [31, 11, 20],
    80: [15, 2],
    81: [26, 37, 18, 21, 20],
    82: [37, 20, 9, 31, 14, 11],
    83: [11],
    84: [2],
    85: [18, 26, 21, 20],
    86: [4, 40, 7, 20, 43, 23],
    87: [37, 20, 9, 31, 14, 11],
    88: [1, 3, 39, 4, 40, 8, 7, 20, 43, 10, 23],
    89: [1, 2, 3, 4, 8, 7, 10, 39, 40, 20, 43, 23],
    90: [20],
    91: [37, 20],
    92: [20],
    93: [37, 20],
    94: [20],
    95: [-1],
    96: [1, 37, 28, 39, 20, 9, 31, 11, 24],
    97: [20],
    98: [2],
    99: [2],
    100: [1, 20],
    101: [4, 40, 7, 20, 43, 23],
    102: [37, 20],
    103: [20, 28, 31, 11],
    104: [4, 40, 7, 20, 43, 23],
    105: [37, 28, 20, 9, 31, 11],
    106: [20],
    107: [2, 20],
    108: [1, 2, 3, 4, 8, 7, 10, 39, 40, 20, 43, 23],
    109: [37, 20, 9, 31, 14, 11],
    110: [28],
    111: [1, 20],
    112: [11],
    113: [20],
}
rule_first = {
    0: [18, 26, 21],
    1: [18, 26, 21],
    2: [-1],
    3: [-1],
    4: [38],
    5: [18, 26, 21],
    6: [21],
    7: [18, 26],
    8: [7, 43, 4, 40, 23],
    9: [7, 43, 4, 40, 23],
    10: [-1],
    11: [-1],
    12: [21],
    13: [40, 23],
    14: [4],
    15: [7],
    16: [43],
    17: [43],
    18: [40],
    19: [40],
    20: [-1],
    21: [-1],
    22: [7],
    23: [40],
    24: [23],
    25: [0],
    26: [-1],
    27: [1, 3, 10, 39, 8],
    28: [1, 3, 10, 39, 8],
    29: [-1],
    30: [-1],
    31: [40],
    32: [1],
    33: [1],
    34: [-1],
    35: [-1],
    36: [23],
    37: [31],
    38: [-1],
    39: [1],
    40: [1],
    41: [15],
    42: [-1],
    43: [-1],
    44: [31],
    45: [0],
    46: [39],
    47: [39],
    48: [-1],
    49: [1],
    50: [3],
    51: [10],
    52: [27, 17],
    53: [-1],
    54: [39],
    55: [27],
    56: [17],
    57: [8],
    58: [4],
    59: [26],
    60: [18],
    61: [37],
    62: [37],
    63: [-1],
    64: [-1],
    65: [26],
    66: [37],
    67: [24, 1, 28, 39, 9, -1],
    68: [9],
    69: [-1],
    70: [-1],
    71: [24, 1, 28, 39, 9, -1],
    72: [1, 39, 24],
    73: [1, 39, 24],
    74: [-1],
    75: [-1],
    76: [28],
    77: [-1],
    78: [-1, 28, 1, 39, 24],
    79: [8],
    80: [18, 26],
    81: [31, 11],
    82: [31, 11],
    83: [-1],
    84: [-1],
    85: [18],
    86: [31],
    87: [-1],
    88: [31, 11],
    89: [14],
    90: [-1],
    91: [30],
    92: [41],
    93: [13],
    94: [-1, 1, 39, 24],
    95: [14],
    96: [31],
    97: [29, 22],
    98: [22],
    99: [29],
    100: [32],
    101: [16],
    102: [35],
    103: [39],
    104: [24],
    105: [1],
    106: [28],
    107: [1],
    108: [15],
    109: [-1],
    110: [-1],
    111: [1],
    112: [6],
    113: [1],
    114: [19, 24, 39, 45, 8],
    115: [15],
    116: [-1],
    117: [-1],
    118: [1],
    119: [24],
    120: [39],
    121: [45],
    122: [19],
    123: [8],
}
nonterminal_rules = {
    46: [
        "$parser_expression = :parser_expression :lbrace $_gen23 :rbrace -> ExpressionParser( rules=$2 )",
    ],
    47: [
        "$_gen24 = $expression_rule $_gen24",
        "$_gen24 = :_empty",
    ],
    48: [
        "$body_element_sub = $lexer",
        "$body_element_sub = $parser",
    ],
    49: [
        "$lexer = :lexer :lbrace $_gen2 :rbrace -> Lexer( atoms=$2 )",
    ],
    50: [
        "$ll1_rule_rhs = $_gen18",
        "$ll1_rule_rhs = :null -> NullProduction(  )",
        "$ll1_rule_rhs = $parser",
    ],
    51: [
        "$enumerated_regex = :regex_enum :lbrace $_gen9 :rbrace :arrow $_gen7 -> EnumeratedRegex( enums=$2, onmatch=$5 )",
    ],
    52: [
        "$ast_parameter = :identifier :equals :nonterminal_reference -> AstParameter( name=$0, index=$2 )",
    ],
    53: [
        "$lexer_mode = :mode :langle :identifier :rangle :lbrace $_gen2 :rbrace -> Mode( name=$2, atoms=$5 )",
    ],
    54: [
        "$_gen20 = $morpheme $_gen21",
        "$_gen20 = :_empty",
    ],
    55: [
        "$_gen26 = $led",
        "$_gen26 = :_empty",
    ],
    56: [
        "$binding_power_marker = :asterisk",
        "$binding_power_marker = :dash",
    ],
    57: [
        "$_gen5 = $regex_partial $_gen5",
        "$_gen5 = :_empty",
    ],
    58: [
        "$_gen13 = :comma :identifier $_gen13",
        "$_gen13 = :_empty",
    ],
    59: [
        "$regex_enumeration = :identifier :colon :regex $_gen11 -> RegexEnum( language=$0, regex=$2, options=$3 )",
    ],
    60: [
        "$lexer_partials = :partials :lbrace $_gen4 :rbrace -> RegexPartials( list=$2 )",
    ],
    61: [
        "$_gen15 = $match_group",
        "$_gen15 = :_empty",
    ],
    62: [
        "$parser_ll1 = :parser :lbrace $_gen16 :rbrace -> Parser( rules=$2 )",
    ],
    63: [
        "$associativity = :left",
        "$associativity = :right",
        "$associativity = :unary",
    ],
    64: [
        "$_gen30 = :comma $macro_parameter $_gen30",
        "$_gen30 = :_empty",
    ],
    65: [
        "$_gen1 = $body_element $_gen1",
        "$_gen1 = :_empty",
    ],
    66: [
        "$lexer_code = :code_start :language :code -> LexerCode( language=$1, code=$2 )",
    ],
    67: [
        "$_gen16 = $ll1_rule $_gen17",
        "$_gen16 = :_empty",
    ],
    68: [
        "$expression_rule = $_gen25 :expr_rule_hint :nonterminal :equals $expression_rule_production -> ExpressionRule( precedence=$0, nonterminal=$2, production=$4 )",
    ],
    69: [
        "$regex_partial = :regex :arrow :regex_partial -> RegexPartial( regex=$0, name=$2 )",
    ],
    70: [
        "$_gen3 = $lexer_atom $_gen3",
        "$_gen3 = :_empty",
    ],
    71: [
        "$precedence = $binding_power_marker :colon $associativity -> Precedence( marker=$0, associativity=$2 )",
    ],
    72: [
        "$lexer_atom = $lexer_regex",
        "$lexer_atom = $lexer_mode",
        "$lexer_atom = $lexer_partials",
        "$lexer_atom = $lexer_code",
    ],
    73: [
        "$rule = $_gen20 $_gen22 -> Production( morphemes=$0, ast=$1 )",
    ],
    74: [
        "$led = :expression_divider $_gen20 -> $1",
    ],
    75: [
        "$_gen29 = $macro_parameter $_gen30",
        "$_gen29 = :_empty",
    ],
    76: [
        "$macro = :identifier :lparen $_gen29 :rparen -> Macro( name=$0, parameters=$2 )",
    ],
    77: [
        "$_gen2 = $lexer_atom $_gen3",
        "$_gen2 = :_empty",
    ],
    78: [
        "$regex_options = :lbrace $_gen12 :rbrace -> $1",
    ],
    79: [
        "$expression_rule_production = :mixfix_rule_hint $nud $_gen22 $_gen26 $_gen22 -> MixfixProduction( nud=$1, nud_ast=$2, led=$3, ast=$4 )",
        "$expression_rule_production = :prefix_rule_hint $_gen20 $_gen22 -> PrefixProduction( morphemes=$1, ast=$2 )",
        "$expression_rule_production = :infix_rule_hint $_gen20 $_gen22 -> InfixProduction( morphemes=$1, ast=$2 )",
    ],
    80: [
        "$macro_parameter = :nonterminal",
        "$macro_parameter = :terminal",
        "$macro_parameter = :string",
        "$macro_parameter = :integer",
        "$macro_parameter = :null",
    ],
    81: [
        "$parser = $parser_ll1",
        "$parser = $parser_expression",
    ],
    82: [
        "$ast_transform = :arrow $ast_transform_sub -> $1",
    ],
    83: [
        "$_gen25 = $binding_power",
        "$_gen25 = :_empty",
    ],
    84: [
        "$_gen27 = $ast_parameter $_gen28",
        "$_gen27 = :_empty",
    ],
    85: [
        "$body_element = $body_element_sub",
    ],
    86: [
        "$lexer_regex = $enumerated_regex",
        "$lexer_regex = :regex $_gen6 :arrow $_gen7 -> Regex( regex=$0, options=$1, onmatch=$3 )",
    ],
    87: [
        "$_gen22 = $ast_transform",
        "$_gen22 = :_empty",
    ],
    88: [
        "$lexer_target = $terminal",
        "$lexer_target = :identifier :lparen $_gen14 :rparen -> LexerFunctionCall( name=$0, terminal=$2 )",
        "$lexer_target = :stack_push",
        "$lexer_target = :action",
        "$lexer_target = :null -> Null(  )",
    ],
    89: [
        "$terminal = :terminal $_gen15 -> Terminal( name=$0, group=$1 )",
    ],
    90: [
        "$_gen9 = $regex_enumeration $_gen10",
        "$_gen9 = :_empty",
    ],
    91: [
        "$_gen19 = :pipe $rule $_gen19",
        "$_gen19 = :_empty",
    ],
    92: [
        "$_gen17 = $ll1_rule $_gen17",
        "$_gen17 = :_empty",
    ],
    93: [
        "$_gen18 = $rule $_gen19",
        "$_gen18 = :_empty",
    ],
    94: [
        "$_gen23 = $expression_rule $_gen24",
        "$_gen23 = :_empty",
    ],
    95: [
        "$grammar = :grammar :lbrace $_gen0 :rbrace -> Grammar( body=$2 )",
    ],
    96: [
        "$morpheme = :terminal",
        "$morpheme = :nonterminal",
        "$morpheme = $macro",
    ],
    97: [
        "$_gen0 = $body_element $_gen1",
        "$_gen0 = :_empty",
    ],
    98: [
        "$_gen14 = $terminal",
        "$_gen14 = :_empty",
    ],
    99: [
        "$_gen28 = :comma $ast_parameter $_gen28",
        "$_gen28 = :_empty",
    ],
    100: [
        "$regex_enumeration_options = :lparen $_gen12 :rparen -> $1",
    ],
    101: [
        "$_gen8 = $lexer_target $_gen8",
        "$_gen8 = :_empty",
    ],
    102: [
        "$ll1_rule = :ll1_rule_hint :nonterminal :equals $ll1_rule_rhs -> Rule( nonterminal=$1, production=$3 )",
    ],
    103: [
        "$nud = $_gen20",
    ],
    104: [
        "$_gen7 = $lexer_target $_gen8",
        "$_gen7 = :_empty",
    ],
    105: [
        "$_gen21 = $morpheme $_gen21",
        "$_gen21 = :_empty",
    ],
    106: [
        "$_gen10 = $regex_enumeration $_gen10",
        "$_gen10 = :_empty",
    ],
    107: [
        "$_gen12 = :identifier $_gen13",
        "$_gen12 = :_empty",
    ],
    108: [
        "$match_group = :lsquare :integer :rsquare -> $1",
        "$match_group = :no_group",
    ],
    109: [
        "$ast_transform_sub = :identifier :lparen $_gen27 :rparen -> AstTransformation( name=$0, parameters=$2 )",
        "$ast_transform_sub = :nonterminal_reference",
    ],
    110: [
        "$_gen6 = $regex_options",
        "$_gen6 = :_empty",
    ],
    111: [
        "$_gen11 = $regex_enumeration_options",
        "$_gen11 = :_empty",
    ],
    112: [
        "$binding_power = :lparen $precedence :rparen -> $1",
    ],
    113: [
        "$_gen4 = $regex_partial $_gen5",
        "$_gen4 = :_empty",
    ],
}
rules = {
    0: "$_gen0 = $body_element $_gen1",
    1: "$_gen1 = $body_element $_gen1",
    2: "$_gen1 = :_empty",
    3: "$_gen0 = :_empty",
    4: "$grammar = :grammar :lbrace $_gen0 :rbrace -> Grammar( body=$2 )",
    5: "$body_element = $body_element_sub",
    6: "$body_element_sub = $lexer",
    7: "$body_element_sub = $parser",
    8: "$_gen2 = $lexer_atom $_gen3",
    9: "$_gen3 = $lexer_atom $_gen3",
    10: "$_gen3 = :_empty",
    11: "$_gen2 = :_empty",
    12: "$lexer = :lexer :lbrace $_gen2 :rbrace -> Lexer( atoms=$2 )",
    13: "$lexer_atom = $lexer_regex",
    14: "$lexer_atom = $lexer_mode",
    15: "$lexer_atom = $lexer_partials",
    16: "$lexer_atom = $lexer_code",
    17: "$lexer_code = :code_start :language :code -> LexerCode( language=$1, code=$2 )",
    18: "$_gen4 = $regex_partial $_gen5",
    19: "$_gen5 = $regex_partial $_gen5",
    20: "$_gen5 = :_empty",
    21: "$_gen4 = :_empty",
    22: "$lexer_partials = :partials :lbrace $_gen4 :rbrace -> RegexPartials( list=$2 )",
    23: "$regex_partial = :regex :arrow :regex_partial -> RegexPartial( regex=$0, name=$2 )",
    24: "$lexer_regex = $enumerated_regex",
    25: "$_gen6 = $regex_options",
    26: "$_gen6 = :_empty",
    27: "$_gen7 = $lexer_target $_gen8",
    28: "$_gen8 = $lexer_target $_gen8",
    29: "$_gen8 = :_empty",
    30: "$_gen7 = :_empty",
    31: "$lexer_regex = :regex $_gen6 :arrow $_gen7 -> Regex( regex=$0, options=$1, onmatch=$3 )",
    32: "$_gen9 = $regex_enumeration $_gen10",
    33: "$_gen10 = $regex_enumeration $_gen10",
    34: "$_gen10 = :_empty",
    35: "$_gen9 = :_empty",
    36: "$enumerated_regex = :regex_enum :lbrace $_gen9 :rbrace :arrow $_gen7 -> EnumeratedRegex( enums=$2, onmatch=$5 )",
    37: "$_gen11 = $regex_enumeration_options",
    38: "$_gen11 = :_empty",
    39: "$regex_enumeration = :identifier :colon :regex $_gen11 -> RegexEnum( language=$0, regex=$2, options=$3 )",
    40: "$_gen12 = :identifier $_gen13",
    41: "$_gen13 = :comma :identifier $_gen13",
    42: "$_gen13 = :_empty",
    43: "$_gen12 = :_empty",
    44: "$regex_enumeration_options = :lparen $_gen12 :rparen -> $1",
    45: "$regex_options = :lbrace $_gen12 :rbrace -> $1",
    46: "$lexer_target = $terminal",
    47: "$_gen14 = $terminal",
    48: "$_gen14 = :_empty",
    49: "$lexer_target = :identifier :lparen $_gen14 :rparen -> LexerFunctionCall( name=$0, terminal=$2 )",
    50: "$lexer_target = :stack_push",
    51: "$lexer_target = :action",
    52: "$_gen15 = $match_group",
    53: "$_gen15 = :_empty",
    54: "$terminal = :terminal $_gen15 -> Terminal( name=$0, group=$1 )",
    55: "$match_group = :lsquare :integer :rsquare -> $1",
    56: "$match_group = :no_group",
    57: "$lexer_target = :null -> Null(  )",
    58: "$lexer_mode = :mode :langle :identifier :rangle :lbrace $_gen2 :rbrace -> Mode( name=$2, atoms=$5 )",
    59: "$parser = $parser_ll1",
    60: "$parser = $parser_expression",
    61: "$_gen16 = $ll1_rule $_gen17",
    62: "$_gen17 = $ll1_rule $_gen17",
    63: "$_gen17 = :_empty",
    64: "$_gen16 = :_empty",
    65: "$parser_ll1 = :parser :lbrace $_gen16 :rbrace -> Parser( rules=$2 )",
    66: "$ll1_rule = :ll1_rule_hint :nonterminal :equals $ll1_rule_rhs -> Rule( nonterminal=$1, production=$3 )",
    67: "$_gen18 = $rule $_gen19",
    68: "$_gen19 = :pipe $rule $_gen19",
    69: "$_gen19 = :_empty",
    70: "$_gen18 = :_empty",
    71: "$ll1_rule_rhs = $_gen18",
    72: "$_gen20 = $morpheme $_gen21",
    73: "$_gen21 = $morpheme $_gen21",
    74: "$_gen21 = :_empty",
    75: "$_gen20 = :_empty",
    76: "$_gen22 = $ast_transform",
    77: "$_gen22 = :_empty",
    78: "$rule = $_gen20 $_gen22 -> Production( morphemes=$0, ast=$1 )",
    79: "$ll1_rule_rhs = :null -> NullProduction(  )",
    80: "$ll1_rule_rhs = $parser",
    81: "$_gen23 = $expression_rule $_gen24",
    82: "$_gen24 = $expression_rule $_gen24",
    83: "$_gen24 = :_empty",
    84: "$_gen23 = :_empty",
    85: "$parser_expression = :parser_expression :lbrace $_gen23 :rbrace -> ExpressionParser( rules=$2 )",
    86: "$_gen25 = $binding_power",
    87: "$_gen25 = :_empty",
    88: "$expression_rule = $_gen25 :expr_rule_hint :nonterminal :equals $expression_rule_production -> ExpressionRule( precedence=$0, nonterminal=$2, production=$4 )",
    89: "$_gen26 = $led",
    90: "$_gen26 = :_empty",
    91: "$expression_rule_production = :mixfix_rule_hint $nud $_gen22 $_gen26 $_gen22 -> MixfixProduction( nud=$1, nud_ast=$2, led=$3, ast=$4 )",
    92: "$expression_rule_production = :prefix_rule_hint $_gen20 $_gen22 -> PrefixProduction( morphemes=$1, ast=$2 )",
    93: "$expression_rule_production = :infix_rule_hint $_gen20 $_gen22 -> InfixProduction( morphemes=$1, ast=$2 )",
    94: "$nud = $_gen20",
    95: "$led = :expression_divider $_gen20 -> $1",
    96: "$binding_power = :lparen $precedence :rparen -> $1",
    97: "$precedence = $binding_power_marker :colon $associativity -> Precedence( marker=$0, associativity=$2 )",
    98: "$binding_power_marker = :asterisk",
    99: "$binding_power_marker = :dash",
    100: "$associativity = :left",
    101: "$associativity = :right",
    102: "$associativity = :unary",
    103: "$morpheme = :terminal",
    104: "$morpheme = :nonterminal",
    105: "$morpheme = $macro",
    106: "$ast_transform = :arrow $ast_transform_sub -> $1",
    107: "$_gen27 = $ast_parameter $_gen28",
    108: "$_gen28 = :comma $ast_parameter $_gen28",
    109: "$_gen28 = :_empty",
    110: "$_gen27 = :_empty",
    111: "$ast_transform_sub = :identifier :lparen $_gen27 :rparen -> AstTransformation( name=$0, parameters=$2 )",
    112: "$ast_transform_sub = :nonterminal_reference",
    113: "$ast_parameter = :identifier :equals :nonterminal_reference -> AstParameter( name=$0, index=$2 )",
    114: "$_gen29 = $macro_parameter $_gen30",
    115: "$_gen30 = :comma $macro_parameter $_gen30",
    116: "$_gen30 = :_empty",
    117: "$_gen29 = :_empty",
    118: "$macro = :identifier :lparen $_gen29 :rparen -> Macro( name=$0, parameters=$2 )",
    119: "$macro_parameter = :nonterminal",
    120: "$macro_parameter = :terminal",
    121: "$macro_parameter = :string",
    122: "$macro_parameter = :integer",
    123: "$macro_parameter = :null",
}
def is_terminal(id): return isinstance(id, int) and 0 <= id <= 45
def parse(tokens, errors=None, start=None):
    if errors is None:
        errors = DefaultSyntaxErrorHandler()
    if isinstance(tokens, str):
        tokens = lex(tokens, 'string', errors)
    ctx = ParserContext(tokens, errors)
    tree = parse_grammar(ctx)
    if tokens.current() != None:
        raise ctx.errors.excess_tokens()
    return tree
def expect(ctx, terminal_id):
    current = ctx.tokens.current()
    if not current:
        raise ctx.errors.no_more_tokens(ctx.nonterminal, terminals[terminal_id], ctx.tokens.last())
    if current.id != terminal_id:
        raise ctx.errors.unexpected_symbol(ctx.nonterminal, current, [terminals[terminal_id]], ctx.rule)
    next = ctx.tokens.advance()
    if next and not is_terminal(next.id):
        raise ctx.errors.invalid_terminal(ctx.nonterminal, next)
    return current
def parse_parser_expression(ctx):
    current = ctx.tokens.current()
    rule = table[0][current.id] if current else -1
    tree = ParseTree(NonTerminal(46, 'parser_expression'))
    ctx.nonterminal = "parser_expression"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 85: # $parser_expression = :parser_expression :lbrace $_gen23 :rbrace -> ExpressionParser( rules=$2 )
        ctx.rule = rules[85]
        ast_parameters = OrderedDict([
            ('rules', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('ExpressionParser', ast_parameters)
        t = expect(ctx, 18) # :parser_expression
        tree.add(t)
        t = expect(ctx, 0) # :lbrace
        tree.add(t)
        subtree = parse__gen23(ctx)
        tree.add(subtree)
        t = expect(ctx, 20) # :rbrace
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[46] if x >=0],
      rules[85]
    )
def parse__gen24(ctx):
    current = ctx.tokens.current()
    rule = table[1][current.id] if current else -1
    tree = ParseTree(NonTerminal(47, '_gen24'))
    ctx.nonterminal = "_gen24"
    tree.list = True
    if current != None and current.id in nonterminal_follow[47] and current.id not in nonterminal_first[47]:
        return tree
    if current == None:
        return tree
    if rule == 82: # $_gen24 = $expression_rule $_gen24
        ctx.rule = rules[82]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_expression_rule(ctx)
        tree.add(subtree)
        subtree = parse__gen24(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_body_element_sub(ctx):
    current = ctx.tokens.current()
    rule = table[2][current.id] if current else -1
    tree = ParseTree(NonTerminal(48, 'body_element_sub'))
    ctx.nonterminal = "body_element_sub"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 6: # $body_element_sub = $lexer
        ctx.rule = rules[6]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer(ctx)
        tree.add(subtree)
        return tree
    elif rule == 7: # $body_element_sub = $parser
        ctx.rule = rules[7]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_parser(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[48] if x >=0],
      rules[7]
    )
def parse_lexer(ctx):
    current = ctx.tokens.current()
    rule = table[3][current.id] if current else -1
    tree = ParseTree(NonTerminal(49, 'lexer'))
    ctx.nonterminal = "lexer"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 12: # $lexer = :lexer :lbrace $_gen2 :rbrace -> Lexer( atoms=$2 )
        ctx.rule = rules[12]
        ast_parameters = OrderedDict([
            ('atoms', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('Lexer', ast_parameters)
        t = expect(ctx, 21) # :lexer
        tree.add(t)
        t = expect(ctx, 0) # :lbrace
        tree.add(t)
        subtree = parse__gen2(ctx)
        tree.add(subtree)
        t = expect(ctx, 20) # :rbrace
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[49] if x >=0],
      rules[12]
    )
def parse_ll1_rule_rhs(ctx):
    current = ctx.tokens.current()
    rule = table[4][current.id] if current else -1
    tree = ParseTree(NonTerminal(50, 'll1_rule_rhs'))
    ctx.nonterminal = "ll1_rule_rhs"
    tree.list = False
    if current != None and current.id in nonterminal_follow[50] and current.id not in nonterminal_first[50]:
        return tree
    if current == None:
        return tree
    if rule == 71: # $ll1_rule_rhs = $_gen18
        ctx.rule = rules[71]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse__gen18(ctx)
        tree.add(subtree)
        return tree
    elif rule == 79: # $ll1_rule_rhs = :null -> NullProduction(  )
        ctx.rule = rules[79]
        ast_parameters = OrderedDict([
        ])
        tree.astTransform = AstTransformNodeCreator('NullProduction', ast_parameters)
        t = expect(ctx, 8) # :null
        tree.add(t)
        return tree
    elif rule == 80: # $ll1_rule_rhs = $parser
        ctx.rule = rules[80]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_parser(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_enumerated_regex(ctx):
    current = ctx.tokens.current()
    rule = table[5][current.id] if current else -1
    tree = ParseTree(NonTerminal(51, 'enumerated_regex'))
    ctx.nonterminal = "enumerated_regex"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 36: # $enumerated_regex = :regex_enum :lbrace $_gen9 :rbrace :arrow $_gen7 -> EnumeratedRegex( enums=$2, onmatch=$5 )
        ctx.rule = rules[36]
        ast_parameters = OrderedDict([
            ('enums', 2),
            ('onmatch', 5),
        ])
        tree.astTransform = AstTransformNodeCreator('EnumeratedRegex', ast_parameters)
        t = expect(ctx, 23) # :regex_enum
        tree.add(t)
        t = expect(ctx, 0) # :lbrace
        tree.add(t)
        subtree = parse__gen9(ctx)
        tree.add(subtree)
        t = expect(ctx, 20) # :rbrace
        tree.add(t)
        t = expect(ctx, 28) # :arrow
        tree.add(t)
        subtree = parse__gen7(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[51] if x >=0],
      rules[36]
    )
def parse_ast_parameter(ctx):
    current = ctx.tokens.current()
    rule = table[6][current.id] if current else -1
    tree = ParseTree(NonTerminal(52, 'ast_parameter'))
    ctx.nonterminal = "ast_parameter"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 113: # $ast_parameter = :identifier :equals :nonterminal_reference -> AstParameter( name=$0, index=$2 )
        ctx.rule = rules[113]
        ast_parameters = OrderedDict([
            ('name', 0),
            ('index', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('AstParameter', ast_parameters)
        t = expect(ctx, 1) # :identifier
        tree.add(t)
        t = expect(ctx, 34) # :equals
        tree.add(t)
        t = expect(ctx, 6) # :nonterminal_reference
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[52] if x >=0],
      rules[113]
    )
def parse_lexer_mode(ctx):
    current = ctx.tokens.current()
    rule = table[7][current.id] if current else -1
    tree = ParseTree(NonTerminal(53, 'lexer_mode'))
    ctx.nonterminal = "lexer_mode"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 58: # $lexer_mode = :mode :langle :identifier :rangle :lbrace $_gen2 :rbrace -> Mode( name=$2, atoms=$5 )
        ctx.rule = rules[58]
        ast_parameters = OrderedDict([
            ('name', 2),
            ('atoms', 5),
        ])
        tree.astTransform = AstTransformNodeCreator('Mode', ast_parameters)
        t = expect(ctx, 4) # :mode
        tree.add(t)
        t = expect(ctx, 25) # :langle
        tree.add(t)
        t = expect(ctx, 1) # :identifier
        tree.add(t)
        t = expect(ctx, 44) # :rangle
        tree.add(t)
        t = expect(ctx, 0) # :lbrace
        tree.add(t)
        subtree = parse__gen2(ctx)
        tree.add(subtree)
        t = expect(ctx, 20) # :rbrace
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[53] if x >=0],
      rules[58]
    )
def parse__gen20(ctx):
    current = ctx.tokens.current()
    rule = table[8][current.id] if current else -1
    tree = ParseTree(NonTerminal(54, '_gen20'))
    ctx.nonterminal = "_gen20"
    tree.list = True
    if current != None and current.id in nonterminal_follow[54] and current.id not in nonterminal_first[54]:
        return tree
    if current == None:
        return tree
    if rule == 72: # $_gen20 = $morpheme $_gen21
        ctx.rule = rules[72]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_morpheme(ctx)
        tree.add(subtree)
        subtree = parse__gen21(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen26(ctx):
    current = ctx.tokens.current()
    rule = table[9][current.id] if current else -1
    tree = ParseTree(NonTerminal(55, '_gen26'))
    ctx.nonterminal = "_gen26"
    tree.list = False
    if current != None and current.id in nonterminal_follow[55] and current.id not in nonterminal_first[55]:
        return tree
    if current == None:
        return tree
    if rule == 89: # $_gen26 = $led
        ctx.rule = rules[89]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_led(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_binding_power_marker(ctx):
    current = ctx.tokens.current()
    rule = table[10][current.id] if current else -1
    tree = ParseTree(NonTerminal(56, 'binding_power_marker'))
    ctx.nonterminal = "binding_power_marker"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 98: # $binding_power_marker = :asterisk
        ctx.rule = rules[98]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 22) # :asterisk
        tree.add(t)
        return tree
    elif rule == 99: # $binding_power_marker = :dash
        ctx.rule = rules[99]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 29) # :dash
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[56] if x >=0],
      rules[99]
    )
def parse__gen5(ctx):
    current = ctx.tokens.current()
    rule = table[11][current.id] if current else -1
    tree = ParseTree(NonTerminal(57, '_gen5'))
    ctx.nonterminal = "_gen5"
    tree.list = True
    if current != None and current.id in nonterminal_follow[57] and current.id not in nonterminal_first[57]:
        return tree
    if current == None:
        return tree
    if rule == 19: # $_gen5 = $regex_partial $_gen5
        ctx.rule = rules[19]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_regex_partial(ctx)
        tree.add(subtree)
        subtree = parse__gen5(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen13(ctx):
    current = ctx.tokens.current()
    rule = table[12][current.id] if current else -1
    tree = ParseTree(NonTerminal(58, '_gen13'))
    ctx.nonterminal = "_gen13"
    tree.list = True
    if current != None and current.id in nonterminal_follow[58] and current.id not in nonterminal_first[58]:
        return tree
    if current == None:
        return tree
    if rule == 41: # $_gen13 = :comma :identifier $_gen13
        ctx.rule = rules[41]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 15) # :comma
        tree.add(t)
        tree.listSeparator = t
        t = expect(ctx, 1) # :identifier
        tree.add(t)
        subtree = parse__gen13(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_regex_enumeration(ctx):
    current = ctx.tokens.current()
    rule = table[13][current.id] if current else -1
    tree = ParseTree(NonTerminal(59, 'regex_enumeration'))
    ctx.nonterminal = "regex_enumeration"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 39: # $regex_enumeration = :identifier :colon :regex $_gen11 -> RegexEnum( language=$0, regex=$2, options=$3 )
        ctx.rule = rules[39]
        ast_parameters = OrderedDict([
            ('language', 0),
            ('regex', 2),
            ('options', 3),
        ])
        tree.astTransform = AstTransformNodeCreator('RegexEnum', ast_parameters)
        t = expect(ctx, 1) # :identifier
        tree.add(t)
        t = expect(ctx, 12) # :colon
        tree.add(t)
        t = expect(ctx, 40) # :regex
        tree.add(t)
        subtree = parse__gen11(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[59] if x >=0],
      rules[39]
    )
def parse_lexer_partials(ctx):
    current = ctx.tokens.current()
    rule = table[14][current.id] if current else -1
    tree = ParseTree(NonTerminal(60, 'lexer_partials'))
    ctx.nonterminal = "lexer_partials"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 22: # $lexer_partials = :partials :lbrace $_gen4 :rbrace -> RegexPartials( list=$2 )
        ctx.rule = rules[22]
        ast_parameters = OrderedDict([
            ('list', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('RegexPartials', ast_parameters)
        t = expect(ctx, 7) # :partials
        tree.add(t)
        t = expect(ctx, 0) # :lbrace
        tree.add(t)
        subtree = parse__gen4(ctx)
        tree.add(subtree)
        t = expect(ctx, 20) # :rbrace
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[60] if x >=0],
      rules[22]
    )
def parse__gen15(ctx):
    current = ctx.tokens.current()
    rule = table[15][current.id] if current else -1
    tree = ParseTree(NonTerminal(61, '_gen15'))
    ctx.nonterminal = "_gen15"
    tree.list = False
    if current != None and current.id in nonterminal_follow[61] and current.id not in nonterminal_first[61]:
        return tree
    if current == None:
        return tree
    if rule == 52: # $_gen15 = $match_group
        ctx.rule = rules[52]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_match_group(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_parser_ll1(ctx):
    current = ctx.tokens.current()
    rule = table[16][current.id] if current else -1
    tree = ParseTree(NonTerminal(62, 'parser_ll1'))
    ctx.nonterminal = "parser_ll1"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 65: # $parser_ll1 = :parser :lbrace $_gen16 :rbrace -> Parser( rules=$2 )
        ctx.rule = rules[65]
        ast_parameters = OrderedDict([
            ('rules', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('Parser', ast_parameters)
        t = expect(ctx, 26) # :parser
        tree.add(t)
        t = expect(ctx, 0) # :lbrace
        tree.add(t)
        subtree = parse__gen16(ctx)
        tree.add(subtree)
        t = expect(ctx, 20) # :rbrace
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[62] if x >=0],
      rules[65]
    )
def parse_associativity(ctx):
    current = ctx.tokens.current()
    rule = table[17][current.id] if current else -1
    tree = ParseTree(NonTerminal(63, 'associativity'))
    ctx.nonterminal = "associativity"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 100: # $associativity = :left
        ctx.rule = rules[100]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 32) # :left
        tree.add(t)
        return tree
    elif rule == 101: # $associativity = :right
        ctx.rule = rules[101]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 16) # :right
        tree.add(t)
        return tree
    elif rule == 102: # $associativity = :unary
        ctx.rule = rules[102]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 35) # :unary
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[63] if x >=0],
      rules[102]
    )
def parse__gen30(ctx):
    current = ctx.tokens.current()
    rule = table[18][current.id] if current else -1
    tree = ParseTree(NonTerminal(64, '_gen30'))
    ctx.nonterminal = "_gen30"
    tree.list = True
    if current != None and current.id in nonterminal_follow[64] and current.id not in nonterminal_first[64]:
        return tree
    if current == None:
        return tree
    if rule == 115: # $_gen30 = :comma $macro_parameter $_gen30
        ctx.rule = rules[115]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 15) # :comma
        tree.add(t)
        tree.listSeparator = t
        subtree = parse_macro_parameter(ctx)
        tree.add(subtree)
        subtree = parse__gen30(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen1(ctx):
    current = ctx.tokens.current()
    rule = table[19][current.id] if current else -1
    tree = ParseTree(NonTerminal(65, '_gen1'))
    ctx.nonterminal = "_gen1"
    tree.list = True
    if current != None and current.id in nonterminal_follow[65] and current.id not in nonterminal_first[65]:
        return tree
    if current == None:
        return tree
    if rule == 1: # $_gen1 = $body_element $_gen1
        ctx.rule = rules[1]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_body_element(ctx)
        tree.add(subtree)
        subtree = parse__gen1(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_lexer_code(ctx):
    current = ctx.tokens.current()
    rule = table[20][current.id] if current else -1
    tree = ParseTree(NonTerminal(66, 'lexer_code'))
    ctx.nonterminal = "lexer_code"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 17: # $lexer_code = :code_start :language :code -> LexerCode( language=$1, code=$2 )
        ctx.rule = rules[17]
        ast_parameters = OrderedDict([
            ('language', 1),
            ('code', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('LexerCode', ast_parameters)
        t = expect(ctx, 43) # :code_start
        tree.add(t)
        t = expect(ctx, 42) # :language
        tree.add(t)
        t = expect(ctx, 5) # :code
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[66] if x >=0],
      rules[17]
    )
def parse__gen16(ctx):
    current = ctx.tokens.current()
    rule = table[21][current.id] if current else -1
    tree = ParseTree(NonTerminal(67, '_gen16'))
    ctx.nonterminal = "_gen16"
    tree.list = True
    if current != None and current.id in nonterminal_follow[67] and current.id not in nonterminal_first[67]:
        return tree
    if current == None:
        return tree
    if rule == 61: # $_gen16 = $ll1_rule $_gen17
        ctx.rule = rules[61]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_ll1_rule(ctx)
        tree.add(subtree)
        subtree = parse__gen17(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_expression_rule(ctx):
    current = ctx.tokens.current()
    rule = table[22][current.id] if current else -1
    tree = ParseTree(NonTerminal(68, 'expression_rule'))
    ctx.nonterminal = "expression_rule"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 88: # $expression_rule = $_gen25 :expr_rule_hint :nonterminal :equals $expression_rule_production -> ExpressionRule( precedence=$0, nonterminal=$2, production=$4 )
        ctx.rule = rules[88]
        ast_parameters = OrderedDict([
            ('precedence', 0),
            ('nonterminal', 2),
            ('production', 4),
        ])
        tree.astTransform = AstTransformNodeCreator('ExpressionRule', ast_parameters)
        subtree = parse__gen25(ctx)
        tree.add(subtree)
        t = expect(ctx, 11) # :expr_rule_hint
        tree.add(t)
        t = expect(ctx, 24) # :nonterminal
        tree.add(t)
        t = expect(ctx, 34) # :equals
        tree.add(t)
        subtree = parse_expression_rule_production(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[68] if x >=0],
      rules[88]
    )
def parse_regex_partial(ctx):
    current = ctx.tokens.current()
    rule = table[23][current.id] if current else -1
    tree = ParseTree(NonTerminal(69, 'regex_partial'))
    ctx.nonterminal = "regex_partial"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 23: # $regex_partial = :regex :arrow :regex_partial -> RegexPartial( regex=$0, name=$2 )
        ctx.rule = rules[23]
        ast_parameters = OrderedDict([
            ('regex', 0),
            ('name', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('RegexPartial', ast_parameters)
        t = expect(ctx, 40) # :regex
        tree.add(t)
        t = expect(ctx, 28) # :arrow
        tree.add(t)
        t = expect(ctx, 36) # :regex_partial
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[69] if x >=0],
      rules[23]
    )
def parse__gen3(ctx):
    current = ctx.tokens.current()
    rule = table[24][current.id] if current else -1
    tree = ParseTree(NonTerminal(70, '_gen3'))
    ctx.nonterminal = "_gen3"
    tree.list = True
    if current != None and current.id in nonterminal_follow[70] and current.id not in nonterminal_first[70]:
        return tree
    if current == None:
        return tree
    if rule == 9: # $_gen3 = $lexer_atom $_gen3
        ctx.rule = rules[9]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer_atom(ctx)
        tree.add(subtree)
        subtree = parse__gen3(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_precedence(ctx):
    current = ctx.tokens.current()
    rule = table[25][current.id] if current else -1
    tree = ParseTree(NonTerminal(71, 'precedence'))
    ctx.nonterminal = "precedence"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 97: # $precedence = $binding_power_marker :colon $associativity -> Precedence( marker=$0, associativity=$2 )
        ctx.rule = rules[97]
        ast_parameters = OrderedDict([
            ('marker', 0),
            ('associativity', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('Precedence', ast_parameters)
        subtree = parse_binding_power_marker(ctx)
        tree.add(subtree)
        t = expect(ctx, 12) # :colon
        tree.add(t)
        subtree = parse_associativity(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[71] if x >=0],
      rules[97]
    )
def parse_lexer_atom(ctx):
    current = ctx.tokens.current()
    rule = table[26][current.id] if current else -1
    tree = ParseTree(NonTerminal(72, 'lexer_atom'))
    ctx.nonterminal = "lexer_atom"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 13: # $lexer_atom = $lexer_regex
        ctx.rule = rules[13]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer_regex(ctx)
        tree.add(subtree)
        return tree
    elif rule == 14: # $lexer_atom = $lexer_mode
        ctx.rule = rules[14]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer_mode(ctx)
        tree.add(subtree)
        return tree
    elif rule == 15: # $lexer_atom = $lexer_partials
        ctx.rule = rules[15]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer_partials(ctx)
        tree.add(subtree)
        return tree
    elif rule == 16: # $lexer_atom = $lexer_code
        ctx.rule = rules[16]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer_code(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[72] if x >=0],
      rules[16]
    )
def parse_rule(ctx):
    current = ctx.tokens.current()
    rule = table[27][current.id] if current else -1
    tree = ParseTree(NonTerminal(73, 'rule'))
    ctx.nonterminal = "rule"
    tree.list = False
    if current != None and current.id in nonterminal_follow[73] and current.id not in nonterminal_first[73]:
        return tree
    if current == None:
        return tree
    if rule == 78: # $rule = $_gen20 $_gen22 -> Production( morphemes=$0, ast=$1 )
        ctx.rule = rules[78]
        ast_parameters = OrderedDict([
            ('morphemes', 0),
            ('ast', 1),
        ])
        tree.astTransform = AstTransformNodeCreator('Production', ast_parameters)
        subtree = parse__gen20(ctx)
        tree.add(subtree)
        subtree = parse__gen22(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_led(ctx):
    current = ctx.tokens.current()
    rule = table[28][current.id] if current else -1
    tree = ParseTree(NonTerminal(74, 'led'))
    ctx.nonterminal = "led"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 95: # $led = :expression_divider $_gen20 -> $1
        ctx.rule = rules[95]
        tree.astTransform = AstTransformSubstitution(1)
        t = expect(ctx, 14) # :expression_divider
        tree.add(t)
        subtree = parse__gen20(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[74] if x >=0],
      rules[95]
    )
def parse__gen29(ctx):
    current = ctx.tokens.current()
    rule = table[29][current.id] if current else -1
    tree = ParseTree(NonTerminal(75, '_gen29'))
    ctx.nonterminal = "_gen29"
    tree.list = True
    if current != None and current.id in nonterminal_follow[75] and current.id not in nonterminal_first[75]:
        return tree
    if current == None:
        return tree
    if rule == 114: # $_gen29 = $macro_parameter $_gen30
        ctx.rule = rules[114]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_macro_parameter(ctx)
        tree.add(subtree)
        subtree = parse__gen30(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_macro(ctx):
    current = ctx.tokens.current()
    rule = table[30][current.id] if current else -1
    tree = ParseTree(NonTerminal(76, 'macro'))
    ctx.nonterminal = "macro"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 118: # $macro = :identifier :lparen $_gen29 :rparen -> Macro( name=$0, parameters=$2 )
        ctx.rule = rules[118]
        ast_parameters = OrderedDict([
            ('name', 0),
            ('parameters', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('Macro', ast_parameters)
        t = expect(ctx, 1) # :identifier
        tree.add(t)
        t = expect(ctx, 31) # :lparen
        tree.add(t)
        subtree = parse__gen29(ctx)
        tree.add(subtree)
        t = expect(ctx, 2) # :rparen
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[76] if x >=0],
      rules[118]
    )
def parse__gen2(ctx):
    current = ctx.tokens.current()
    rule = table[31][current.id] if current else -1
    tree = ParseTree(NonTerminal(77, '_gen2'))
    ctx.nonterminal = "_gen2"
    tree.list = True
    if current != None and current.id in nonterminal_follow[77] and current.id not in nonterminal_first[77]:
        return tree
    if current == None:
        return tree
    if rule == 8: # $_gen2 = $lexer_atom $_gen3
        ctx.rule = rules[8]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer_atom(ctx)
        tree.add(subtree)
        subtree = parse__gen3(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_regex_options(ctx):
    current = ctx.tokens.current()
    rule = table[32][current.id] if current else -1
    tree = ParseTree(NonTerminal(78, 'regex_options'))
    ctx.nonterminal = "regex_options"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 45: # $regex_options = :lbrace $_gen12 :rbrace -> $1
        ctx.rule = rules[45]
        tree.astTransform = AstTransformSubstitution(1)
        t = expect(ctx, 0) # :lbrace
        tree.add(t)
        subtree = parse__gen12(ctx)
        tree.add(subtree)
        t = expect(ctx, 20) # :rbrace
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[78] if x >=0],
      rules[45]
    )
def parse_expression_rule_production(ctx):
    current = ctx.tokens.current()
    rule = table[33][current.id] if current else -1
    tree = ParseTree(NonTerminal(79, 'expression_rule_production'))
    ctx.nonterminal = "expression_rule_production"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 91: # $expression_rule_production = :mixfix_rule_hint $nud $_gen22 $_gen26 $_gen22 -> MixfixProduction( nud=$1, nud_ast=$2, led=$3, ast=$4 )
        ctx.rule = rules[91]
        ast_parameters = OrderedDict([
            ('nud', 1),
            ('nud_ast', 2),
            ('led', 3),
            ('ast', 4),
        ])
        tree.astTransform = AstTransformNodeCreator('MixfixProduction', ast_parameters)
        t = expect(ctx, 30) # :mixfix_rule_hint
        tree.add(t)
        subtree = parse_nud(ctx)
        tree.add(subtree)
        subtree = parse__gen22(ctx)
        tree.add(subtree)
        subtree = parse__gen26(ctx)
        tree.add(subtree)
        subtree = parse__gen22(ctx)
        tree.add(subtree)
        return tree
    elif rule == 92: # $expression_rule_production = :prefix_rule_hint $_gen20 $_gen22 -> PrefixProduction( morphemes=$1, ast=$2 )
        ctx.rule = rules[92]
        ast_parameters = OrderedDict([
            ('morphemes', 1),
            ('ast', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('PrefixProduction', ast_parameters)
        t = expect(ctx, 41) # :prefix_rule_hint
        tree.add(t)
        subtree = parse__gen20(ctx)
        tree.add(subtree)
        subtree = parse__gen22(ctx)
        tree.add(subtree)
        return tree
    elif rule == 93: # $expression_rule_production = :infix_rule_hint $_gen20 $_gen22 -> InfixProduction( morphemes=$1, ast=$2 )
        ctx.rule = rules[93]
        ast_parameters = OrderedDict([
            ('morphemes', 1),
            ('ast', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('InfixProduction', ast_parameters)
        t = expect(ctx, 13) # :infix_rule_hint
        tree.add(t)
        subtree = parse__gen20(ctx)
        tree.add(subtree)
        subtree = parse__gen22(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[79] if x >=0],
      rules[93]
    )
def parse_macro_parameter(ctx):
    current = ctx.tokens.current()
    rule = table[34][current.id] if current else -1
    tree = ParseTree(NonTerminal(80, 'macro_parameter'))
    ctx.nonterminal = "macro_parameter"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 119: # $macro_parameter = :nonterminal
        ctx.rule = rules[119]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 24) # :nonterminal
        tree.add(t)
        return tree
    elif rule == 120: # $macro_parameter = :terminal
        ctx.rule = rules[120]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 39) # :terminal
        tree.add(t)
        return tree
    elif rule == 121: # $macro_parameter = :string
        ctx.rule = rules[121]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 45) # :string
        tree.add(t)
        return tree
    elif rule == 122: # $macro_parameter = :integer
        ctx.rule = rules[122]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 19) # :integer
        tree.add(t)
        return tree
    elif rule == 123: # $macro_parameter = :null
        ctx.rule = rules[123]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 8) # :null
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[80] if x >=0],
      rules[123]
    )
def parse_parser(ctx):
    current = ctx.tokens.current()
    rule = table[35][current.id] if current else -1
    tree = ParseTree(NonTerminal(81, 'parser'))
    ctx.nonterminal = "parser"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 59: # $parser = $parser_ll1
        ctx.rule = rules[59]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_parser_ll1(ctx)
        tree.add(subtree)
        return tree
    elif rule == 60: # $parser = $parser_expression
        ctx.rule = rules[60]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_parser_expression(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[81] if x >=0],
      rules[60]
    )
def parse_ast_transform(ctx):
    current = ctx.tokens.current()
    rule = table[36][current.id] if current else -1
    tree = ParseTree(NonTerminal(82, 'ast_transform'))
    ctx.nonterminal = "ast_transform"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 106: # $ast_transform = :arrow $ast_transform_sub -> $1
        ctx.rule = rules[106]
        tree.astTransform = AstTransformSubstitution(1)
        t = expect(ctx, 28) # :arrow
        tree.add(t)
        subtree = parse_ast_transform_sub(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[82] if x >=0],
      rules[106]
    )
def parse__gen25(ctx):
    current = ctx.tokens.current()
    rule = table[37][current.id] if current else -1
    tree = ParseTree(NonTerminal(83, '_gen25'))
    ctx.nonterminal = "_gen25"
    tree.list = False
    if current != None and current.id in nonterminal_follow[83] and current.id not in nonterminal_first[83]:
        return tree
    if current == None:
        return tree
    if rule == 86: # $_gen25 = $binding_power
        ctx.rule = rules[86]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_binding_power(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen27(ctx):
    current = ctx.tokens.current()
    rule = table[38][current.id] if current else -1
    tree = ParseTree(NonTerminal(84, '_gen27'))
    ctx.nonterminal = "_gen27"
    tree.list = True
    if current != None and current.id in nonterminal_follow[84] and current.id not in nonterminal_first[84]:
        return tree
    if current == None:
        return tree
    if rule == 107: # $_gen27 = $ast_parameter $_gen28
        ctx.rule = rules[107]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_ast_parameter(ctx)
        tree.add(subtree)
        subtree = parse__gen28(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_body_element(ctx):
    current = ctx.tokens.current()
    rule = table[39][current.id] if current else -1
    tree = ParseTree(NonTerminal(85, 'body_element'))
    ctx.nonterminal = "body_element"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 5: # $body_element = $body_element_sub
        ctx.rule = rules[5]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_body_element_sub(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[85] if x >=0],
      rules[5]
    )
def parse_lexer_regex(ctx):
    current = ctx.tokens.current()
    rule = table[40][current.id] if current else -1
    tree = ParseTree(NonTerminal(86, 'lexer_regex'))
    ctx.nonterminal = "lexer_regex"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 24: # $lexer_regex = $enumerated_regex
        ctx.rule = rules[24]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_enumerated_regex(ctx)
        tree.add(subtree)
        return tree
    elif rule == 31: # $lexer_regex = :regex $_gen6 :arrow $_gen7 -> Regex( regex=$0, options=$1, onmatch=$3 )
        ctx.rule = rules[31]
        ast_parameters = OrderedDict([
            ('regex', 0),
            ('options', 1),
            ('onmatch', 3),
        ])
        tree.astTransform = AstTransformNodeCreator('Regex', ast_parameters)
        t = expect(ctx, 40) # :regex
        tree.add(t)
        subtree = parse__gen6(ctx)
        tree.add(subtree)
        t = expect(ctx, 28) # :arrow
        tree.add(t)
        subtree = parse__gen7(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[86] if x >=0],
      rules[31]
    )
def parse__gen22(ctx):
    current = ctx.tokens.current()
    rule = table[41][current.id] if current else -1
    tree = ParseTree(NonTerminal(87, '_gen22'))
    ctx.nonterminal = "_gen22"
    tree.list = False
    if current != None and current.id in nonterminal_follow[87] and current.id not in nonterminal_first[87]:
        return tree
    if current == None:
        return tree
    if rule == 76: # $_gen22 = $ast_transform
        ctx.rule = rules[76]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_ast_transform(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_lexer_target(ctx):
    current = ctx.tokens.current()
    rule = table[42][current.id] if current else -1
    tree = ParseTree(NonTerminal(88, 'lexer_target'))
    ctx.nonterminal = "lexer_target"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 46: # $lexer_target = $terminal
        ctx.rule = rules[46]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_terminal(ctx)
        tree.add(subtree)
        return tree
    elif rule == 49: # $lexer_target = :identifier :lparen $_gen14 :rparen -> LexerFunctionCall( name=$0, terminal=$2 )
        ctx.rule = rules[49]
        ast_parameters = OrderedDict([
            ('name', 0),
            ('terminal', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('LexerFunctionCall', ast_parameters)
        t = expect(ctx, 1) # :identifier
        tree.add(t)
        t = expect(ctx, 31) # :lparen
        tree.add(t)
        subtree = parse__gen14(ctx)
        tree.add(subtree)
        t = expect(ctx, 2) # :rparen
        tree.add(t)
        return tree
    elif rule == 50: # $lexer_target = :stack_push
        ctx.rule = rules[50]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 3) # :stack_push
        tree.add(t)
        return tree
    elif rule == 51: # $lexer_target = :action
        ctx.rule = rules[51]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 10) # :action
        tree.add(t)
        return tree
    elif rule == 57: # $lexer_target = :null -> Null(  )
        ctx.rule = rules[57]
        ast_parameters = OrderedDict([
        ])
        tree.astTransform = AstTransformNodeCreator('Null', ast_parameters)
        t = expect(ctx, 8) # :null
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[88] if x >=0],
      rules[57]
    )
def parse_terminal(ctx):
    current = ctx.tokens.current()
    rule = table[43][current.id] if current else -1
    tree = ParseTree(NonTerminal(89, 'terminal'))
    ctx.nonterminal = "terminal"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 54: # $terminal = :terminal $_gen15 -> Terminal( name=$0, group=$1 )
        ctx.rule = rules[54]
        ast_parameters = OrderedDict([
            ('name', 0),
            ('group', 1),
        ])
        tree.astTransform = AstTransformNodeCreator('Terminal', ast_parameters)
        t = expect(ctx, 39) # :terminal
        tree.add(t)
        subtree = parse__gen15(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[89] if x >=0],
      rules[54]
    )
def parse__gen9(ctx):
    current = ctx.tokens.current()
    rule = table[44][current.id] if current else -1
    tree = ParseTree(NonTerminal(90, '_gen9'))
    ctx.nonterminal = "_gen9"
    tree.list = True
    if current != None and current.id in nonterminal_follow[90] and current.id not in nonterminal_first[90]:
        return tree
    if current == None:
        return tree
    if rule == 32: # $_gen9 = $regex_enumeration $_gen10
        ctx.rule = rules[32]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_regex_enumeration(ctx)
        tree.add(subtree)
        subtree = parse__gen10(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen19(ctx):
    current = ctx.tokens.current()
    rule = table[45][current.id] if current else -1
    tree = ParseTree(NonTerminal(91, '_gen19'))
    ctx.nonterminal = "_gen19"
    tree.list = True
    if current != None and current.id in nonterminal_follow[91] and current.id not in nonterminal_first[91]:
        return tree
    if current == None:
        return tree
    if rule == 68: # $_gen19 = :pipe $rule $_gen19
        ctx.rule = rules[68]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 9) # :pipe
        tree.add(t)
        tree.listSeparator = t
        subtree = parse_rule(ctx)
        tree.add(subtree)
        subtree = parse__gen19(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen17(ctx):
    current = ctx.tokens.current()
    rule = table[46][current.id] if current else -1
    tree = ParseTree(NonTerminal(92, '_gen17'))
    ctx.nonterminal = "_gen17"
    tree.list = True
    if current != None and current.id in nonterminal_follow[92] and current.id not in nonterminal_first[92]:
        return tree
    if current == None:
        return tree
    if rule == 62: # $_gen17 = $ll1_rule $_gen17
        ctx.rule = rules[62]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_ll1_rule(ctx)
        tree.add(subtree)
        subtree = parse__gen17(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen18(ctx):
    current = ctx.tokens.current()
    rule = table[47][current.id] if current else -1
    tree = ParseTree(NonTerminal(93, '_gen18'))
    ctx.nonterminal = "_gen18"
    tree.list = True
    if current != None and current.id in nonterminal_follow[93] and current.id not in nonterminal_first[93]:
        return tree
    if current == None:
        return tree
    if rule == 67: # $_gen18 = $rule $_gen19
        ctx.rule = rules[67]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_rule(ctx)
        tree.add(subtree)
        subtree = parse__gen19(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen23(ctx):
    current = ctx.tokens.current()
    rule = table[48][current.id] if current else -1
    tree = ParseTree(NonTerminal(94, '_gen23'))
    ctx.nonterminal = "_gen23"
    tree.list = True
    if current != None and current.id in nonterminal_follow[94] and current.id not in nonterminal_first[94]:
        return tree
    if current == None:
        return tree
    if rule == 81: # $_gen23 = $expression_rule $_gen24
        ctx.rule = rules[81]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_expression_rule(ctx)
        tree.add(subtree)
        subtree = parse__gen24(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_grammar(ctx):
    current = ctx.tokens.current()
    rule = table[49][current.id] if current else -1
    tree = ParseTree(NonTerminal(95, 'grammar'))
    ctx.nonterminal = "grammar"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 4: # $grammar = :grammar :lbrace $_gen0 :rbrace -> Grammar( body=$2 )
        ctx.rule = rules[4]
        ast_parameters = OrderedDict([
            ('body', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('Grammar', ast_parameters)
        t = expect(ctx, 38) # :grammar
        tree.add(t)
        t = expect(ctx, 0) # :lbrace
        tree.add(t)
        subtree = parse__gen0(ctx)
        tree.add(subtree)
        t = expect(ctx, 20) # :rbrace
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[95] if x >=0],
      rules[4]
    )
def parse_morpheme(ctx):
    current = ctx.tokens.current()
    rule = table[50][current.id] if current else -1
    tree = ParseTree(NonTerminal(96, 'morpheme'))
    ctx.nonterminal = "morpheme"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 103: # $morpheme = :terminal
        ctx.rule = rules[103]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 39) # :terminal
        tree.add(t)
        return tree
    elif rule == 104: # $morpheme = :nonterminal
        ctx.rule = rules[104]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 24) # :nonterminal
        tree.add(t)
        return tree
    elif rule == 105: # $morpheme = $macro
        ctx.rule = rules[105]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_macro(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[96] if x >=0],
      rules[105]
    )
def parse__gen0(ctx):
    current = ctx.tokens.current()
    rule = table[51][current.id] if current else -1
    tree = ParseTree(NonTerminal(97, '_gen0'))
    ctx.nonterminal = "_gen0"
    tree.list = True
    if current != None and current.id in nonterminal_follow[97] and current.id not in nonterminal_first[97]:
        return tree
    if current == None:
        return tree
    if rule == 0: # $_gen0 = $body_element $_gen1
        ctx.rule = rules[0]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_body_element(ctx)
        tree.add(subtree)
        subtree = parse__gen1(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen14(ctx):
    current = ctx.tokens.current()
    rule = table[52][current.id] if current else -1
    tree = ParseTree(NonTerminal(98, '_gen14'))
    ctx.nonterminal = "_gen14"
    tree.list = False
    if current != None and current.id in nonterminal_follow[98] and current.id not in nonterminal_first[98]:
        return tree
    if current == None:
        return tree
    if rule == 47: # $_gen14 = $terminal
        ctx.rule = rules[47]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_terminal(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen28(ctx):
    current = ctx.tokens.current()
    rule = table[53][current.id] if current else -1
    tree = ParseTree(NonTerminal(99, '_gen28'))
    ctx.nonterminal = "_gen28"
    tree.list = True
    if current != None and current.id in nonterminal_follow[99] and current.id not in nonterminal_first[99]:
        return tree
    if current == None:
        return tree
    if rule == 108: # $_gen28 = :comma $ast_parameter $_gen28
        ctx.rule = rules[108]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 15) # :comma
        tree.add(t)
        tree.listSeparator = t
        subtree = parse_ast_parameter(ctx)
        tree.add(subtree)
        subtree = parse__gen28(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_regex_enumeration_options(ctx):
    current = ctx.tokens.current()
    rule = table[54][current.id] if current else -1
    tree = ParseTree(NonTerminal(100, 'regex_enumeration_options'))
    ctx.nonterminal = "regex_enumeration_options"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 44: # $regex_enumeration_options = :lparen $_gen12 :rparen -> $1
        ctx.rule = rules[44]
        tree.astTransform = AstTransformSubstitution(1)
        t = expect(ctx, 31) # :lparen
        tree.add(t)
        subtree = parse__gen12(ctx)
        tree.add(subtree)
        t = expect(ctx, 2) # :rparen
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[100] if x >=0],
      rules[44]
    )
def parse__gen8(ctx):
    current = ctx.tokens.current()
    rule = table[55][current.id] if current else -1
    tree = ParseTree(NonTerminal(101, '_gen8'))
    ctx.nonterminal = "_gen8"
    tree.list = True
    if current != None and current.id in nonterminal_follow[101] and current.id not in nonterminal_first[101]:
        return tree
    if current == None:
        return tree
    if rule == 28: # $_gen8 = $lexer_target $_gen8
        ctx.rule = rules[28]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer_target(ctx)
        tree.add(subtree)
        subtree = parse__gen8(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_ll1_rule(ctx):
    current = ctx.tokens.current()
    rule = table[56][current.id] if current else -1
    tree = ParseTree(NonTerminal(102, 'll1_rule'))
    ctx.nonterminal = "ll1_rule"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 66: # $ll1_rule = :ll1_rule_hint :nonterminal :equals $ll1_rule_rhs -> Rule( nonterminal=$1, production=$3 )
        ctx.rule = rules[66]
        ast_parameters = OrderedDict([
            ('nonterminal', 1),
            ('production', 3),
        ])
        tree.astTransform = AstTransformNodeCreator('Rule', ast_parameters)
        t = expect(ctx, 37) # :ll1_rule_hint
        tree.add(t)
        t = expect(ctx, 24) # :nonterminal
        tree.add(t)
        t = expect(ctx, 34) # :equals
        tree.add(t)
        subtree = parse_ll1_rule_rhs(ctx)
        tree.add(subtree)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[102] if x >=0],
      rules[66]
    )
def parse_nud(ctx):
    current = ctx.tokens.current()
    rule = table[57][current.id] if current else -1
    tree = ParseTree(NonTerminal(103, 'nud'))
    ctx.nonterminal = "nud"
    tree.list = False
    if current != None and current.id in nonterminal_follow[103] and current.id not in nonterminal_first[103]:
        return tree
    if current == None:
        return tree
    if rule == 94: # $nud = $_gen20
        ctx.rule = rules[94]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse__gen20(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen7(ctx):
    current = ctx.tokens.current()
    rule = table[58][current.id] if current else -1
    tree = ParseTree(NonTerminal(104, '_gen7'))
    ctx.nonterminal = "_gen7"
    tree.list = True
    if current != None and current.id in nonterminal_follow[104] and current.id not in nonterminal_first[104]:
        return tree
    if current == None:
        return tree
    if rule == 27: # $_gen7 = $lexer_target $_gen8
        ctx.rule = rules[27]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_lexer_target(ctx)
        tree.add(subtree)
        subtree = parse__gen8(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen21(ctx):
    current = ctx.tokens.current()
    rule = table[59][current.id] if current else -1
    tree = ParseTree(NonTerminal(105, '_gen21'))
    ctx.nonterminal = "_gen21"
    tree.list = True
    if current != None and current.id in nonterminal_follow[105] and current.id not in nonterminal_first[105]:
        return tree
    if current == None:
        return tree
    if rule == 73: # $_gen21 = $morpheme $_gen21
        ctx.rule = rules[73]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_morpheme(ctx)
        tree.add(subtree)
        subtree = parse__gen21(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen10(ctx):
    current = ctx.tokens.current()
    rule = table[60][current.id] if current else -1
    tree = ParseTree(NonTerminal(106, '_gen10'))
    ctx.nonterminal = "_gen10"
    tree.list = True
    if current != None and current.id in nonterminal_follow[106] and current.id not in nonterminal_first[106]:
        return tree
    if current == None:
        return tree
    if rule == 33: # $_gen10 = $regex_enumeration $_gen10
        ctx.rule = rules[33]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_regex_enumeration(ctx)
        tree.add(subtree)
        subtree = parse__gen10(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen12(ctx):
    current = ctx.tokens.current()
    rule = table[61][current.id] if current else -1
    tree = ParseTree(NonTerminal(107, '_gen12'))
    ctx.nonterminal = "_gen12"
    tree.list = True
    if current != None and current.id in nonterminal_follow[107] and current.id not in nonterminal_first[107]:
        return tree
    if current == None:
        return tree
    if rule == 40: # $_gen12 = :identifier $_gen13
        ctx.rule = rules[40]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 1) # :identifier
        tree.add(t)
        subtree = parse__gen13(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_match_group(ctx):
    current = ctx.tokens.current()
    rule = table[62][current.id] if current else -1
    tree = ParseTree(NonTerminal(108, 'match_group'))
    ctx.nonterminal = "match_group"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 55: # $match_group = :lsquare :integer :rsquare -> $1
        ctx.rule = rules[55]
        tree.astTransform = AstTransformSubstitution(1)
        t = expect(ctx, 27) # :lsquare
        tree.add(t)
        t = expect(ctx, 19) # :integer
        tree.add(t)
        t = expect(ctx, 33) # :rsquare
        tree.add(t)
        return tree
    elif rule == 56: # $match_group = :no_group
        ctx.rule = rules[56]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 17) # :no_group
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[108] if x >=0],
      rules[56]
    )
def parse_ast_transform_sub(ctx):
    current = ctx.tokens.current()
    rule = table[63][current.id] if current else -1
    tree = ParseTree(NonTerminal(109, 'ast_transform_sub'))
    ctx.nonterminal = "ast_transform_sub"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 111: # $ast_transform_sub = :identifier :lparen $_gen27 :rparen -> AstTransformation( name=$0, parameters=$2 )
        ctx.rule = rules[111]
        ast_parameters = OrderedDict([
            ('name', 0),
            ('parameters', 2),
        ])
        tree.astTransform = AstTransformNodeCreator('AstTransformation', ast_parameters)
        t = expect(ctx, 1) # :identifier
        tree.add(t)
        t = expect(ctx, 31) # :lparen
        tree.add(t)
        subtree = parse__gen27(ctx)
        tree.add(subtree)
        t = expect(ctx, 2) # :rparen
        tree.add(t)
        return tree
    elif rule == 112: # $ast_transform_sub = :nonterminal_reference
        ctx.rule = rules[112]
        tree.astTransform = AstTransformSubstitution(0)
        t = expect(ctx, 6) # :nonterminal_reference
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[109] if x >=0],
      rules[112]
    )
def parse__gen6(ctx):
    current = ctx.tokens.current()
    rule = table[64][current.id] if current else -1
    tree = ParseTree(NonTerminal(110, '_gen6'))
    ctx.nonterminal = "_gen6"
    tree.list = False
    if current != None and current.id in nonterminal_follow[110] and current.id not in nonterminal_first[110]:
        return tree
    if current == None:
        return tree
    if rule == 25: # $_gen6 = $regex_options
        ctx.rule = rules[25]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_regex_options(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse__gen11(ctx):
    current = ctx.tokens.current()
    rule = table[65][current.id] if current else -1
    tree = ParseTree(NonTerminal(111, '_gen11'))
    ctx.nonterminal = "_gen11"
    tree.list = False
    if current != None and current.id in nonterminal_follow[111] and current.id not in nonterminal_first[111]:
        return tree
    if current == None:
        return tree
    if rule == 37: # $_gen11 = $regex_enumeration_options
        ctx.rule = rules[37]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_regex_enumeration_options(ctx)
        tree.add(subtree)
        return tree
    return tree
def parse_binding_power(ctx):
    current = ctx.tokens.current()
    rule = table[66][current.id] if current else -1
    tree = ParseTree(NonTerminal(112, 'binding_power'))
    ctx.nonterminal = "binding_power"
    tree.list = False
    if current == None:
        raise ctx.errors.unexpected_eof()
    if rule == 96: # $binding_power = :lparen $precedence :rparen -> $1
        ctx.rule = rules[96]
        tree.astTransform = AstTransformSubstitution(1)
        t = expect(ctx, 31) # :lparen
        tree.add(t)
        subtree = parse_precedence(ctx)
        tree.add(subtree)
        t = expect(ctx, 2) # :rparen
        tree.add(t)
        return tree
    raise ctx.errors.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [terminals[x] for x in nonterminal_first[112] if x >=0],
      rules[96]
    )
def parse__gen4(ctx):
    current = ctx.tokens.current()
    rule = table[67][current.id] if current else -1
    tree = ParseTree(NonTerminal(113, '_gen4'))
    ctx.nonterminal = "_gen4"
    tree.list = True
    if current != None and current.id in nonterminal_follow[113] and current.id not in nonterminal_first[113]:
        return tree
    if current == None:
        return tree
    if rule == 18: # $_gen4 = $regex_partial $_gen5
        ctx.rule = rules[18]
        tree.astTransform = AstTransformSubstitution(0)
        subtree = parse_regex_partial(ctx)
        tree.add(subtree)
        subtree = parse__gen5(ctx)
        tree.add(subtree)
        return tree
    return tree
# Lexer Code #
# START USER CODE
# END USER CODE
def emit(ctx, terminal, source_string, line, col):
    if terminal:
        ctx.tokens.append(Terminal(terminals[terminal], terminal, source_string, ctx.resource, line, col))
def default_action(ctx, terminal, source_string, line, col):
    emit(ctx, terminal, source_string, line, col)
def init():
    return {}
def destroy(context):
    pass
class LexerStackPush:
    def __init__(self, mode):
        self.mode = mode
class LexerAction:
    def __init__(self, action):
        self.action = action
class LexerContext:
    def __init__(self, string, resource, errors, user_context):
        self.__dict__.update(locals())
        self.stack = ['default']
        self.line = 1
        self.col = 1
        self.tokens = []
        self.user_context = user_context
        self.re_match = None # https://docs.python.org/3/library/re.html#match-objects
class HermesLexer:
    regex = {
        'default': OrderedDict([
          (re.compile(r'(grammar)\s*({)'), [
              # (terminal, group, function)
              ('grammar', 1, None),
              ('lbrace', 2, None),
              LexerStackPush('grammar'),
          ]),
          (re.compile(r'\s+'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'\#.*'), [
              # (terminal, group, function)
          ]),
        ]),
        'grammar': OrderedDict([
          (re.compile(r'\s+'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'\#.*'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'}'), [
              # (terminal, group, function)
              ('rbrace', 0, None),
              LexerAction('pop'),
          ]),
          (re.compile(r'lexer'), [
              # (terminal, group, function)
              ('lexer', 0, None),
              LexerStackPush('lexer'),
          ]),
          (re.compile(r'parser'), [
              # (terminal, group, function)
              ('parser', 0, None),
              LexerStackPush('parser'),
          ]),
        ]),
        'lexer': OrderedDict([
          (re.compile(r'\s+'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'\#.*'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'code<([a-z]+)>\s*<<\s*([a-zA-Z_]+)(?=\s)(.*?)(\2)', re.DOTALL), [
              # (terminal, group, function)
              ('code_start', 2, None),
              ('language', 1, None),
              ('code', 3, None),
          ]),
          (re.compile(r'}'), [
              # (terminal, group, function)
              ('rbrace', 0, None),
              LexerAction('pop'),
          ]),
          (re.compile(r'{'), [
              # (terminal, group, function)
              ('lbrace', 0, None),
          ]),
          (re.compile(r'<'), [
              # (terminal, group, function)
              ('langle', 0, None),
          ]),
          (re.compile(r'>'), [
              # (terminal, group, function)
              ('rangle', 0, None),
          ]),
          (re.compile(r'\('), [
              # (terminal, group, function)
              ('lparen', 0, None),
          ]),
          (re.compile(r'\)'), [
              # (terminal, group, function)
              ('rparen', 0, None),
          ]),
          (re.compile(r'\[\]'), [
              # (terminal, group, function)
              ('no_group', 0, None),
          ]),
          (re.compile(r'\['), [
              # (terminal, group, function)
              ('lsquare', 0, None),
          ]),
          (re.compile(r'\]'), [
              # (terminal, group, function)
              ('rsquare', 0, None),
          ]),
          (re.compile(r'[0-9]+'), [
              # (terminal, group, function)
              ('integer', 0, None),
          ]),
          (re.compile(r'(r\'(\\\'|[^\'])*\'|"(\\\"|[^\"])*")'), [
              # (terminal, group, function)
              ('regex', 0, None),
              LexerStackPush('regex_options'),
          ]),
          (re.compile(r'->'), [
              # (terminal, group, function)
              ('arrow', 0, None),
          ]),
          (re.compile(r','), [
              # (terminal, group, function)
              ('comma', 0, None),
          ]),
          (re.compile(r'@([a-zA-Z][a-zA-Z0-9_]*)'), [
              # (terminal, group, function)
              ('stack_push', 1, None),
          ]),
          (re.compile(r'%([a-zA-Z][a-zA-Z0-9_]*)'), [
              # (terminal, group, function)
              ('action', 1, None),
          ]),
          (re.compile(r':([a-zA-Z][a-zA-Z0-9_]*|_empty)'), [
              # (terminal, group, function)
              ('terminal', 1, None),
          ]),
          (re.compile(r'_[a-zA-Z][a-zA-Z0-9_]*'), [
              # (terminal, group, function)
              ('regex_partial', 0, None),
          ]),
          (re.compile(r'null'), [
              # (terminal, group, function)
              ('null', 0, None),
          ]),
          (re.compile(r'mode'), [
              # (terminal, group, function)
              ('mode', 0, None),
              LexerStackPush('lexer'),
          ]),
          (re.compile(r'partials'), [
              # (terminal, group, function)
              ('partials', 0, None),
              LexerStackPush('lexer'),
          ]),
          (re.compile(r'enum'), [
              # (terminal, group, function)
              ('regex_enum', 0, None),
              LexerStackPush('regex_enum'),
          ]),
          (re.compile(r'[a-zA-Z][a-zA-Z0-9_]*'), [
              # (terminal, group, function)
              ('identifier', 0, None),
          ]),
        ]),
        'regex_enum': OrderedDict([
          (re.compile(r'\s+'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'\#.*'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'}'), [
              # (terminal, group, function)
              ('rbrace', 0, None),
              LexerAction('pop'),
          ]),
          (re.compile(r'{'), [
              # (terminal, group, function)
              ('lbrace', 0, None),
          ]),
          (re.compile(r'\('), [
              # (terminal, group, function)
              ('lparen', 0, None),
          ]),
          (re.compile(r'\)'), [
              # (terminal, group, function)
              ('rparen', 0, None),
          ]),
          (re.compile(r':'), [
              # (terminal, group, function)
              ('colon', 0, None),
          ]),
          (re.compile(r','), [
              # (terminal, group, function)
              ('comma', 0, None),
          ]),
          (re.compile(r'(r\'(\\\'|[^\'])*\'|"(\\\"|[^\"])*")'), [
              # (terminal, group, function)
              ('regex', 0, None),
          ]),
          (re.compile(r'[a-zA-Z][a-zA-Z0-9_]*'), [
              # (terminal, group, function)
              ('identifier', 0, None),
          ]),
        ]),
        'regex_options': OrderedDict([
          (re.compile(r'\s+'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'\#.*'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'[a-zA-Z][a-zA-Z0-9_]*'), [
              # (terminal, group, function)
              ('identifier', 0, None),
          ]),
          (re.compile(r','), [
              # (terminal, group, function)
              ('comma', 0, None),
          ]),
          (re.compile(r'{'), [
              # (terminal, group, function)
              ('lbrace', 0, None),
          ]),
          (re.compile(r'}'), [
              # (terminal, group, function)
              ('rbrace', 0, None),
          ]),
          (re.compile(r'->'), [
              # (terminal, group, function)
              ('arrow', 0, None),
              LexerAction('pop'),
          ]),
        ]),
        'parser': OrderedDict([
          (re.compile(r'\s+'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'\#.*'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'{'), [
              # (terminal, group, function)
              ('lbrace', 0, None),
          ]),
          (re.compile(r'}'), [
              # (terminal, group, function)
              ('rbrace', 0, None),
              LexerAction('pop'),
          ]),
          (re.compile(r'\|'), [
              # (terminal, group, function)
              ('pipe', 0, None),
          ]),
          (re.compile(r'='), [
              # (terminal, group, function)
              ('equals', 0, None),
          ]),
          (re.compile(r'\('), [
              # (terminal, group, function)
              ('lparen', 0, None),
          ]),
          (re.compile(r'\)'), [
              # (terminal, group, function)
              ('rparen', 0, None),
          ]),
          (re.compile(r','), [
              # (terminal, group, function)
              ('comma', 0, None),
          ]),
          (re.compile(r'->'), [
              # (terminal, group, function)
              ('arrow', 0, None),
          ]),
          (re.compile(r'null'), [
              # (terminal, group, function)
              ('null', 0, None),
          ]),
          (re.compile(r'parser\s*<\s*expression\s*>\s*({)'), [
              # (terminal, group, function)
              ('parser_expression', None, None),
              ('lbrace', 1, None),
              LexerStackPush('parser_expr'),
          ]),
          (re.compile(r':([a-zA-Z][a-zA-Z0-9_]*|_empty)'), [
              # (terminal, group, function)
              ('terminal', 1, None),
          ]),
          (re.compile(r'\$([a-zA-Z][a-zA-Z0-9_]*)(?=\s*\=)'), [
              # (terminal, group, function)
              ('ll1_rule_hint', None, None),
              ('nonterminal', 1, None),
          ]),
          (re.compile(r'\$([a-zA-Z][a-zA-Z0-9_]*)'), [
              # (terminal, group, function)
              ('nonterminal', 1, None),
          ]),
          (re.compile(r'\$([0-9]+|\$)'), [
              # (terminal, group, function)
              ('nonterminal_reference', 1, None),
          ]),
          (re.compile(r'[a-zA-Z][a-zA-Z0-9_]*'), [
              # (terminal, group, function)
              ('identifier', 0, None),
          ]),
          (re.compile(r'"[^"]+"'), [
              # (terminal, group, function)
              ('string', 0, None),
          ]),
          (re.compile(r'[0-9]+'), [
              # (terminal, group, function)
              ('integer', 0, None),
          ]),
        ]),
        'parser_expr': OrderedDict([
          (re.compile(r'\s+'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'\#.*'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'(\()(?=\s*[\*-])'), [
              # (terminal, group, function)
              ('lparen', 1, None),
              LexerStackPush('binding_power'),
          ]),
          (re.compile(r'->'), [
              # (terminal, group, function)
              ('arrow', 0, None),
          ]),
          (re.compile(r'<=>'), [
              # (terminal, group, function)
              ('expression_divider', 0, None),
          ]),
          (re.compile(r'\|'), [
              # (terminal, group, function)
              ('pipe', 0, None),
          ]),
          (re.compile(r'='), [
              # (terminal, group, function)
              ('equals', 0, None),
          ]),
          (re.compile(r'{'), [
              # (terminal, group, function)
              ('lbrace', 0, None),
          ]),
          (re.compile(r'}'), [
              # (terminal, group, function)
              ('rbrace', 0, None),
              LexerAction('pop'),
          ]),
          (re.compile(r'\('), [
              # (terminal, group, function)
              ('lparen', 0, None),
          ]),
          (re.compile(r'\)'), [
              # (terminal, group, function)
              ('rparen', 0, None),
          ]),
          (re.compile(r','), [
              # (terminal, group, function)
              ('comma', 0, None),
          ]),
          (re.compile(r':([a-zA-Z][a-zA-Z0-9_]*|_empty)'), [
              # (terminal, group, function)
              ('terminal', 1, None),
          ]),
          (re.compile(r'(\$([a-zA-Z][a-zA-Z0-9_]*))[ \t]*(=)[ \t]*\1[ \t]+:([a-zA-Z][a-zA-Z0-9_]*)[ \t]+\1(?![ \t]+(:|\$))'), [
              # (terminal, group, function)
              ('expr_rule_hint', None, None),
              ('nonterminal', 2, None),
              ('equals', 3, None),
              ('infix_rule_hint', None, None),
              ('nonterminal', 2, None),
              ('terminal', 4, None),
              ('nonterminal', 2, None),
          ]),
          (re.compile(r'(\$([a-zA-Z][a-zA-Z0-9_]*))[ \t]*(=)[ \t]*:([a-zA-Z][a-zA-Z0-9_]*)[ \t]+\1(?![ \t](:|\$))'), [
              # (terminal, group, function)
              ('expr_rule_hint', None, None),
              ('nonterminal', 2, None),
              ('equals', 3, None),
              ('prefix_rule_hint', None, None),
              ('terminal', 4, None),
              ('nonterminal', 2, None),
          ]),
          (re.compile(r'\$([a-zA-Z][a-zA-Z0-9_]*)\s*(=)'), [
              # (terminal, group, function)
              ('expr_rule_hint', None, None),
              ('nonterminal', 1, None),
              ('equals', 2, None),
              ('mixfix_rule_hint', None, None),
          ]),
          (re.compile(r'\$([a-zA-Z][a-zA-Z0-9_]*)'), [
              # (terminal, group, function)
              ('nonterminal', 1, None),
          ]),
          (re.compile(r'\$([0-9]+|\$)'), [
              # (terminal, group, function)
              ('nonterminal_reference', 1, None),
          ]),
          (re.compile(r'[a-zA-Z][a-zA-Z0-9_]*'), [
              # (terminal, group, function)
              ('identifier', 0, None),
          ]),
          (re.compile(r'"[^"]+"'), [
              # (terminal, group, function)
              ('string', 0, None),
          ]),
          (re.compile(r'[0-9]+'), [
              # (terminal, group, function)
              ('integer', 0, None),
          ]),
        ]),
        'binding_power': OrderedDict([
          (re.compile(r'\s+'), [
              # (terminal, group, function)
          ]),
          (re.compile(r'\*'), [
              # (terminal, group, function)
              ('asterisk', 0, None),
          ]),
          (re.compile(r'-'), [
              # (terminal, group, function)
              ('dash', 0, None),
          ]),
          (re.compile(r':'), [
              # (terminal, group, function)
              ('colon', 0, None),
          ]),
          (re.compile(r'left'), [
              # (terminal, group, function)
              ('left', 0, None),
          ]),
          (re.compile(r'right'), [
              # (terminal, group, function)
              ('right', 0, None),
          ]),
          (re.compile(r'unary'), [
              # (terminal, group, function)
              ('unary', 0, None),
          ]),
          (re.compile(r'\)'), [
              # (terminal, group, function)
              ('rparen', 0, None),
              LexerAction('pop'),
          ]),
        ]),
    }
    def _advance_line_col(self, string, length, line, col):
        for i in range(length):
            if string[i] == '\n':
                line += 1
                col = 1
            else:
                col += 1
        return (line, col)
    def _advance_string(self, ctx, string):
        (ctx.line, ctx.col) = self._advance_line_col(string, len(string), ctx.line, ctx.col)
        ctx.string = ctx.string[len(string):]
    def _next(self, ctx, debug=False):
        for regex, outputs in self.regex[ctx.stack[-1]].items():
            if debug:
                from xtermcolor import colorize
                token_count = len(ctx.tokens)
                print('{1} ({2}, {3}) regex: {0}'.format(
                    colorize(regex.pattern, ansi=40), colorize(ctx.string[:20].replace('\n', '\\n'), ansi=15), ctx.line, ctx.col)
                )
            match = regex.match(ctx.string)
            if match:
                ctx.re_match = match
                for output in outputs:
                    if isinstance(output, tuple):
                        (terminal, group, function) = output
                        function = function if function else default_action
                        source_string = match.group(group) if group is not None else ''
                        (group_line, group_col) = self._advance_line_col(ctx.string, match.start(group) if group else 0, ctx.line, ctx.col)
                        function(
                            ctx,
                            terminal,
                            source_string,
                            group_line,
                            group_col
                        )
                        if debug:
                            print('    matched: {}'.format(colorize(match.group(0).replace('\n', '\\n'), ansi=3)))
                            for token in ctx.tokens[token_count:]:
                                print('    emit: [{}] [{}, {}] [{}] stack:{} context:{}'.format(
                                    colorize(token.str, ansi=9),
                                    colorize(str(token.line), ansi=5),
                                    colorize(str(token.col), ansi=5),
                                    colorize(token.source_string, ansi=3),
                                    colorize(str(ctx.stack), ansi=4),
                                    colorize(str(ctx.user_context), ansi=13)
                                ))
                            token_count = len(ctx.tokens)
                    if isinstance(output, LexerStackPush):
                        ctx.stack.append(output.mode)
                        if debug:
                            print('    push on stack: {}'.format(colorize(output.mode, ansi=4)))
                    if isinstance(output, LexerAction):
                        if output.action == 'pop':
                            mode = ctx.stack.pop()
                            if debug:
                                print('    pop off stack: {}'.format(colorize(mode, ansi=4)))
                self._advance_string(ctx, match.group(0))
                return len(match.group(0)) > 0
        return False
    def lex(self, string, resource, errors=None, debug=False):
        if errors is None:
            errors = DefaultSyntaxErrorHandler()
        string_copy = string
        user_context = init()
        ctx = LexerContext(string, resource, errors, user_context)
        while len(ctx.string):
            matched = self._next(ctx, debug)
            if matched == False:
                raise ctx.errors.unrecognized_token(string_copy, ctx.line, ctx.col)
        destroy(ctx.user_context)
        return ctx.tokens
def lex(source, resource, errors=None, debug=False):
    return TokenStream(HermesLexer().lex(source, resource, errors, debug))
