import sys
import os
import re
import base64
import argparse
import json
from collections import OrderedDict

{% import re %}
{% from hermes.Grammar import AstTranslation, AstSpecification, ExprRule %}
{% from hermes.Grammar import PrefixOperator, InfixOperator %}
{% from hermes.Macro import SeparatedListMacro, MorphemeListMacro, TerminatedListMacro, MinimumListMacro, OptionalMacro, OptionallyTerminatedListMacro %}
{% from hermes.Morpheme import Terminal, NonTerminal %}

###############
# Common Code #
###############

def no_color(string, color):
  return string

def term_color(string, intcolor):
  return "\033[38;5;{0}m{1}\033[0m".format(intcolor, string)

def parse_tree_string(parsetree, indent=None, color=no_color, b64_source=False, indent_level=0):
    indent_str = (' ' * indent * indent_level) if indent else ''
    if isinstance(parsetree, ParseTree):
        children = [parse_tree_string(child, indent, color, b64_source, indent_level+1) for child in parsetree.children]
        if indent is None or len(children) == 0:
            return '{0}({1}: {2})'.format(indent_str, color(parsetree.nonterminal, 10), ', '.join(children))
        else:
            return '{0}({1}:\n{2}\n{3})'.format(
                indent_str,
                color(parsetree.nonterminal, 10),
                ',\n'.join(children),
                indent_str
            )
    elif isinstance(parsetree, Terminal):
        return indent_str + color(parsetree.dumps(b64_source=b64_source), 6)

def ast_string(ast, indent=None, color=no_color, b64_source=False, indent_level=0):
    indent_str = (' ' * indent * indent_level) if indent else ''
    next_indent_str = (' ' * indent * (indent_level+1)) if indent else ''
    if isinstance(ast, Ast):
        children = OrderedDict([(k, ast_string(v, indent, color, b64_source, indent_level+1)) for k, v in ast.attributes.items()])
        if indent is None:
            return '({0}: {1})'.format(
                color(ast.name, 9),
                ', '.join('{0}={1}'.format(color(k, 2), v) for k, v in children.items())
            )
        else:
            return '({0}:\n{1}\n{2})'.format(
                color(ast.name, 9),
                ',\n'.join(['{0}{1}={2}'.format(next_indent_str, color(k, 2), v) for k, v in children.items()]),
                indent_str
            )
    elif isinstance(ast, list):
        children = [ast_string(element, indent, color, b64_source, indent_level+1) for element in ast]
        if indent is None or len(children) == 0:
            return '[{0}]'.format(', '.join(children))
        else:
            return '[\n{1}\n{0}]'.format(
                indent_str,
                ',\n'.join(['{0}{1}'.format(next_indent_str, child) for child in children]),
            )
    elif isinstance(ast, Terminal):
        return color(ast.dumps(b64_source=b64_source), 6)

class Terminal:
  def __init__(self, id, str, source_string, resource, line, col):
    self.__dict__.update(locals())
  def getId(self):
    return self.id
  def toAst(self):
    return self
  def dumps(self, b64_source=False, **kwargs):
    source_string = base64.b64encode(self.source_string.encode('utf-8')).decode('utf-8') if b64_source else self.source_string
    return '<{} (line {} col {}) `{}`>'.format(self.str, self.line, self.col, source_string)
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
  def toAst(self):
      retval = []
      for ast in self:
          retval.append(ast.toAst())
      return retval
  def dumps(self, indent=None, color=no_color, b64_source=False):
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
  def add( self, tree ):
      self.children.append( tree )
  def toAst( self ):
      if self.list == 'slist' or self.list == 'nlist':
          if len(self.children) == 0:
              return AstList()
          offset = 1 if self.children[0] == self.listSeparator else 0
          first = self.children[offset].toAst()
          r = AstList()
          if first is not None:
              r.append(first)
          r.extend(self.children[offset+1].toAst())
          return r
      elif self.list == 'otlist':
          if len(self.children) == 0:
              return AstList()
          r = AstList()
          if self.children[0] != self.listSeparator:
              r.append(self.children[0].toAst())
          r.extend(self.children[1].toAst())
          return r
      elif self.list == 'tlist':
          if len(self.children) == 0:
              return AstList()
          r = AstList([self.children[0].toAst()])
          r.extend(self.children[2].toAst())
          return r
      elif self.list == 'mlist':
          r = AstList()
          if len(self.children) == 0:
              return r
          lastElement = len(self.children) - 1
          for i in range(lastElement):
              r.append(self.children[i].toAst())
          r.extend(self.children[lastElement].toAst())
          return r
      elif self.isExpr:
          if isinstance(self.astTransform, AstTransformSubstitution):
              return self.children[self.astTransform.idx].toAst()
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
                  parameters[name] = child.toAst()
              return Ast(self.astTransform.name, parameters)
      else:
          if isinstance(self.astTransform, AstTransformSubstitution):
              return self.children[self.astTransform.idx].toAst()
          elif isinstance(self.astTransform, AstTransformNodeCreator):
              parameters = OrderedDict()
              for name, idx in self.astTransform.parameters.items():
                  parameters[name] = self.children[idx].toAst()
              return Ast(self.astTransform.name, parameters)
          elif len(self.children):
              return self.children[0].toAst()
          else:
              return None

  def dumps(self, indent=None, color=no_color, b64_source=False):
      args = locals()
      del args['self']
      return parse_tree_string(self, **args)

