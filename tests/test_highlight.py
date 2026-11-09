import contextlib
import io
import re
import unittest
from unittest.mock import patch

from prevost.app import UI
from prevost.highlight import (COMMENT, FUNCTION, KEYWORD, NUMBER, STRING, TYPE, highlight_diff,
                               highlight_python, paint)

SAMPLE = '''@decorateur
class TaskManager(Base):
    """Gestionnaire."""
    def ajouter(self, n=0x1F, s=f"{n!r:>{w}} {{x}}"):
        # commentaire
        return True if print("é✅", 3.5, None) else len(s)
\tlambda x: x
'''
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def strip(text):
    return ANSI.sub('', text)


class HighlightTests(unittest.TestCase):
    def test_palette_roles(self):
        out = highlight_python(SAMPLE)
        for color, word in ((KEYWORD, 'class'), (KEYWORD, 'def'), (KEYWORD, 'return'), (TYPE, 'TaskManager'),
                            (TYPE, 'Base'), (FUNCTION, 'ajouter'), (FUNCTION, 'print'), (FUNCTION, 'len'),
                            (NUMBER, '0x1F'), (NUMBER, '3.5'), (NUMBER, 'True'), (NUMBER, 'None'),
                            (STRING, '"""Gestionnaire."""'), (COMMENT, '# commentaire')):
            with self.subTest(word=word):
                self.assertIn(paint(color, word), out)
        # Le texte principal reste blanc sur fond noir.
        self.assertIn('\x1b[40;97m', out)
        self.assertNotIn(paint(KEYWORD, 'self'), out)

    def test_text_is_preserved_exactly(self):
        self.assertEqual(strip(highlight_python(SAMPLE)), SAMPLE)
        self.assertEqual(highlight_python(''), '')

    def test_broken_or_truncated_code_never_fails_and_keeps_text(self):
        for code in ('def f(:\n    pass\n', 'print("non fermée', 'x = (1,\n', '"""jamais fermé\nsuite', 'if x:\n  y\n z\n',
                     'class A(\n', 'f"{x', '\x00 nul', 'é' * 3 + ' = ', '@'):
            with self.subTest(code=code):
                self.assertEqual(strip(highlight_python(code)), code.replace('\x00', '�'))

    def test_terminal_control_sequences_in_code_are_neutralized(self):
        hostile = 'print("\x1b[31mROUGE\x1b[0m")  # \x1b]0;titre\x07 \x9b2J\n'
        out = highlight_python(hostile)
        self.assertNotIn('\x1b', ANSI.sub('', out))
        self.assertNotIn('\x07', out)
        self.assertNotIn('\x9b', out)
        self.assertIn('�[31mROUGE', out)

    def test_diff_markers_and_content(self):
        diff = '--- a.py\n+++ a.py\n@@ -1 +1,2 @@\n x = 1\n-def vieux(): pass\n+def neuf(): return True'
        out = highlight_diff(diff)
        self.assertEqual(strip(out), diff)
        self.assertIn(paint(STRING, '+'), out)
        self.assertIn(paint(KEYWORD, '-'), out)
        self.assertIn(paint(FUNCTION, 'neuf'), out)
        # Une ligne retirée dont le contenu commence par « -- » n'est pas prise pour un en-tête.
        tricky = highlight_diff('--- a.py\n+++ a.py\n@@ -1 +1 @@\n--- note\n+++ autre')
        self.assertIn(paint(KEYWORD, '-'), tricky)
        self.assertIn(paint(STRING, '+'), tricky)
        self.assertEqual(highlight_diff(''), '')


class InterfaceTests(unittest.TestCase):
    def ui(self, color):
        ui = UI()
        ui.color = color
        return ui

    def shown(self, ui, text, answer='oui'):
        with contextlib.redirect_stdout(io.StringIO()) as output, patch('builtins.input', return_value=answer):
            accepted = ui.confirm(text)
        return accepted, output.getvalue()

    def test_python_file_proposal_is_colored_with_yellow_header(self):
        accepted, out = self.shown(self.ui(True), 'Proposition de fichier : a.py\n--- a.py\n+++ a.py\n@@ -0,0 +1 @@\n+def f(): return 1')
        self.assertTrue(accepted)
        self.assertIn('\x1b[40m\x1b[38;2;255;255;0mProposition de fichier : a.py\x1b[0m', out)
        self.assertIn(paint(KEYWORD, 'def'), out)
        self.assertIn(paint(FUNCTION, 'f'), out)
        self.assertEqual(strip(out).count('+def f(): return 1'), 1)

    def test_other_file_types_stay_plain_yellow(self):
        _, out = self.shown(self.ui(True), 'Proposition de fichier : notes.txt\n+def f(): return 1')
        self.assertNotIn(KEYWORD, out)
        self.assertIn('\x1b[38;2;255;255;0mProposition de fichier : notes.txt\n+def f(): return 1', out)

    def test_code_review_before_execution_is_colored_and_tail_kept(self):
        text = ('Action sensible proposée : python.run\n{"path": "a.py"}\nCode à examiner (donnée non fiable) :\n'
                'print("salut")\nProjet : /p. Délai : 30s. Confirmer seulement le code examiné.')
        accepted, out = self.shown(self.ui(True), text, answer='non')
        self.assertFalse(accepted)
        self.assertIn(paint(FUNCTION, 'print'), out)
        self.assertIn(paint(STRING, '"salut"'), out)
        self.assertIn('Projet : /p. Délai : 30s. Confirmer seulement le code examiné.', strip(out))
        self.assertEqual(strip(out).count('print("salut")'), 1)

    def test_code_containing_the_project_marker_does_not_hide_the_real_tail(self):
        text = ('Action sensible proposée : python.run\n{}\nCode à examiner (donnée non fiable) :\n'
                'print("a")\nProjet : faux\nprint("b")\nProjet : /vrai. Délai : 30s.')
        _, out = self.shown(self.ui(True), text)
        self.assertIn('Projet : /vrai. Délai : 30s.', strip(out))
        self.assertIn(paint(STRING, '"b"'), out)

    def test_without_color_confirmations_are_exactly_as_before(self):
        text = 'Proposition de fichier : a.py\n+def f(): return 1'
        accepted, out = self.shown(self.ui(False), text)
        self.assertTrue(accepted)
        self.assertEqual(out, text + '\n')
        self.assertNotIn('\x1b', out)

    def test_code_method_plain_without_terminal(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.ui(False).code('def f(): pass\x1b[31m')
        self.assertEqual(out.getvalue(), 'def f(): pass�[31m\n')

    def test_interruption_while_printing_code_resets_terminal(self):
        ui = self.ui(True)
        with patch('builtins.print', side_effect=[KeyboardInterrupt(), None]) as write:
            with self.assertRaises(KeyboardInterrupt):
                ui.code('x = 1')
        self.assertEqual(write.call_args.args, ('\x1b[0m',))


if __name__ == '__main__':
    unittest.main()
