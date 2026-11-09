import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prevost.app import Ollama, Project, UI, code_mission, describe_plan, main
from prevost.memory import ProjectMemory


def plan(code='print("ok")\n', expected='ok\n', path='p.py'):
    return json.dumps({'files': [{'path': path, 'content': code}], 'commands': [],
                       'checks': [{'path': path, 'expected_stdout': expected}]})


class Script:
    def __init__(self, *answers):
        self.answers = list(answers)

    def chat(self, model, messages, structured=False):
        yield self.answers.pop(0)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'project'
        self.root.mkdir()
        self.project = Project(self.root, Path(self.tmp.name)/'state')


class PlanDisplayTests(Base):
    def mission(self, model, raw_plan=False, color=False):
        ui = UI()
        ui.color = color
        ui.confirm = lambda text: True
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = code_mission(model, 'simulé', self.project, 'Faire p.py', ui, 5,
                                  memory=ProjectMemory(self.project.state), raw_plan=raw_plan)
        return result, output.getvalue()

    def test_describe_plan_lists_files_commands_and_checks(self):
        self.project.write('vieux.py', 'a = 1\nb = 2\n', lambda _: True)
        files = [{'path': 'vieux.py', 'content': 'a = 1\nb = 3\nc = 4\n'}, {'path': 'neuf.py', 'content': 'print(1)\n'},
                 {'path': 'notes.txt', 'content': 'x'}]
        text = describe_plan(self.project, files, [['python3', 'neuf.py', 'deux mots']],
                             [{'path': 'neuf.py', 'expected_stdout': 'x' * 100 + '\nfin\n'}])
        self.assertIn('rien n’est écrit ni lancé avant vos « oui »', text)
        self.assertIn('vieux.py : modifié, 3 ligne(s)', text)
        self.assertIn('neuf.py : nouveau, 1 ligne(s)', text)
        self.assertIn("python3 neuf.py 'deux mots'", text)
        self.assertIn('2 ligne(s), commence par', text)
        self.assertIn('…', text)
        self.assertIn('Attention : aucun contrôle pour vieux.py ; le bilan restera incomplet.', text)
        self.assertNotIn('notes.txt ; ', text)
        self.assertNotIn('Attention : aucun contrôle pour vieux.py, neuf.py', text)

    def test_describe_empty_plan_and_control_characters(self):
        self.assertIn('Fichiers : aucun', describe_plan(self.project, [], [], []))
        self.assertIn('Contrôles : aucun', describe_plan(self.project, [], [], []))
        text = describe_plan(self.project, [{'path': 'p.py', 'content': 'x'}], [],
                             [{'path': 'p.py', 'expected_stdout': '\x1b[31mrouge\n'}])
        self.assertNotIn('\x1b', text)

    def test_default_hides_raw_json_and_shows_readable_plan(self):
        result, output = self.mission(Script(plan()))
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertIn('je prépare le plan', output)
        self.assertIn('Plan proposé', output)
        self.assertIn('p.py : nouveau', output)
        # Le brut du plan (clé « commands ») n'apparaît pas ; le bilan final, lui, contient bien « files ».
        self.assertNotIn('"commands"', output)

    def test_raw_plan_option_still_streams_the_json(self):
        _, output = self.mission(Script(plan()), raw_plan=True)
        self.assertIn('"commands"', output)
        self.assertIn('Plan proposé', output)
        self.assertNotIn('je prépare le plan', output)

    def test_progress_dots_follow_the_amount_received(self):
        ui = UI()
        ui.color = False
        with contextlib.redirect_stdout(io.StringIO()) as output:
            received = ui.progress(iter(['a' * 450, 'b' * 450]), 'je prépare le plan')
        self.assertEqual(received, 'a' * 450 + 'b' * 450)
        self.assertEqual(output.getvalue(), 'PRÉVOST > je prépare le plan..\n')

    def test_progress_restores_terminal_on_stream_failure(self):
        ui = UI()
        ui.color = True
        def chunks():
            yield 'partiel'
            raise ValueError('flux interrompu')
        with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(ValueError):
            ui.progress(chunks(), 'je prépare le plan')
        self.assertIn('\x1b[0m', output.getvalue())

    def test_each_correction_shows_its_own_readable_plan(self):
        _, output = self.mission(Script(plan(code='print("faux")\n'), plan()))
        self.assertEqual(output.count('Plan proposé'), 2)
        self.assertEqual(output.count('je prépare le plan'), 2)


