"""Code Python coloré pour le terminal, sans dépendance (module standard tokenize).

Palette du thème prevost-noir : fond noir, texte blanc, mots-clés rouges, chaînes vertes,
nombres jaunes, fonctions bleu ciel, types mauves, commentaires gris. Le texte reste
identique caractère pour caractère ; seules les séquences de couleur s'ajoutent, et les
caractères de contrôle du code (donnée non fiable) sont neutralisés.
"""
import io
import keyword
import tokenize

WHITE = '40;97'
KEYWORD = '1;38;2;255;85;85'
STRING = '38;2;114;241;149'
NUMBER = '38;2;255;212;71'
FUNCTION = '38;2;135;206;235'
TYPE = '38;2;199;146;234'
COMMENT = '38;2;153;153;153'
CONSTANTS = ('True', 'False', 'None')
FSTRING_PARTS = tuple(getattr(tokenize, name) for name in ('FSTRING_START', 'FSTRING_MIDDLE', 'FSTRING_END')
                      if hasattr(tokenize, name))


def safe(value):
    return ''.join(c if c in '\n\t' or (ord(c) >= 32 and not 127 <= ord(c) < 160) else '�' for c in str(value))


def paint(code, text):
    if not text:
        return ''
    background = '' if code == WHITE else '\033[40m'
    return f'{background}\033[{code}m{safe(text)}\033[0m'


def spans(code):
    """Intervalles (début, fin, couleur) du code ; s'arrête sans erreur à la première anomalie de syntaxe."""
    lines = io.StringIO(code).readlines()
    starts, position = [], 0
    for line in lines:
        starts.append(position)
        position += len(line)
    found, previous = [], None
    stream = iter(tokenize.generate_tokens(io.StringIO(code).readline))
    token = None
    try:
        token = next(stream, None)
        while token is not None:
            upcoming = next(stream, None)
            (r1, c1), (r2, c2) = token.start, token.end
            if 1 <= r1 <= len(starts) and 1 <= r2 <= len(starts):
                begin, end = starts[r1 - 1] + c1, starts[r2 - 1] + c2
                color = None
                if token.type == tokenize.COMMENT:
                    color = COMMENT
                elif token.type == tokenize.STRING or token.type in FSTRING_PARTS:
                    color = STRING
                elif token.type == tokenize.NUMBER:
                    color = NUMBER
                elif token.type == tokenize.NAME:
                    name = token.string
                    if name in CONSTANTS:
                        color = NUMBER
                    elif keyword.iskeyword(name):
                        color = KEYWORD
                    elif previous == 'def':
                        color = FUNCTION
                    elif previous == 'class':
                        color = TYPE
                    elif upcoming is not None and upcoming.type == tokenize.OP and upcoming.string == '(':
                        color = TYPE if name[:1].isupper() and not name.isupper() else FUNCTION
                    elif name[:1].isupper() and not name.isupper():
                        color = TYPE
                if color and end > begin:
                    found.append((begin, end, color))
            if token.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT):
                previous = token.string
            token = upcoming
    except (tokenize.TokenError, SyntaxError, IndentationError, ValueError):
        pass  # code partiel ou cassé : le reste s'affiche en blanc
    return found


def highlight_python(code):
    code = str(code)
    out, position = [], 0
    for begin, end, color in spans(code):
        if begin < position:
            continue  # intervalle qui se chevauche : ignoré plutôt que de risquer de déformer le texte
        out.append(paint(WHITE, code[position:begin]))
        out.append(paint(color, code[begin:end]))
        position = end
    out.append(paint(WHITE, code[position:]))
    return ''.join(out)


def highlight_diff(diff):
    """Différences d'un fichier Python : marqueurs + vert, - rouge, contenu coloré ligne par ligne."""
    lines = str(diff).split('\n')
    out = []
    for index, line in enumerate(lines):
        if (index == 0 and line.startswith('--- ')) or (index == 1 and line.startswith('+++ ')) or line.startswith('@@'):
            out.append(paint(WHITE, line))
        elif line[:1] in ('+', '-', ' ') and line:
            marker = {'+': STRING, '-': KEYWORD, ' ': WHITE}[line[0]]
            out.append(paint(marker, line[0]) + highlight_python(line[1:]))
        else:
            out.append(paint(WHITE, line))
    return '\n'.join(out)
