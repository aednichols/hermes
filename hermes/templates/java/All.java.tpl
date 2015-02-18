{% if java_package %}
package {{java_package}};
{% endif %}

{% import re %}
{% from hermes.Grammar import AstTranslation, AstSpecification, ExprRule %}
{% from hermes.Grammar import PrefixOperator, InfixOperator %}
{% from hermes.Macro import SeparatedListMacro, MorphemeListMacro, TerminatedListMacro, MinimumListMacro, OptionalMacro, OptionallyTerminatedListMacro %}
{% from hermes.Morpheme import Terminal, NonTerminal %}

import java.util.*;
import java.io.IOException;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.util.Arrays;
import java.nio.*;
import java.nio.channels.FileChannel;
import java.nio.charset.Charset;
{% if lexer %}
import java.util.regex.Pattern;
import java.util.regex.Matcher;
import java.lang.reflect.Method;
{% endif %}

{% if add_main %}
import org.json.*;
{% endif %}

public class {{prefix}}Parser {

    private static Map<Integer, List<TerminalIdentifier>> nonterminal_first;
    private static Map<Integer, List<TerminalIdentifier>> nonterminal_follow;
    private static Map<Integer, List<TerminalIdentifier>> rule_first;
    private static Map<Integer, List<String>> nonterminal_rules;
    private static Map<Integer, String> rules;
    public static {{prefix}}TerminalMap terminal_map = new {{prefix}}TerminalMap({{prefix}}TerminalIdentifier.values());

    public static String join(Collection<?> s, String delimiter) {
        StringBuilder builder = new StringBuilder();
        Iterator iter = s.iterator();
        while (iter.hasNext()) {
            builder.append(iter.next());
            if (!iter.hasNext()) {
                break;
            }
            builder.append(delimiter);
        }
        return builder.toString();
    }

    public static String getIndentString(int spaces) {
        StringBuilder sb = new StringBuilder();
        for(int i = 0; i < spaces; i++) {
            sb.append(' ');
        }
        return sb.toString();
    }

    public static String base64_encode(byte[] bytes) {
        int b64_len = ((bytes.length + ( (bytes.length % 3 != 0) ? (3 - (bytes.length % 3)) : 0) ) / 3) * 4;
        int cycle = 0, b64_index = 0;
        byte[] alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/".getBytes();
        byte[] b64 = new byte[b64_len];
        byte[] buffer = new byte[3];
        Arrays.fill(buffer, (byte) -1);

        for (byte b : bytes) {
            int index = cycle % 3;
            buffer[index] = b;
            boolean last = (cycle == (bytes.length - 1));
            if ( index == 2 || last ) {
                if ( last ) {
                    if ( buffer[1] == -1 ) buffer[1] = 0;
                    if ( buffer[2] == -1 ) buffer[2] = 0;
                }

                b64[b64_index++] = alphabet[buffer[0] >> 2];
                b64[b64_index++] = alphabet[((buffer[0] & 0x3) << 4) | ((buffer[1] >> 4) & 0xf)];
                b64[b64_index++] = alphabet[((buffer[1] & 0xf) << 2) | ((buffer[2] >> 6) & 0x3)];
                b64[b64_index++] = alphabet[buffer[2] & 0x3f];

                if ( buffer[1] == 0 ) b64[b64_index - 2] = (byte) '=';
                if ( buffer[2] == 0 ) b64[b64_index - 1] = (byte) '=';

                Arrays.fill(buffer, (byte) -1);
            }
            cycle++;
        }
        return new String(b64);
    }

    public static String readStdin() throws IOException {
        InputStreamReader stream = new InputStreamReader(System.in, "utf-8");
        char buffer[] = new char[System.in.available()];
        try {
            stream.read(buffer, 0, System.in.available());
        } finally {
            stream.close();
        }
        return new String(buffer);
    }

    public static String readFile(String path) throws IOException {
        FileInputStream stream = new FileInputStream(new File(path));
        try {
            FileChannel fc = stream.getChannel();
            MappedByteBuffer bb = fc.map(FileChannel.MapMode.READ_ONLY, 0, fc.size());
            /* Instead of using default, pass in a decoder. */
            return Charset.defaultCharset().decode(bb).toString();
        }
        finally {
            stream.close();
        }
    }

    public static class SyntaxError extends Exception {
        public SyntaxError(String message) {
            super(message);
        }
    }

    public interface SyntaxErrorFormatter {
        /* Called when the parser runs out of tokens but isn't finished parsing. */
        String unexpected_eof(String method, List<TerminalIdentifier> expected, List<String> nt_rules);

        /* Called when the parser finished parsing but there are still tokens left in the stream. */
        String excess_tokens(String method, Terminal terminal);

        /* Called when the parser is expecting one token and gets another. */
        String unexpected_symbol(String method, Terminal actual, List<TerminalIdentifier> expected, String rule);

        /* Called when the parser is expecing a tokens but there are no more tokens. */
        String no_more_tokens(String method, TerminalIdentifier expecting, Terminal last);

        /* Invalid terminal is found in the token stream. */
        String invalid_terminal(String method, Terminal invalid);
    }

    public static class TokenStream extends ArrayList<Terminal> {
        private int index;

        public TokenStream(List<Terminal> terminals) {
            super(terminals);
            reset();
        }

        public TokenStream() {
            reset();
        }

        public void reset() {
            this.index = 0;
        }

        public Terminal advance() {
            this.index += 1;
            return this.current();
        }

        public Terminal current() {
            try {
                return this.get(this.index);
            } catch (IndexOutOfBoundsException e) {
                return null;
            }
        }

        public Terminal last() {
          return this.get(this.size() - 1);
        }
    }

    public static class NonTerminal {
        private int id;
        private String string;

        NonTerminal(int id, String string) {
            this.id = id;
            this.string = string;
        }