class UndoTests(Base):
    def versions(self, name, *contents):
        for content in contents:
            self.project.write(name, content, lambda _: True)

    def test_backups_are_attributed_to_their_file_newest_first(self):
        self.versions('a.py', 'v1\n', 'v2\n', 'v3\n')
        self.versions('b.py', 'x1\n', 'x2\n')
        found = self.project.backups('a.py')
        self.assertEqual([(self.project.state/'backups'/e['file']).read_text() for e in found], ['v2\n', 'v1\n'])
        self.assertEqual(len(self.project.backups('b.py')), 1)
        self.assertEqual(self.project.backups('jamais.py'), [])
        self.assertEqual(self.project.backups('./a.py'), found)
        self.assertEqual((self.project.state/'backups.jsonl').stat().st_mode & 0o777, 0o600)
        self.assertTrue(all(p.name.endswith('.bak') for p in (self.project.state/'backups').iterdir()))

    def test_restore_shows_diff_asks_confirmation_and_keeps_replaced_version(self):
        self.versions('a.py', 'v1\n', 'v2\n', 'v3\n')
        proposals = []
        oldest = self.project.backups('a.py')[-1]
        self.assertTrue(self.project.restore('a.py', oldest, lambda text: proposals.append(text) or True))
        self.assertEqual(self.project.read('a.py'), 'v1\n')
        self.assertIn('Proposition de fichier : a.py', proposals[0])
        self.assertIn('-v3', proposals[0])
        self.assertIn('+v1', proposals[0])
        # La version remplacée (v3) est sauvegardée : la restauration elle-même s'annule.
        newest = self.project.backups('a.py')[0]
        self.assertEqual((self.project.state/'backups'/newest['file']).read_text(), 'v3\n')
        self.assertEqual(len(self.project.backups('a.py')), 3)

    def test_refused_restore_changes_nothing(self):
        self.versions('a.py', 'v1\n', 'v2\n')
        before = len(self.project.backups('a.py'))
        self.assertFalse(self.project.restore('a.py', self.project.backups('a.py')[0], lambda _: False))
        self.assertEqual(self.project.read('a.py'), 'v2\n')
        self.assertEqual(len(self.project.backups('a.py')), before)

    def test_tampered_index_cannot_escape_the_backup_folder(self):
        self.versions('a.py', 'v1\n', 'v2\n')
        secret = Path(self.tmp.name)/'secret.bak'
        secret.write_text('SECRET')
        index = self.project.state/'backups.jsonl'
        with index.open('a') as stream:
            for entry in ({'file': '../../secret.bak', 'path': 'a.py', 'date': 'x'},
                          {'file': str(secret), 'path': 'a.py', 'date': 'x'},
                          {'file': '999.bak', 'path': 'a.py', 'date': 'x'}, 'pas un objet', {'path': 'a.py'}):
                stream.write(json.dumps(entry) + '\n')
            stream.write('{pas du json\n')
        self.assertEqual(len(self.project.backups('a.py')), 1)
        with self.assertRaises(ValueError):
            self.project.restore('a.py', {'file': '../../secret.bak'}, lambda _: True)
        with self.assertRaises(ValueError):
            self.project.restore('a.py', 'pas un dict', lambda _: True)
        self.assertEqual(self.project.read('a.py'), 'v2\n')

    def test_unsafe_names_are_refused(self):
        for name in ('../x.py', '/etc/passwd', '.git/config'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.project.backups(name)

    def test_older_backups_without_an_index_are_counted_not_listed(self):
        self.versions('a.py', 'v1\n', 'v2\n')
        (self.project.state/'backups'/'123.bak').write_text('ancienne')
        self.assertEqual(self.project.unattributed_backups(), 1)
        self.assertEqual(len(self.project.backups('a.py')), 1)
        fresh = Project(Path(self.tmp.name)/'autre', Path(self.tmp.name)/'autre-etat') if (Path(self.tmp.name)/'autre').mkdir() is None else None
        self.assertEqual(fresh.unattributed_backups(), 0)


class UndoCommandTests(Base):
    def session(self, inputs):
        with patch('prevost.app.Project', return_value=self.project), patch.object(Ollama, 'models', return_value=['simule']), \
             patch('builtins.input', side_effect=inputs), contextlib.redirect_stdout(io.StringIO()) as output:
            status = main(['--project', str(self.root), '--model', 'simule', '--ollama', 'http://127.0.0.1:11434'])
        return status, output.getvalue()

    def setUp(self):
        super().setUp()
        for content in ('v1\n', 'v2\n', 'v3\n'):
            self.project.write('a.py', content, lambda _: True)

    def test_list_then_restore_with_confirmation(self):
        status, output = self.session(['/annuler a.py', '/annuler a.py 2', 'oui', '/quitter'])
        self.assertEqual(status, 0)
        self.assertIn('1. ', output)
        self.assertIn('2. ', output)
        self.assertIn('Restaurer : /annuler a.py NUMÉRO', output)
        self.assertIn('Fichier restauré', output)
        self.assertEqual(self.project.read('a.py'), 'v1\n')

    def test_refusal_and_wrong_input_change_nothing(self):
        status, output = self.session(['/annuler a.py 1', '', '/annuler', '/annuler a.py 9', '/annuler a.py x',
                                       '/annuler inconnu.py', '/quitter'])
        self.assertEqual(status, 0)
        self.assertEqual(self.project.read('a.py'), 'v3\n')
        self.assertIn('Restauration refusée', output)
        self.assertIn('Usage : /annuler', output)
        self.assertIn('Numéro de sauvegarde invalide', output)
        self.assertIn('Aucune sauvegarde pour inconnu.py', output)
        self.assertIn('ne supprime rien', output)

    def test_mention_of_older_unattributed_backups(self):
        (self.project.state/'backups'/'1.bak').write_text('ancienne')
        _, output = self.session(['/annuler a.py', '/quitter'])
        self.assertIn('1 sauvegarde(s) plus ancienne(s)', output)


if __name__ == '__main__':
    unittest.main()