class Ast():
    def __init__(self, name, attributes):
        self.__dict__.update(locals())
    def getAttr(self, attr):
        return self.attributes[attr]
    def dumps(self, indent=None, color=no_color, b64_source=False):
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
  def json(self):
    if len(self) == 0:
      return '[]'
    tokens_json = []
    json_fmt = '"terminal": "{terminal}", "resource": "{resource}", "line": {line}, "col": {col}, "source_string": "{source_string}"'
    for token in self:
        tokens_json.append(
            '{' +
            json_fmt.format(
              terminal=token.str,
              resource=token.resource,
              line=token.line,
              col=token.col,
              source_string=base64.b64encode(token.source_string.encode('utf-8')).decode('utf-8')
            ) +
            '}'
        )
    return '[\n    ' + ',\n    '.join(tokens_json) + '\n]'
  def current(self):
    try:
      return self[self.index]
    except IndexError:
      return None

class DefaultSyntaxErrorFormatter:
  def unexpected_eof(self, nonterminal, expected_terminals, nonterminal_rules):
    return "Error: unexpected end of file"
  def excess_tokens(self, nonterminal, terminal):
    return "Finished parsing without consuming all tokens."
  def unexpected_symbol(self, nonterminal, actual_terminal, expected_terminals, rule):
    return "Unexpected symbol (line {line}, col {col}) when parsing parse_{nt}.  Expected {expected}, got {actual}.".format(
      line=actual_terminal.line,
      col=actual_terminal.col,
      nt=nonterminal,
      expected=', '.join(expected_terminals),
      actual=actual_terminal
    )
  def no_more_tokens(self, nonterminal, expected_terminal, last_terminal):
    return "No more tokens.  Expecting " + expected_terminal
  def invalid_terminal(nonterminal, invalid_terminal):
    return "Invalid symbol ID: {} ({})".format(invalid_terminal.id, invalid_terminal.string)

class ParserContext:
  def __init__(self, tokens, error_formatter):
    self.__dict__.update(locals())
    self.nonterminal_string = None
    self.rule_string = None

###############
# Parser Code #
###############

parser_terminals = {
{% for terminal in grammar.standard_terminals %}
    {{terminal.id}}: '{{terminal.string}}',
{% endfor %}

{% for terminal in grammar.standard_terminals %}
    '{{terminal.string.lower()}}': {{terminal.id}},
{% endfor %}
}

# table[nonterminal][terminal] = rule
table = [
{% py parse_table = grammar.parse_table %}
{% for i in range(len(grammar.nonterminals)) %}
    [{{', '.join([str(rule.id) if rule else str(-1) for rule in parse_table[i]])}}],
{% endfor %}
]

nonterminal_first = {
{% for nonterminal in grammar.nonterminals %}
    {{nonterminal.id}}: [{{', '.join([str(t.id) for t in grammar.first(nonterminal)])}}],
{% endfor %}
}

nonterminal_follow = {
{% for nonterminal in grammar.nonterminals %}
    {{nonterminal.id}}: [{{', '.join([str(t.id) for t in grammar.follow(nonterminal)])}}],
{% endfor %}
}