        public int getId() {
            return this.id;
        }

        public String getString() {
            return this.string;
        }

        public String toString() {
            return this.string;
        }
    }

    public interface AstTransform {}

    public static class AstTransformNodeCreator implements AstTransform {
        private String name;
        private LinkedHashMap<String, Integer> parameters;

        AstTransformNodeCreator(String name, LinkedHashMap<String, Integer> parameters) {
            this.name = name;
            this.parameters = parameters;
        }

        public Map<String, Integer> getParameters() {
            return this.parameters;
        }

        public String getName() {
            return this.name;
        }

        public String toString() {
            LinkedList<String> items = new LinkedList<String>();
            for (final Map.Entry<String, Integer> entry : this.parameters.entrySet()) {
                items.add(entry.getKey() + "=$" + entry.getValue().toString());
            }
            return "AstNodeCreator: " + this.name + "( " + join(items, ", ") + " )";
        }
    }

    public static class AstTransformSubstitution implements AstTransform {
        private int index;

        AstTransformSubstitution(int index) {
            this.index = index;
        }

        public int getIndex() {
            return this.index;
        }

        public String toString() {
            return "AstSubstitution: $" + Integer.toString(this.index);
        }
    }

    public interface AstNode {
        public String toString();
        public String toPrettyString();
        public String toPrettyString(int indent);
    }

    public static class AstList extends ArrayList<AstNode> implements AstNode {
        public String toString() {
            return "[" + join(this, ", ") + "]";
        }

        public String toPrettyString() {
            return toPrettyString(0);
        }

        public String toPrettyString(int indent) {
            String spaces = getIndentString(indent);
            if (this.size() == 0) {
                return spaces + "[]";
            }

            ArrayList<String> elements = new ArrayList<String>();
            for ( AstNode node : this ) {
                elements.add(node.toPrettyString(indent + 2));
            }

            return spaces + "[\n" + join(elements, ",\n") + "\n" + spaces + "]";
        }
    }

    public static class Ast implements AstNode {
        private String name;
        private Map<String, AstNode> attributes;

        Ast(String name, Map<String, AstNode> attributes) {
            this.name = name;
            this.attributes = attributes;
        }

        public AstNode getAttribute(String name) {
            return this.attributes.get(name);
        }

        public Map<String, AstNode> getAttributes() {
            return this.attributes;
        }

        public String getName() {
            return this.name;
        }

        public String toString() {
            Formatter formatter = new Formatter(new StringBuilder(), Locale.US);

            LinkedList<String> attributes = new LinkedList<String>();
            for (final Map.Entry<String, AstNode> attribute : this.attributes.entrySet()) {
                final String name = attribute.getKey();
                final AstNode node = attribute.getValue();
                final String nodeStr = (node == null) ? "None" : node.toString();
                attributes.add(name + "=" + nodeStr);
            }

            formatter.format("(%s: %s)", this.name, join(attributes, ", "));
            return formatter.toString();
        }

        public String toPrettyString() {
            return toPrettyString(0);
        }

        public String toPrettyString(int indent) {
            String spaces = getIndentString(indent);

            ArrayList<String> children = new ArrayList<String>();
            for( Map.Entry<String, AstNode> attribute : this.attributes.entrySet() ) {
                String valueString = attribute.getValue() == null ? "None" : attribute.getValue().toPrettyString(indent + 2).trim();
                children.add(spaces + "  " + attribute.getKey() + "=" + valueString);
            }

            return spaces + "(" + this.name + ":\n" + join(children, ",\n") + "\n" + spaces + ")";
        }
    }

    public interface ParseTreeNode {
        public AstNode toAst();
        public String toString();
        public String toPrettyString();
        public String toPrettyString(int indent);
    }

    public static class Terminal implements AstNode, ParseTreeNode
    {
        private int id;
        private String terminal_str;
        private String source_string;
        private String resource;
        private int line;
        private int col;

        public Terminal(int id, String terminal_str, String source_string, String resource, int line, int col) {
            this.id = id;
            this.terminal_str = terminal_str;
            this.source_string = source_string;
            this.resource = resource;
            this.line = line;
            this.col = col;
        }

        public int getId() {
            return this.id;
        }

        public String getTerminalStr() {
            return this.terminal_str;
        }

        public String getSourceString() {
            return this.source_string;
        }

        public String getResource() {
            return this.resource;
        }

        public int getLine() {
            return this.line;
        }

        public int getColumn() {
            return this.col;
        }

        public String toString() {
            StringBuilder sb = new StringBuilder();
            Formatter formatter = new Formatter(sb, Locale.US);
            formatter.format("{\"terminal\": \"%s\", \"resource\": \"%s\", \"line\": %d, \"col\": %d, \"source_string\": \"%s\"}", this.getTerminalStr(), this.getResource(), this.getLine(), this.getColumn(), base64_encode(this.getSourceString().getBytes()));
            return formatter.toString();
        }

        public String toPrettyString() {
            return toPrettyString(0);
        }

        public String toPrettyString(int indent) {
            String spaces = getIndentString(indent);
            // <b (line 0 col 0) ``>
            return String.format("%s<%s (line %d col %d) `%s`>", spaces, this.getTerminalStr(), this.getLine(), this.getColumn(), this.getSourceString());
        }

        public AstNode toAst() { return this; }
    }

    public static class ParseTree implements ParseTreeNode {
        private NonTerminal nonterminal;
        private ArrayList<ParseTreeNode> children;

        private boolean isExpr, isNud, isPrefix, isInfix, isExprNud;
        private int nudMorphemeCount;
        private Terminal listSeparator;
        private String list;
        private AstTransform astTransform;

