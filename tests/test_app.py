import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from prevost.app import Ollama, Project, UI, choose, code_mission


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'project'
        self.root.mkdir()
        self.state = Path(self.tmp.name)/'state'
        self.project = Project(self.root, self.state)

    def test_terminal_palette_and_control_neutralization(self):
        ui = UI()
        ui.color = True
        with contextlib.redirect_stdout(io.StringIO()) as output:
            ui.show('Réponse')
            ui.tool('python.run')
            ui.raw('brut\x1b[31m\x9b0m')
            self.assertEqual(ui.answer(iter(['Bon', 'jour'])), 'Bonjour')
        self.assertEqual(output.getvalue(),
            '\x1b[40m\x1b[38;2;135;206;235mRéponse\x1b[0m\n'
            '\x1b[40m\x1b[38;2;255;255;0mpython.run\x1b[0m\n'
            '\x1b[40;97mbrut�[31m�0m\x1b[0m\n'
            '\x1b[40m\x1b[38;2;255;32;32mPRÉVOST > \x1b[0m'
            '\x1b[40m\x1b[38;2;135;206;235mBon\x1b[0m\x1b[40m\x1b[38;2;135;206;235mjour\x1b[0m\x1b[0m\n')

    def test_input_resets_on_return_and_interrupt(self):
        ui = UI()
        ui.color = True
        for effect in ('oui', EOFError(), KeyboardInterrupt()):
            with self.subTest(effect=effect), contextlib.redirect_stdout(io.StringIO()) as output:
                def read(prompt):
                    self.assertEqual(prompt, '\x1b[40;97mVous > ')
                    if isinstance(effect, BaseException):
                        raise effect
                    return effect
                with patch('builtins.input', side_effect=read):
                    if isinstance(effect, BaseException):
                        with self.assertRaises(type(effect)):
                            ui.read('Vous > ')
                    else:
                        self.assertEqual(ui.read('Vous > '), 'oui')
                self.assertEqual(output.getvalue(), '\x1b[0m')

    def test_no_color_and_redirected_output(self):
        for terminal, environment in ((False, {}), (True, {'NO_COLOR': '1'})):
            with patch('sys.stdout.isatty', return_value=terminal), patch.dict('os.environ', environment, clear=True):
                ui = UI()
            self.assertFalse(ui.color)
            with contextlib.redirect_stdout(io.StringIO()) as output, patch('builtins.input', return_value='oui') as read:
                ui.answer(['texte\x1b[31m'])
                ui.tool('outil')
                ui.raw('sortie')
                self.assertTrue(ui.confirm('proposition'))
            self.assertNotIn('\x1b', output.getvalue())
            self.assertNotIn('\x1b', read.call_args.args[0])

    def test_stream_failure_leaves_reset_color(self):
        ui = UI()
        ui.color = True
        for error in (ValueError('flux interrompu'), KeyboardInterrupt()):
            def chunks():
                yield 'partiel'
                raise error
            with self.subTest(error=error), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaises(type(error)):
                    ui.answer(chunks())
                self.assertTrue(output.getvalue().endswith('partiel\x1b[0m\x1b[0m\n'))

    def test_interrupted_display_resets_terminal(self):
        ui = UI()
        ui.color = True
        for display in (ui.show, ui.tool, ui.raw):
            with self.subTest(display=display), patch('builtins.print', side_effect=[KeyboardInterrupt(), None]) as write:
                with self.assertRaises(KeyboardInterrupt):
                    display('texte')
                self.assertEqual(write.call_args.args, ('\x1b[0m',))
                self.assertTrue(write.call_args.kwargs['flush'])

    def test_complete_mission_simulated_model_real_execution(self):
        # Seule la génération Ollama est simulée ; écriture et sous-processus sont réels.
        plan = {'files': [{'path': 'bonjour.py', 'content': 'print("Bonjour PRÉVOST")\n'}],
                'commands': [[sys.executable, 'bonjour.py']]}
        class Model:
            def chat(self, *args, **kwargs):
                text = json.dumps(plan)
                yield text[:30]
                yield text[30:]
        ui = UI()
        ui.color = True
        with contextlib.redirect_stdout(io.StringIO()) as captured, patch('builtins.input', return_value='oui'):
            code_mission(Model(), 'simulé', self.project, 'Créer un programme de salutation', ui, 5)
        self.assertIn('\x1b[38;2;135;206;235m', captured.getvalue())
        self.assertIn('\x1b[38;2;255;255;0mExécution', captured.getvalue())
        self.assertIn('\x1b[38;2;255;255;0mCommande proposée', captured.getvalue())
        self.assertIn('\x1b[40;97m{', captured.getvalue())
        self.assertIn('Bonjour PRÉVOST', self.project.read('bonjour.py'))
        records = [json.loads(line) for line in self.project.record.read_text().splitlines()]
        result = next(row for row in records if row.get('event') == 'command')
        self.assertEqual(result['output'], 'Bonjour PRÉVOST\n')
        self.assertEqual(result['returncode'], 0)
        self.assertFalse(result['timeout'])
        self.assertEqual(len(Project(self.root, self.state).conversation()), 2)

    def test_refused_command_does_not_execute(self):
        result = self.project.run([sys.executable, '-c', 'open("bad", "w").close()'], 2, lambda _: False)
        self.assertTrue(result['cancelled'])
        self.assertFalse((self.root/'bad').exists())

    def test_timeout(self):
        start = time.monotonic()
        result = self.project.run([sys.executable, '-c', 'import time; time.sleep(10)'], .1, lambda _: True)
        self.assertTrue(result['timeout'])
        self.assertLess(time.monotonic() - start, 3)

    def test_output_and_nonzero_status(self):
        result = self.project.run([sys.executable, '-c', 'import sys; print("erreur"); sys.exit(3)'], 3, lambda _: True)
        self.assertEqual(result['returncode'], 3)
        self.assertEqual(result['output'], 'erreur\n')

    def test_containment(self):
        for path in ('../outside', '/tmp/outside', '.git/config'):
            with self.assertRaises(ValueError):
                self.project.path(path)
        (self.root/'link').symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.project.path('link/file')

    def test_write_refusal_and_backup(self):
        self.assertFalse(self.project.write('a.py', 'old\n', lambda _: False))
        self.assertFalse((self.root/'a.py').exists())
        self.project.write('a.py', 'old\n', lambda _: True)
        self.project.write('a.py', 'new\n', lambda _: True)
        self.assertEqual(self.project.read('a.py'), 'new\n')
        self.assertEqual(next((self.project.state/'backups').iterdir()).read_text(), 'old\n')

    def test_concurrent_change_refused(self):
        self.project.write('a', 'old', lambda _: True)
        def confirm(_):
            (self.root/'a').write_text('changed')
            return True
        with self.assertRaises(ValueError):
            self.project.write('a', 'new', confirm)
        self.assertEqual(self.project.read('a'), 'changed')

    def test_project_histories_separate(self):
        self.project.save({'role': 'user', 'content': 'mission'})
        other = Path(self.tmp.name)/'other'
        other.mkdir()
        self.assertEqual(Project(other, self.state).conversation(), [])
        self.assertEqual(self.project.record.stat().st_mode & 0o777, 0o600)

    def test_protocol_stream_simulated_transport(self):
        chunks = b'{"message":{"content":"Bon"},"done":false}\n{"message":{"content":"jour"},"done":true}\n'
        client = Ollama('http://127.0.0.1:11435')
        with patch.object(client, 'open', return_value=io.BytesIO(chunks)):
            self.assertEqual(list(client.chat('installed', [])), ['Bon', 'jour'])
        with patch.object(client, 'open', return_value=io.BytesIO(b'{"message":{"content":"partiel"}}\n')):
            with self.assertRaises(ValueError):
                list(client.chat('installed', []))

    def test_model_must_be_installed(self):
        client = Ollama('http://localhost:11434')
        with patch.object(client, 'models', return_value=['installed']):
            self.assertEqual(choose(client, UI(), 'installed'), 'installed')
            with self.assertRaises(ValueError):
                choose(client, UI(), 'invented')

    def test_bad_plan_has_no_partial_write(self):
        class Model:
            def chat(self, *args, **kwargs):
                yield json.dumps({'files': [{'path': 'good', 'content': 'x'}, {'path': '../bad', 'content': 'x'}]})
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            code_mission(Model(), 'simulé', self.project, 'mission', UI(), 2)
        self.assertFalse((self.root/'good').exists())

    def test_cli_manual_mission_real(self):
        commands = '/ecrire hello.py\nprint("MISSION_OK")\n.fin\noui\n/commande ' + shlex_executable() + ' hello.py\noui\n/quitter\n'
        result = subprocess.run([sys.executable, '-B', '-m', 'prevost', '--project', str(self.root),
            '--ollama', 'http://127.0.0.1:1', '--http-timeout', '.1'], input=commands,
            text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('MISSION_OK\\n', result.stdout)
        self.assertIn('Outils manuels disponibles', result.stdout)
        self.assertEqual((self.root/'hello.py').read_text(), 'print("MISSION_OK")\n')

    def test_network_commands_dispatch_without_model_or_implicit_audit(self):
        from prevost.app import main
        commands = ['/reseaux', '/arreter-reseau', '/retirer-reseau identifiant', '/veille-reseau', '/quitter']
        with patch('prevost.app.Project', return_value=self.project), patch.object(Ollama, 'models', return_value=['simule']), \
             patch('builtins.input', side_effect=commands), patch('prevost.network.main', return_value=0) as network_main, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--project', str(self.root), '--model', 'simule', '--ollama', 'http://127.0.0.1:11434']), 0)
        self.assertEqual([call.args[0] for call in network_main.call_args_list],
                         [['liste'], ['arreter'], ['retirer', '--network', 'identifiant'], ['veille']])


def shlex_executable():
    import shlex
    return shlex.quote(sys.executable)


if __name__ == '__main__':
    unittest.main()