rule_first = {
{% for rule in grammar.get_expanded_rules() %}
    {{rule.id}}: [{{', '.join([str(t.id) for t in grammar.first(rule.production)])}}],
{% endfor %}
}

nonterminal_rules = {
{% for nonterminal in grammar.nonterminals %}
    {{nonterminal.id}}: [
  {% for rule in grammar.get_expanded_rules() %}
    {% if rule.nonterminal.id == nonterminal.id %}
        "{{rule}}",
    {% endif %}
  {% endfor %}
    ],
{% endfor %}
}

rules = {
{% for rule in grammar.get_expanded_rules() %}
    {{rule.id}}: "{{rule}}",
{% endfor %}
}

def is_terminal(id): return isinstance(id, int) and 0 <= id <= {{len(grammar.standard_terminals) - 1}}

def parse(tokens, error_formatter=None, start=None):
    if isinstance(tokens, str):
        tokens = lex(tokens, '<string>')
    if error_formatter is None:
        error_formatter = DefaultSyntaxErrorFormatter()
    ctx = ParserContext(tokens, error_formatter)
    tree = parse_{{grammar.start.string.lower()}}(ctx)
    if tokens.current() != None:
        raise SyntaxError('Finished parsing without consuming all tokens.')
    return tree

def expect(ctx, terminal_id):
    current = ctx.tokens.current()
    if not current:
        raise SyntaxError(ctx.error_formatter.no_more_tokens(ctx.nonterminal, parser_terminals[terminal_id], ctx.tokens.last()))
    if current.id != terminal_id:
        raise SyntaxError(ctx.error_formatter.unexpected_symbol(ctx.nonterminal, current, [parser_terminals[terminal_id]], ctx.rule))
    next = ctx.tokens.advance()
    if next and not is_terminal(next.id):
        raise SyntaxError(ctx.error_formatter.invalid_terminal(ctx.nonterminal, next))
    return current

{% for expression_nonterminal in grammar.expression_nonterminals %}
    {% py name = expression_nonterminal.string %}

# START definitions for expression parser `{{name}}`
infix_binding_power_{{name}} = {
    {% for rule in grammar.get_rules(expression_nonterminal) %}
        {% if rule.operator and rule.operator.associativity in ['left', 'right'] %}
    {{rule.operator.operator.id}}: {{rule.operator.binding_power}}, # {{rule}}
        {% endif %}
    {% endfor %}
}

prefix_binding_power_{{name}} = {
    {% for rule in grammar.get_rules(expression_nonterminal) %}
        {% if rule.operator and rule.operator.associativity in ['unary'] %}
    {{rule.operator.operator.id}}: {{rule.operator.binding_power}}, # {{rule}}
        {% endif %}
    {% endfor %}
}

def get_infix_binding_power_{{name}}(terminal_id):
    try:
        return infix_binding_power_{{name}}[terminal_id]
    except:
        return 0

def get_prefix_binding_power_{{name}}(terminal_id):
    try:
        return prefix_binding_power_{{name}}[terminal_id]
    except:
        return 0

def parse_{{name}}(ctx):
    return parse_{{name}}_internal(ctx, rbp=0)

def parse_{{name}}_internal(ctx, rbp=0):
    left = nud_{{name}}(ctx)
    if isinstance(left, ParseTree):
        left.isExpr = True
        left.isNud = True
    while ctx.tokens.current() and rbp < get_infix_binding_power_{{name}}(ctx.tokens.current().id):
        left = led_{{name}}(left, ctx)
    if left:
        left.isExpr = True
    return left