        ParseTree(NonTerminal nonterminal) {
            this.nonterminal = nonterminal;
            this.children = new ArrayList<ParseTreeNode>();
            this.astTransform = null;
            this.isExpr = false;
            this.isNud = false;
            this.isPrefix = false;
            this.isInfix = false;
            this.isExprNud = false;
            this.nudMorphemeCount = 0;
            this.listSeparator = null;
            this.list = "";
        }

        public void setExpr(boolean value) { this.isExpr = value; }
        public void setNud(boolean value) { this.isNud = value; }
        public void setPrefix(boolean value) { this.isPrefix = value; }
        public void setInfix(boolean value) { this.isInfix = value; }
        public void setExprNud(boolean value) { this.isExprNud = value; }
        public void setAstTransformation(AstTransform value) { this.astTransform = value; }
        public void setNudMorphemeCount(int value) { this.nudMorphemeCount = value; }
        public void setList(String value) { this.list = value; }
        public void setListSeparator(Terminal value) { this.listSeparator = value; }

        public int getNudMorphemeCount() { return this.nudMorphemeCount; }
        public List<ParseTreeNode> getChildren() { return this.children; }
        public boolean isInfix() { return this.isInfix; }
        public boolean isPrefix() { return this.isPrefix; }
        public boolean isExpr() { return this.isExpr; }
        public boolean isNud() { return this.isNud; }
        public boolean isExprNud() { return this.isExprNud; }

        public void add(ParseTreeNode tree) {
            if (this.children == null) {
                this.children = new ArrayList<ParseTreeNode>();
            }
            this.children.add(tree);
        }

        private boolean isCompoundNud() {
            if ( this.children.size() > 0 && this.children.get(0) instanceof ParseTree ) {
                ParseTree child = (ParseTree) this.children.get(0);

                if ( child.isNud() && !child.isPrefix() && !this.isExprNud() && !this.isInfix() ) {
                    return true;
                }
            }
            return false;
        }

        public AstNode toAst() {
            if ( this.list == "slist" || this.list == "nlist" ) {
                int offset = (this.children.size() > 0 && this.children.get(0) == this.listSeparator) ? 1 : 0;
                AstList astList = new AstList();
                if ( this.children.size() == 0 ) {
                    return astList;
                }
                AstNode first = this.children.get(offset).toAst();
                if ( first != null ) {
                    astList.add(this.children.get(offset).toAst());
                }
                astList.addAll((AstList) this.children.get(offset + 1).toAst());
                return astList;
            } else if ( this.list == "otlist" ) {
                AstList astList = new AstList();
                if ( this.children.size() == 0 ) {
                    return astList;
                }
                if (this.children.get(0) != this.listSeparator) {
                    astList.add(this.children.get(0).toAst());
                }
                astList.addAll((AstList) this.children.get(1).toAst());
                return astList;
            } else if ( this.list == "tlist" ) {
                AstList astList = new AstList();
                if ( this.children.size() == 0 ) {
                    return astList;
                }
                astList.add(this.children.get(0).toAst());
                astList.addAll((AstList) this.children.get(2).toAst());
                return astList;
            } else if ( this.list == "mlist" ) {
                AstList astList = new AstList();
                int lastElement = this.children.size() - 1;

                if ( this.children.size() == 0 ) {
                    return astList;
                }

                for (int i = 0; i < lastElement; i++) {
                    astList.add(this.children.get(i).toAst());
                }

                astList.addAll((AstList) this.children.get(this.children.size() - 1).toAst());
                return astList;
            } else if ( this.isExpr ) {
                if ( this.astTransform instanceof AstTransformSubstitution ) {
                    AstTransformSubstitution astSubstitution = (AstTransformSubstitution) astTransform;
                    return this.children.get(astSubstitution.getIndex()).toAst();
                } else if ( this.astTransform instanceof AstTransformNodeCreator ) {
                    AstTransformNodeCreator astNodeCreator = (AstTransformNodeCreator) this.astTransform;
                    LinkedHashMap<String, AstNode> parameters = new LinkedHashMap<String, AstNode>();
                    ParseTreeNode child;
                    for ( final Map.Entry<String, Integer> parameter : astNodeCreator.getParameters().entrySet() ) {
                        String name = parameter.getKey();
                        int index = parameter.getValue().intValue();

                        if ( index == '$' ) {
                            child = this.children.get(0);
                        } else if ( this.isCompoundNud() ) {
                            ParseTree firstChild = (ParseTree) this.children.get(0);

                            if ( index < firstChild.getNudMorphemeCount() ) {
                                child = firstChild.getChildren().get(index);
                            } else {
                                index = index - firstChild.getNudMorphemeCount() + 1;
                                child = this.children.get(index);
                            }
                        } else if ( this.children.size() == 1 && !(this.children.get(0) instanceof ParseTree) && !(this.children.get(0) instanceof List) ) {
                            // TODO: I don't think this should ever be called
                            child = this.children.get(0);
                        } else {
                            child = this.children.get(index);
                        }
                        parameters.put(name, child.toAst());
                    }
                    return new Ast(astNodeCreator.getName(), parameters);
                }
            } else {
                AstTransformSubstitution defaultAction = new AstTransformSubstitution(0);
                AstTransform action = this.astTransform != null ? this.astTransform : defaultAction;

                if (this.children.size() == 0) return null;

                if (action instanceof AstTransformSubstitution) {
                    AstTransformSubstitution astSubstitution = (AstTransformSubstitution) action;
                    return this.children.get(astSubstitution.getIndex()).toAst();
                } else if (action instanceof AstTransformNodeCreator) {
                    AstTransformNodeCreator astNodeCreator = (AstTransformNodeCreator) action;
                    LinkedHashMap<String, AstNode> evaluatedParameters = new LinkedHashMap<String, AstNode>();
                    for ( Map.Entry<String, Integer> baseParameter : astNodeCreator.getParameters().entrySet() ) {
                        String name = baseParameter.getKey();
                        int index2 = baseParameter.getValue().intValue();
                        evaluatedParameters.put(name, this.children.get(index2).toAst());
                    }
                    return new Ast(astNodeCreator.getName(), evaluatedParameters);
                }
            }
            return null;
        }