def nud_{{name}}(ctx):
    tree = ParseTree(NonTerminal({{expression_nonterminal.id}}, '{{name}}'))
    current = ctx.tokens.current()
    ctx.nonterminal = "{{name}}"

    if not current:
        return tree

    {% for i, rule in enumerate(grammar.get_expanded_rules(expression_nonterminal)) %}
      {% py first_set = grammar.first(rule.production) %}
      {% if len(first_set) and not first_set.issuperset(grammar.first(expression_nonterminal)) %}
    {{'if' if i == 0 else 'elif'}} current.id in rule_first[{{rule.id}}]:
        # {{rule}}
        ctx.rule = rules[{{rule.id}}]
        {% if isinstance(rule.nudAst, AstSpecification) %}
        ast_parameters = OrderedDict([
          {% for k,v in rule.nudAst.parameters.items() %}
            ('{{k}}', {% if v == '$' %}'{{v}}'{% else %}{{v}}{% endif %}),
          {% endfor %}
        ])
        tree.astTransform = AstTransformNodeCreator('{{rule.nudAst.name}}', ast_parameters)
        {% elif isinstance(rule.nudAst, AstTranslation) %}
        tree.astTransform = AstTransformSubstitution({{rule.nudAst.idx}})
        {% endif %}

        tree.nudMorphemeCount = {{len(rule.nud_production)}}

        {% for morpheme in rule.nud_production.morphemes %}
          {% if isinstance(morpheme, Terminal) %}
        tree.add(expect(ctx, {{morpheme.id}}))
          {% elif isinstance(morpheme, NonTerminal) and morpheme.string.upper() == rule.nonterminal.string.upper() %}
            {% if isinstance(rule.operator, PrefixOperator) %}
        tree.add(parse_{{name}}_internal(ctx, get_prefix_binding_power_{{name}}({{rule.operator.operator.id}})))
        tree.isPrefix = True
            {% else %}
        tree.add(parse_{{rule.nonterminal.string.lower()}}(ctx))
            {% endif %}
          {% elif isinstance(morpheme, NonTerminal) %}
        tree.add(parse_{{morpheme.string.lower()}}(ctx))
          {% endif %}
        {% endfor %}
      {% endif %}
    {% endfor %}

    return tree

def led_{{name}}(left, ctx):
    tree = ParseTree(NonTerminal({{expression_nonterminal.id}}, '{{name}}'))
    current = ctx.tokens.current()
    ctx.nonterminal = "{{name}}"

    {% for rule in grammar.get_expanded_rules(expression_nonterminal) %}
      {% py led = rule.ledProduction.morphemes %}
      {% if len(led) %}

    if current.id == {{led[0].id}}: # {{led[0]}}
        # {{rule}}
        ctx.rule = rules[{{rule.id}}]
        {% if isinstance(rule.ast, AstSpecification) %}
        ast_parameters = OrderedDict([
          {% for k,v in rule.ast.parameters.items() %}
            ('{{k}}', {% if v == '$' %}'{{v}}'{% else %}{{v}}{% endif %}),
          {% endfor %}
        ])
        tree.astTransform = AstTransformNodeCreator('{{rule.ast.name}}', ast_parameters)
        {% elif isinstance(rule.ast, AstTranslation) %}
        tree.astTransform = AstTransformSubstitution({{rule.ast.idx}})
        {% endif %}

        {% if len(rule.nud_production) == 1 and isinstance(rule.nud_production.morphemes[0], NonTerminal) %}
          {% py nt = rule.nud_production.morphemes[0] %}
          {% if nt == rule.nonterminal or (isinstance(nt.macro, OptionalMacro) and nt.macro.nonterminal == rule.nonterminal) %}
        tree.isExprNud = True
          {% endif %}
        {% endif %}

        tree.add(left)

        {% py associativity = {rule.operator.operator.id: rule.operator.associativity for rule in grammar.get_rules(expression_nonterminal) if rule.operator} %}
        {% for morpheme in led %}
          {% if isinstance(morpheme, Terminal) %}
        tree.add(expect(ctx, {{morpheme.id}})) # {{morpheme}}
          {% elif isinstance(morpheme, NonTerminal) and morpheme.string.upper() == rule.nonterminal.string.upper() %}
        modifier = {{1 if rule.operator.operator.id in associativity and associativity[rule.operator.operator.id] == 'right' else 0}}
            {% if isinstance(rule.operator, InfixOperator) %}
        tree.isInfix = True
            {% endif %}
        tree.add(parse_{{name}}_internal(ctx, get_infix_binding_power_{{name}}({{rule.operator.operator.id}}) - modifier))
          {% elif isinstance(morpheme, NonTerminal) %}
        tree.add(parse_{{morpheme.string.lower()}}(ctx))
          {% endif %}
        {% endfor %}
      {% endif %}
    {% endfor %}

    return tree

# END definitions for expression parser `{{name}}`
{% endfor %}

{% for nonterminal in grammar.ll1_nonterminals %}
  {% py name = nonterminal.string %}