        public String toString() {
          ArrayList<String> children = new ArrayList<String>();
          for (ParseTreeNode child : this.children) {
            children.add(child.toString());
          }
          return "(" + this.nonterminal.getString() + ": " + join(children, ", ") + ")";
        }

        public String toPrettyString() {
          return toPrettyString(0);
        }

        public String toPrettyString(int indent) {

          if (this.children.size() == 0) {
            return "(" + this.nonterminal.toString() + ": )";
          }

          String spaces = getIndentString(indent);

          ArrayList<String> children = new ArrayList<String>();
          for ( ParseTreeNode node : this.children ) {
            String sub = node.toPrettyString(indent + 2).trim();
            children.add(spaces + "  " +  sub);
          }

          return spaces + "(" + this.nonterminal.toString() + ":\n" + join(children, ",\n") + "\n" + spaces + ")";
        }
    }

    private static class ParserContext {
        public TokenStream tokens;
        public SyntaxErrorFormatter error_formatter;
        public String nonterminal;
        public String rule;

        public ParserContext(TokenStream tokens, SyntaxErrorFormatter error_formatter) {
            this.tokens = tokens;
            this.error_formatter = error_formatter;
        }
    }

    private static class DefaultSyntaxErrorFormatter implements SyntaxErrorFormatter {
        public String unexpected_eof(String method, List<TerminalIdentifier> expected, List<String> nt_rules) {
            return "Error: unexpected end of file";
        }

        public String excess_tokens(String method, Terminal terminal) {
            return "Finished parsing without consuming all tokens.";
        }

        public String unexpected_symbol(String method, Terminal actual, List<TerminalIdentifier> expected, String rule) {
            ArrayList<String> expected_terminals = new ArrayList<String>();
            for ( TerminalIdentifier e : expected ) {
                expected_terminals.add(e.string());
            }
            return String.format(
                "Unexpected symbol (line %d, col %d) when parsing parse_%s.  Expected %s, got %s.",
                actual.getLine(), actual.getColumn(), method, join(expected_terminals, ", "), actual.toPrettyString()
            );
        }

        public String no_more_tokens(String method, TerminalIdentifier expecting, Terminal last) {
            return "No more tokens.  Expecting " + expecting.string();
        }

        public String invalid_terminal(String method, Terminal invalid) {
            return "Invalid symbol ID: "+invalid.getId()+" ("+invalid.getTerminalStr()+")";
        }
    }

    public interface TerminalMap {
        TerminalIdentifier get(String string);
        TerminalIdentifier get(int id);
        boolean isValid(String string);
        boolean isValid(int id);
    }

    public static class {{prefix}}TerminalMap implements TerminalMap {
        private Map<Integer, TerminalIdentifier> id_to_term;
        private Map<String, TerminalIdentifier> str_to_term;

        {{prefix}}TerminalMap({{prefix}}TerminalIdentifier[] terminals) {
            id_to_term = new HashMap<Integer, TerminalIdentifier>();
            str_to_term = new HashMap<String, TerminalIdentifier>();
            for( {{prefix}}TerminalIdentifier terminal : terminals ) {
                Integer id = new Integer(terminal.id());
                String str = terminal.string();
                id_to_term.put(id, terminal);
                str_to_term.put(str, terminal);
            }
        }

        public TerminalIdentifier get(String string) { return this.str_to_term.get(string); }
        public TerminalIdentifier get(int id) { return this.id_to_term.get(id); }
        public boolean isValid(String string) { return this.str_to_term.containsKey(string); }
        public boolean isValid(int id) { return this.id_to_term.containsKey(id); }
    }

    public interface TerminalIdentifier {
        public int id();
        public String string();
    }

    public enum {{prefix}}TerminalIdentifier implements TerminalIdentifier {
{% for index, terminal in enumerate(grammar.standard_terminals) %}
        TERMINAL_{{terminal.string.upper()}}({{terminal.id}}, "{{terminal.string}}"),
{% endfor %}
        END_SENTINAL(-3, "END_SENTINAL");

        private final int id;
        private final String string;

        {{prefix}}TerminalIdentifier(int id, String string) {
            this.id = id;
            this.string = string;
        }

        public int id() {return id;}
        public String string() {return string;}
    }

    /* table[nonterminal][terminal] = rule */
    private static final int[][] table = {
{% py parse_table = grammar.parse_table %}
{% for i in range(len(grammar.nonterminals)) %}
        { {{', '.join([str(rule.id) if rule else str(-1) for rule in parse_table[i]])}} },
{% endfor %}
    };

    static {
        Map<Integer, List<TerminalIdentifier>> map = new HashMap<Integer, List<TerminalIdentifier>>();
{% for nonterminal in grammar.nonterminals %}
        map.put({{nonterminal.id}}, Arrays.asList(new TerminalIdentifier[] {
  {% for terminal in grammar.first(nonterminal) %}
    {% if terminal in grammar.standard_terminals %}
            {{prefix}}TerminalIdentifier.TERMINAL_{{terminal.string.upper()}},
    {% endif %}
  {% endfor %}
        }));
{% endfor %}
        nonterminal_first = Collections.unmodifiableMap(map);
    }

    static {
        Map<Integer, List<TerminalIdentifier>> map = new HashMap<Integer, List<TerminalIdentifier>>();
{% for nonterminal in grammar.nonterminals %}
        map.put({{nonterminal.id}}, Arrays.asList(new TerminalIdentifier[] {
  {% for terminal in grammar.follow(nonterminal) %}
    {% if terminal in grammar.standard_terminals %}
            {{prefix}}TerminalIdentifier.TERMINAL_{{terminal.string.upper()}},
    {% endif %}
  {% endfor %}
        }));
{% endfor %}
        nonterminal_follow = Collections.unmodifiableMap(map);
    }

    static {
        Map<Integer, List<TerminalIdentifier>> map = new HashMap<Integer, List<TerminalIdentifier>>();
{% for rule in grammar.get_expanded_rules() %}
        map.put({{rule.id}}, Arrays.asList(new TerminalIdentifier[] {
  {% for terminal in grammar.first(rule.production) %}
    {% if terminal in grammar.standard_terminals %}
            {{prefix}}TerminalIdentifier.TERMINAL_{{terminal.string.upper()}},
    {% endif %}
  {% endfor %}
        }));
{% endfor %}
        rule_first = Collections.unmodifiableMap(map);
    }

    static {
        Map<Integer, List<String>> map = new HashMap<Integer, List<String>>();
{% for nonterminal in grammar.nonterminals %}
        map.put({{nonterminal.id}}, new ArrayList<String>());
{% endfor %}
{% for rule in grammar.get_expanded_rules() %}
        map.get({{rule.nonterminal.id}}).add("{{rule}}");
{% endfor %}
        nonterminal_rules = Collections.unmodifiableMap(map);
    }

    static {
        Map<Integer, String> map = new HashMap<Integer, String>();
{% for rule in grammar.get_expanded_rules() %}
        map.put(new Integer({{rule.id}}), "{{rule}}");
{% endfor %}
        rules = Collections.unmodifiableMap(map);
    }

    public static boolean is_terminal(int id) {
        return 0 <= id && id <= {{len(grammar.standard_terminals) - 1}};
    }

    public ParseTree parse(TokenStream tokens) throws SyntaxError {
        return parse(tokens, new DefaultSyntaxErrorFormatter());
    }

    public ParseTree parse(TokenStream tokens, SyntaxErrorFormatter error_formatter) throws SyntaxError {
        ParserContext ctx = new ParserContext(tokens, error_formatter);
        ParseTree tree = parse_{{grammar.start.string.lower()}}(ctx);
        if (ctx.tokens.current() != null) {
            StackTraceElement[] stack = Thread.currentThread().getStackTrace();
            throw new SyntaxError(ctx.error_formatter.excess_tokens(stack[1].getMethodName(), ctx.tokens.current()));
        }
        return tree;
    }

    private static Terminal expect(ParserContext ctx, TerminalIdentifier expecting) throws SyntaxError {
        Terminal current = ctx.tokens.current();
        if (current == null) {
            throw new SyntaxError(ctx.error_formatter.no_more_tokens(ctx.nonterminal, expecting, ctx.tokens.last()));
        }
        if (current.getId() != expecting.id()) {
            ArrayList<TerminalIdentifier> expectedList = new ArrayList<TerminalIdentifier>();
            expectedList.add(expecting);
            throw new SyntaxError(ctx.error_formatter.unexpected_symbol(ctx.nonterminal, current, expectedList, ctx.rule));
        }
        Terminal next = ctx.tokens.advance();
        if ( next != null && !is_terminal(next.getId()) ) {
            throw new SyntaxError(ctx.error_formatter.invalid_terminal(ctx.nonterminal, next));
        }
        return current;
    }

{% for expression_nonterminal in grammar.expression_nonterminals %}
  {% py name = expression_nonterminal.string %}
    private static Map<Integer, Integer> infix_binding_power_{{name}};
    private static Map<Integer, Integer> prefix_binding_power_{{name}};

    static {
        Map<Integer, Integer> map = new HashMap<Integer, Integer>();
  {% for rule in grammar.get_rules(expression_nonterminal) %}
    {% if rule.operator and rule.operator.associativity in ['left', 'right'] %}
        map.put({{rule.operator.operator.id}}, {{rule.operator.binding_power}}); /* {{rule}} */
    {% endif %}
  {% endfor %}
        infix_binding_power_{{name}} = Collections.unmodifiableMap(map);
    }

    static {
        Map<Integer, Integer> map = new HashMap<Integer, Integer>();
  {% for rule in grammar.get_rules(expression_nonterminal) %}
    {% if rule.operator and rule.operator.associativity in ['unary'] %}
        map.put({{rule.operator.operator.id}}, {{rule.operator.binding_power}}); /* {{rule}} */
    {% endif %}
  {% endfor %}
        prefix_binding_power_{{name}} = Collections.unmodifiableMap(map);
    }

    static int get_infix_binding_power_{{name}}(int terminal_id) {
        if (infix_binding_power_{{name}}.containsKey(terminal_id)) {
            return infix_binding_power_{{name}}.get(terminal_id);
        }
        return 0;
    }

    static int get_prefix_binding_power_{{name}}(int terminal_id) {
        if (prefix_binding_power_{{name}}.containsKey(terminal_id)) {
            return prefix_binding_power_{{name}}.get(terminal_id);
        }
        return 0;
    }

    public static ParseTree parse_{{name}}(ParserContext ctx) throws SyntaxError {
        return parse_{{name}}_internal(ctx, 0);
    }

    public static ParseTree parse_{{name}}_internal(ParserContext ctx, int rbp) throws SyntaxError {
        ParseTree left = nud_{{name}}(ctx);
        if ( left instanceof ParseTree ) {
            left.setExpr(true);
            left.setNud(true);
        }
        while (ctx.tokens.current() != null && rbp < get_infix_binding_power_{{name}}(ctx.tokens.current().getId())) {
            left = led_{{name}}(left, ctx);
        }
        if (left != null) {
            left.setExpr(true);
        }
        return left;
    }