def parse_{{name}}(ctx):
    current = ctx.tokens.current()
    rule = table[{{nonterminal.id - len(grammar.standard_terminals)}}][current.id] if current else -1
    tree = ParseTree(NonTerminal({{nonterminal.id}}, '{{name}}'))
    ctx.nonterminal = "{{name}}"

    {% if isinstance(nonterminal.macro, SeparatedListMacro) %}
    tree.list = 'slist'
    {% elif isinstance(nonterminal.macro, MorphemeListMacro) %}
    tree.list = 'nlist'
    {% elif isinstance(nonterminal.macro, TerminatedListMacro) %}
    tree.list = 'tlist'
    {% elif isinstance(nonterminal.macro, MinimumListMacro) %}
    tree.list = 'mlist'
    {% elif isinstance(nonterminal.macro, OptionallyTerminatedListMacro) %}
    tree.list = 'otlist'
    {% else %}
    tree.list = False
    {% endif %}

    {% if not grammar.must_consume_tokens(nonterminal) %}
    if current != None and current.id in nonterminal_follow[{{nonterminal.id}}] and current.id not in nonterminal_first[{{nonterminal.id}}]:
        return tree
    {% endif %}

    if current == None:
    {% if grammar.must_consume_tokens(nonterminal) %}
        raise SyntaxError('Error: unexpected end of file')
    {% else %}
        return tree
    {% endif %}

    {% for index, rule in enumerate([rule for rule in grammar.get_expanded_rules(nonterminal) if not rule.is_empty]) %}

      {% if index == 0 %}
    if rule == {{rule.id}}: # {{rule}}
      {% else %}
    elif rule == {{rule.id}}: # {{rule}}
      {% endif %}

        ctx.rule = rules[{{rule.id}}]

      {% if isinstance(rule.ast, AstTranslation) %}
        tree.astTransform = AstTransformSubstitution({{rule.ast.idx}})
      {% elif isinstance(rule.ast, AstSpecification) %}
        ast_parameters = OrderedDict([
        {% for k,v in rule.ast.parameters.items() %}
            ('{{k}}', {% if v == '$' %}'{{v}}'{% else %}{{v}}{% endif %}),
        {% endfor %}
        ])
        tree.astTransform = AstTransformNodeCreator('{{rule.ast.name}}', ast_parameters)
      {% else %}
        tree.astTransform = AstTransformSubstitution(0)
      {% endif %}

      {% for index, morpheme in enumerate(rule.production.morphemes) %}

        {% if isinstance(morpheme, Terminal) %}
        t = expect(ctx, {{morpheme.id}}) # {{morpheme}}
        tree.add(t)
          {% if isinstance(nonterminal.macro, SeparatedListMacro) or isinstance(nonterminal.macro, OptionallyTerminatedListMacro) %}
            {% if nonterminal.macro.separator == morpheme %}
        tree.listSeparator = t
            {% endif %}
          {% endif %}
        {% endif %}

        {% if isinstance(morpheme, NonTerminal) %}
        subtree = parse_{{morpheme.string.lower()}}(ctx)
        tree.add(subtree)
        {% endif %}

      {% endfor %}
        return tree
    {% endfor %}

    {% if grammar.must_consume_tokens(nonterminal) %}
    raise SyntaxError(ctx.error_formatter.unexpected_symbol(
      ctx.nonterminal,
      ctx.tokens.current(),
      [parser_terminals[x] for x in nonterminal_first[{{nonterminal.id}}]],
      rules[{{rule.id}}]
    ))
    {% else %}
    return tree
    {% endif %}

{% endfor %}

{% if lexer %}

##############
# Lexer Code #
##############

lexer_terminals = {
{% for terminal in lexer.terminals %}
    {{terminal.id}}: '{{terminal.string}}',
{% endfor %}

{% for terminal in lexer.terminals %}
    '{{terminal.string.lower()}}': {{terminal.id}},
{% endfor %}
}

# START USER CODE
{{lexer.code}}
# END USER CODE

{% if re.search(r'def\s+default_action', lexer.code) is None %}
def default_action(context, mode, match, terminal, resource, line, col):
    tokens = [Terminal(lexer_terminals[terminal], terminal, match, resource, line, col)] if terminal else []
    return (tokens, mode, context)
{% endif %}

{% if re.search(r'def\s+init', lexer.code) is None %}
def init():
    return {}
{% endif %}

{% if re.search(r'def\s+destroy', lexer.code) is None %}
def destroy(context):
    pass
{% endif %}

class HermesLexer:
    regex = {
      {% for mode, regex_list in lexer.items() %}
        '{{mode}}': [
          {% for regex in regex_list %}
          (re.compile({{regex.regex}}{{", "+' | '.join(['re.'+x for x in regex.options]) if regex.options else ''}}), {{"'" + regex.terminal.string.lower() + "'" if regex.terminal else 'None'}}, {{regex.function}}),
          {% endfor %}
        ],
      {% endfor %}
    }

    def _update_line_col(self, match, line, col):
        match_lines = match.split('\n')
        line += len(match_lines) - 1
        if len(match_lines) == 1:
            col += len(match_lines[0])
        else:
            col = len(match_lines[-1]) + 1
        return (line, col)

    def _unrecognized_token(self, string, line, col):
        lines = string.split('\n')
        bad_line = lines[line-1]
        message = 'Unrecognized token on line {}, column {}:\n\n{}\n{}'.format(
            line, col, bad_line, ''.join([' ' for x in range(col-1)]) + '^'
        )
        raise SyntaxError(message)

    def _next(self, string, mode, context, resource, line, col):
        for (regex, terminal, function) in self.regex[mode]:
            match = regex.match(string)
            if match:
                function = function if function else default_action
                (tokens, mode, context) = function(context, mode, match.group(0), terminal, resource, line, col)
                return (tokens, match.group(0), mode)
        return ([], '', mode)

    def lex(self, string, resource, debug=False):
        (mode, line, col) = ('default', 1, 1)
        context = init()
        string_copy = string
        parsed_tokens = []
        while len(string):
            (tokens, match, mode) = self._next(string, mode, context, resource, line, col)
            if len(match) == 0:
                self._unrecognized_token(string_copy, line, col)

            string = string[len(match):]

            if tokens is None:
                self._unrecognized_token(string_copy, line, col)

            parsed_tokens.extend(tokens)

            (line, col) = self._update_line_col(match, line, col)

            if debug:
                for token in tokens:
                    print('token --> [{}] [{}, {}] [{}] [{}] [{}]'.format(
                        colorize(token.str, ansi=9),
                        colorize(str(token.line), ansi=5),
                        colorize(str(token.col), ansi=5),
                        colorize(token.source_string, ansi=3),
                        colorize(mode, ansi=4),
                        colorize(str(context), ansi=13)
                    ))
        destroy(context)
        return parsed_tokens

def lex(source, resource, debug=False):
    return TokenStream(HermesLexer().lex(source, resource, debug))

{% endif %}

{% if add_main %}

########
# Main #
########

def cli():
    if len(sys.argv) != 3 or (sys.argv[1] not in ['parsetree', 'ast']{% if lexer %} and sys.argv[1] != 'tokens'{% endif %}):
        sys.stderr.write("Usage: Main.py <parsetree|ast> <tokens_file>\n")
        {% if lexer %}
        sys.stderr.write("Usage: Main.py <tokens> <source_file>\n")
        {% endif %}
        sys.exit(-1)

    if sys.argv[1] in ['parsetree', 'ast']:
        tokens = TokenStream()
        with open(os.path.expanduser(sys.argv[2])) as fp:
            json_tokens = json.loads(fp.read())
            for json_token in json_tokens:
                tokens.append(Terminal(
                    parser_terminals[json_token['terminal']],
                    json_token['terminal'],
                    json_token['source_string'],
                    json_token['resource'],
                    json_token['line'],
                    json_token['col']
                ))

        try:
            tree = parse(tokens)
            if sys.argv[1] == 'parsetree':
                print(tree.dumps(indent=2))
            else:
                ast = tree.toAst()
                print(ast.dumps(indent=2) if ast else ast)
        except SyntaxError as error:
            print(error)

    if sys.argv[1] == 'tokens':
        try:
            with open(sys.argv[2]) as fp:
                tokens = lex(fp.read(), os.path.basename(sys.argv[2]))
            print(tokens.json())
        except SyntaxError as error:
            sys.exit(error)

if __name__ == '__main__':
    cli()
{% endif %}