    private static ParseTree nud_{{name}}(ParserContext ctx) throws SyntaxError {
        ParseTree tree = new ParseTree( new NonTerminal({{expression_nonterminal.id}}, "{{name}}") );
        Terminal current = ctx.tokens.current();
        ctx.nonterminal = "{{name}}";

        if (current == null) {
            return tree;
        }

  {% for i, rule in enumerate(grammar.get_expanded_rules(expression_nonterminal)) %}
    {% py ruleFirstSet = grammar.first(rule.production) %}

    {% if len(ruleFirstSet) and not ruleFirstSet.issuperset(grammar.first(expression_nonterminal))%}
        {{'if' if i == 0 else 'else if'}} (rule_first.get({{rule.id}}).contains(terminal_map.get(current.getId()))) {

      {% py ast = rule.nudAst if rule.nudAst else rule.ast %}
            /* ({{rule.id}}) {{rule}} */
            ctx.rule = rules.get({{rule.id}});

      {% if isinstance(ast, AstSpecification) %}
            LinkedHashMap<String, Integer> parameters = new LinkedHashMap<String, Integer>();
        {% for key, value in ast.parameters.items() %}
            parameters.put("{{key}}", {{"(int) '$'" if value == '$' else value}});
        {% endfor %}
            tree.setAstTransformation(new AstTransformNodeCreator("{{ast.name}}", parameters));
      {% elif isinstance(ast, AstTranslation) %}
            tree.setAstTransformation(new AstTransformSubstitution({{ast.idx}}));
      {% endif %}

            tree.setNudMorphemeCount({{len(rule.nud_production)}});

      {% for morpheme in rule.nud_production.morphemes %}
        {% if isinstance(morpheme, Terminal) %}
            tree.add(expect(ctx, {{prefix}}TerminalIdentifier.TERMINAL_{{morpheme.string.upper()}}));
        {% elif isinstance(morpheme, NonTerminal) and morpheme.string.upper() == rule.nonterminal.string.upper() %}
          {% if isinstance(rule.operator, PrefixOperator) %}
            tree.add(parse_{{name}}_internal(ctx, get_prefix_binding_power_{{name}}({{rule.operator.operator.id}})));
            tree.setPrefix(true);
          {% else %}
            tree.add(parse_{{rule.nonterminal.string.lower()}}(ctx));
          {% endif %}
        {% elif isinstance(morpheme, NonTerminal) %}
            tree.add(parse_{{morpheme.string.lower()}}(ctx));
        {% endif %}
      {% endfor %}
        }
    {% endif %}
  {% endfor %}

        return tree;
    }

    private static ParseTree led_{{name}}(ParseTree left, ParserContext ctx) throws SyntaxError {
        ParseTree tree = new ParseTree( new NonTerminal({{expression_nonterminal.id}}, "{{name}}") );
        Terminal current = ctx.tokens.current();
        ctx.nonterminal = "{{name}}";
        int modifier;

  {% for rule in grammar.get_expanded_rules(expression_nonterminal) %}
    {% py led = rule.ledProduction.morphemes %}
    {% if len(led) %}

        if (current.getId() == {{led[0].id}}) {
            /* {{rule}} */
            ctx.rule = rules.get({{rule.id}});

      {% if isinstance(rule.ast, AstSpecification) %}
            LinkedHashMap<String, Integer> parameters = new LinkedHashMap<String, Integer>();
        {% for key, value in rule.ast.parameters.items() %}
            parameters.put("{{key}}", {{"(int) '$'" if value == '$' else value}});
        {% endfor %}
            tree.setAstTransformation(new AstTransformNodeCreator("{{rule.ast.name}}", parameters));
      {% elif isinstance(rule.ast, AstTranslation) %}
            tree.setAstTransformation(new AstTransformSubstitution({{rule.ast.idx}}));
      {% endif %}

      {% if len(rule.nud_production) == 1 and isinstance(rule.nud_production.morphemes[0], NonTerminal) %}
        {% py nt = rule.nud_production.morphemes[0] %}
        {% if nt == rule.nonterminal or (isinstance(nt.macro, OptionalMacro) and nt.macro.nonterminal == rule.nonterminal) %}
            tree.setExprNud(true);
        {% endif %}
      {% endif %}

            tree.add(left);

      {% py associativity = {rule.operator.operator.id: rule.operator.associativity for rule in grammar.get_rules(expression_nonterminal) if rule.operator} %}
      {% for morpheme in led %}
        {% if isinstance(morpheme, Terminal) %}
            tree.add(expect(ctx, {{prefix}}TerminalIdentifier.TERMINAL_{{morpheme.string.upper()}}));
        {% elif isinstance(morpheme, NonTerminal) and morpheme.string.upper() == rule.nonterminal.string.upper() %}
            modifier = {{1 if rule.operator.operator.id in associativity and associativity[rule.operator.operator.id] == 'right' else 0}};
        {% if isinstance(rule.operator, InfixOperator) %}
            tree.setInfix(true);
        {% endif %}
            tree.add(parse_{{name}}_internal(ctx, get_infix_binding_power_{{name}}({{rule.operator.operator.id}}) - modifier));
        {% elif isinstance(morpheme, NonTerminal) %}
            tree.add(parse_{{morpheme.string.lower()}}(ctx));
        {% endif %}
      {% endfor %}
            return tree;
        }
        {% endif %}
      {% endfor %}

        return tree;
    }
{% endfor %}

{% for nonterminal in grammar.ll1_nonterminals %}
    private static ParseTree parse_{{nonterminal.string.lower()}}(ParserContext ctx) throws SyntaxError {
        Terminal current = ctx.tokens.current();
        Terminal next;
        ParseTree subtree;
        int rule = (current != null) ? table[{{nonterminal.id - len(grammar.standard_terminals)}}][current.getId()] : -1;
        ParseTree tree = new ParseTree( new NonTerminal({{nonterminal.id}}, "{{nonterminal.string}}"));
        ctx.nonterminal = "{{nonterminal.string.lower()}}";

  {% if isinstance(nonterminal.macro, SeparatedListMacro) %}
        tree.setList("slist");
  {% elif isinstance(nonterminal.macro, MorphemeListMacro) %}
        tree.setList("nlist");
  {% elif isinstance(nonterminal.macro, TerminatedListMacro) %}
        tree.setList("tlist");
  {% elif isinstance(nonterminal.macro, MinimumListMacro) %}
        tree.setList("mlist");
  {% elif isinstance(nonterminal.macro, OptionallyTerminatedListMacro) %}
        tree.setList("otlist");
  {% else %}
        tree.setList(null);
  {% endif %}

  {% if not grammar.must_consume_tokens(nonterminal) %}
        if ( current != null &&
             !nonterminal_first.get({{nonterminal.id}}).contains(terminal_map.get(current.getId())) &&
              nonterminal_follow.get({{nonterminal.id}}).contains(terminal_map.get(current.getId())) ) {
            return tree;
        }
  {% endif %}

        if (current == null) {
  {% if grammar.must_consume_tokens(nonterminal) %}
            throw new SyntaxError(ctx.error_formatter.unexpected_eof(
                "{{nonterminal.string.lower()}}",
                nonterminal_first.get({{nonterminal.id}}),
                nonterminal_rules.get({{nonterminal.id}})
            ));
  {% else %}
            return tree;
  {% endif %}
        }

  {% for index, rule in enumerate([rule for rule in grammar.get_expanded_rules(nonterminal) if not rule.is_empty]) %}
    {% if index == 0 %}
        if (rule == {{rule.id}}) {
    {% else %}
        else if (rule == {{rule.id}}) {
    {% endif %}
            /* {{rule}} */
            ctx.rule = rules.get({{rule.id}});

    {% if isinstance(rule.ast, AstTranslation) %}
            tree.setAstTransformation(new AstTransformSubstitution({{rule.ast.idx}}));
    {% elif isinstance(rule.ast, AstSpecification) %}
            LinkedHashMap<String, Integer> parameters = new LinkedHashMap<String, Integer>();
      {% for key, value in rule.ast.parameters.items() %}
            parameters.put("{{key}}", {{"(int) '$'" if value == '$' else value}});
      {% endfor %}
            tree.setAstTransformation(new AstTransformNodeCreator("{{rule.ast.name}}", parameters));
    {% else %}
            tree.setAstTransformation(new AstTransformSubstitution(0));
    {% endif %}

    {% for index, morpheme in enumerate(rule.production.morphemes) %}
      {% if isinstance(morpheme, Terminal) %}
            next = expect(ctx, {{prefix}}TerminalIdentifier.TERMINAL_{{morpheme.string.upper()}});
            tree.add(next);
        {% if isinstance(nonterminal.macro, SeparatedListMacro) or isinstance(nonterminal.macro, OptionallyTerminatedListMacro) %}
          {% if nonterminal.macro.separator == morpheme %}
            tree.setListSeparator(next);
          {% endif %}
        {% endif %}
      {% endif %}

      {% if isinstance(morpheme, NonTerminal) %}
            subtree = parse_{{morpheme.string.lower()}}(ctx);
            tree.add(subtree);
      {% endif %}
    {% endfor %}

            return tree;
        }
  {% endfor %}

  {% if grammar.must_consume_tokens(nonterminal) %}
        throw new SyntaxError(ctx.error_formatter.unexpected_symbol(
            "{{nonterminal.string.lower()}}",
            current,
            nonterminal_first.get({{nonterminal.id}}),
            rules.get({{rule.id}})
        ));
  {% else %}
        return tree;
  {% endif %}
    }
{% endfor %}

    {% if lexer %}
    /* Section: Lexer */
    private Map<String, List<HermesRegex>> regex = null;

    private class HermesRegex {
        public Pattern pattern;
        public {{prefix}}TerminalIdentifier terminal;
        public String function;

        HermesRegex(Pattern pattern, {{prefix}}TerminalIdentifier terminal, String function) {
            this.pattern = pattern;
            this.terminal = terminal;
            this.function = function;
        }

        public String toString() {
            return String.format("<HermesRegex pattern=%s, terminal=%s, func=%s>", this.pattern, this.terminal, this.function);
        }
    }

    private class LexerMatch {
        public List<Terminal> terminals;
        public String mode;
        public String match;
        public Object context;

        public LexerMatch(List<Terminal> terminals, String mode, Object context) {
            this.terminals = terminals;
            this.mode = mode;
            this.context = context;
        }

        public String toString() {
          StringBuffer t = new StringBuffer();
          for (Terminal x : this.terminals) {
            t.append(x.getTerminalStr() + " ");
          }
          return String.format(
            "<LexerMatch terminals=%s, mode=%s>",
            t, this.mode
          );
        }
    }

    private class LexerContext {
        public String string;
        public int line;
        public int col;
        public String mode;
        public Object context;
        public List<Terminal> terminals;

        LexerContext(String string) {
            this.string = string;
            this.line = 1;
            this.col = 1;
            this.mode = "default";
            this.terminals = new ArrayList<Terminal>();
        }

        public void advance(String match) {
            for (int i = 0; i < match.length(); i++) {
                if (match.charAt(i) == '\n') {
                    this.line += 1;
                    this.col = 1;
                } else {
                    this.col += 1;
                }
            }
            this.string = this.string.substring(match.length());
        }
    }

    {% if re.search(r'public\s+LexerMatch\s+default_action', lexer.code) is None %}
    public LexerMatch default_action(Object context, String mode, String match, {{prefix}}TerminalIdentifier terminal, String resource, int line, int col) {
        List<Terminal> terminals = new ArrayList<Terminal>();
        if (terminal != null) {
            terminals.add(new Terminal(terminal.id(), terminal.string(), match, resource, line, col));
        }
        return new LexerMatch(terminals, mode, context);
    }
    {% endif %}

    /* START USER CODE */
    {{lexer.code}}
    /* END USER CODE */

    {% if re.search(r'public\s+Object\s+init', lexer.code) is None %}
    public Object init() {
        return null;
    }
    {% endif %}

    {% if re.search(r'public\s+void\s+destroy', lexer.code) is None %}
    public void destroy(Object context) {
        return;
    }
    {% endif %}

    private void lexer_init() {
        this.regex = new HashMap<String, List<HermesRegex>>();
{% for mode, regex_list in lexer.items() %}
        this.regex.put("{{mode}}", Arrays.asList(new HermesRegex[] {
  {% for regex in regex_list %}
            new HermesRegex(Pattern.compile({{regex.regex}}), {{prefix+'TerminalIdentifier.TERMINAL_' + regex.terminal.string.upper() if regex.terminal else 'null'}}, {{'"'+regex.function+'"' if regex.function is not None else 'null'}}),
  {% endfor %}
        }));
{% endfor %}
    }

    private void unrecognized_token(String string, int line, int col) throws SyntaxError {
        String[] a = string.split("\n");
        String bad_line = string.split("\n")[line-1];
        StringBuffer spaces = new StringBuffer();
        for (int i = 0; i < col-1; i++) {
          spaces.append(' ');
        }
        String message = String.format(
            "Unrecognized token on line %d, column %d:\n\n%s\n%s^",
            line, col, bad_line, spaces
        );
        throw new SyntaxError(message);
    }

    private LexerMatch next(LexerContext lctx, String resource) {
        for (int i = 0; i < this.regex.get(lctx.mode).size(); i++) {
            HermesRegex regex = this.regex.get(lctx.mode).get(i);
            Matcher matcher = regex.pattern.matcher(lctx.string);
            if (matcher.lookingAt()) {
                if (false && regex.terminal == null) {
                    lctx.advance(matcher.group(0));
                    i = -1;
                    continue;
                }
                String function = regex.function != null ? regex.function : "default_action";
                try {
                    Method method = getClass().getMethod(function, Object.class, String.class, String.class, {{prefix}}TerminalIdentifier.class, String.class, int.class, int.class);
                    LexerMatch lexer_match = (LexerMatch) method.invoke(
                        this,
                        lctx.context,
                        lctx.mode,
                        matcher.group(0),
                        regex.terminal,
                        resource,
                        lctx.line,
                        lctx.col
                    );

                    lexer_match.match = matcher.group(0);
                    lctx.terminals.addAll(lexer_match.terminals);
                    lctx.mode = lexer_match.mode;
                    lctx.context = lexer_match.context;
                    lctx.advance(matcher.group(0));
                    return lexer_match;
                } catch (Exception e) {
                    e.printStackTrace(System.err);
                    continue;
                }
            }
        }
        return null;
    }

    public List<Terminal> lex(String string, String resource) throws SyntaxError {
        LexerContext lctx = new LexerContext(string);
        Object context = this.init();
        String string_copy = new String(string);
        if (this.regex == null) {
            lexer_init();
        }
        while (lctx.string.length() > 0) {
            LexerMatch match = this.next(lctx, resource);

            if (match == null || match.match.length() == 0) {
                this.unrecognized_token(string_copy, lctx.line, lctx.col);
            }
        }
        this.destroy(context);
        return lctx.terminals;
    }
    {% endif %}

    /* Section: Main */
    {% if add_main %}
    public static void main(String args[]) {
        if (args.length != 2 || (!"parsetree".equals(args[0]) && !"ast".equals(args[0]) {% if lexer %} && !"tokens".equals(args[0]){% endif %})) {
          System.out.println("Usage: {{prefix}}Parser <parsetree,ast> <tokens file>");
          {% if lexer %}
          System.out.println("Usage: {{prefix}}Parser <tokens> <source file>");
          {% endif %}
          System.exit(-1);
        }

        if ("parsetree".equals(args[0]) || "ast".equals(args[0])) {
            try {
                TokenStream tokens = new TokenStream();
                String contents = readFile(args[1]);
                JSONArray arr = new JSONArray(contents);

                for ( int i = 0; i < arr.length(); i++ ) {
                    JSONObject token = arr.getJSONObject(i);
                    tokens.add(new Terminal(
                        {{prefix}}Parser.terminal_map.get(token.getString("terminal")).id(),
                        token.getString("terminal"),
                        token.getString("source_string"),
                        token.getString("resource"),
                        token.getInt("line"),
                        token.getInt("col")
                    ));
                }

                {{prefix}}Parser parser = new {{prefix}}Parser();
                ParseTreeNode parsetree = parser.parse(tokens);

                if ( args.length > 1 && args[0].equals("ast") ) {
                    AstNode ast = parsetree.toAst();
                    if ( ast != null ) {
                        System.out.println(ast.toPrettyString());
                    } else {
                        System.out.println("None");
                    }
                } else {
                    System.out.println(parsetree.toPrettyString());
                }
            } catch (Exception e) {
                System.err.println(e.getMessage());
                System.exit(-1);
            }
        }

        {% if lexer %}
        if ("tokens".equals(args[0])) {
            try {
                String contents = readFile(args[1]);
                {{prefix}}Parser parser = new {{prefix}}Parser();
                List<Terminal> terminals = parser.lex(contents, args[1]);
                if (terminals.size() == 0) {
                    System.out.println("[]");
                } else {
                    System.out.println(String.format("[\n    %s\n]", join(terminals, ",\n    ")));
                }
            } catch (Exception e) {
                System.err.println(e.getMessage());
                System.exit(-1);
            }
        }
        {% endif %}
    }
    {% endif %}
}