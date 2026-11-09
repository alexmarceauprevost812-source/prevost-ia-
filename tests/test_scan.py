"""Routage Nmap testé sans aucun scan réseau réel."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from prevost.app import Ollama, Project, UI, main, scan_mission, scan_request, scan_target


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'project'; self.root.mkdir()
        self.project = Project(self.root, Path(self.tmp.name)/'state')
        self.ui = UI(); self.ui.color = True

    def test_narrow_user_intent_and_typo(self):
        for request, target in [('scan complet', ''), ('scam complet', ''),
                                ('SCAN COMPLET scanme.nmap.org', 'scanme.nmap.org'),
                                ('scan  complet  192.0.2.1', '192.0.2.1')]:
            self.assertEqual(scan_request(request), target)
        for text in ['explique un scan complet', 'scammer une personne', 'commande : scan complet', '/agent scan complet']:
            self.assertIsNone(scan_request(text))

    def test_exact_target_validation(self):
        for text in ['', '-A', 'host --script all', 'https://scanme.nmap.org', '192.0.2.0/24',
                     '192.0.2.1-254', '192.0.2.999', '*.test', 'a;id', 'a\nb', '::1', '224.0.0.1', '0.0.0.0']:
            with self.subTest(target=text), self.assertRaises(ValueError):
                scan_target(text)
        self.assertEqual(scan_target('SCANME.NMAP.ORG'), 'scanme.nmap.org')
        self.assertEqual(scan_target('192.0.2.1'), '192.0.2.1')

    def test_typo_routes_to_real_command_contract_without_ollama(self):
        # L’exécution Nmap est simulée ; le contrat de confirmation est réellement appelé.
        for request in ['scam complet', 'scan complet', '/scan']:
            with self.subTest(request=request):
                prompts = []
                def execute(argv, timeout, confirm):
                    self.assertEqual(argv, ['nmap', '-v', '-A', 'scanme.nmap.org'])
                    self.assertEqual(timeout, 30)
                    prompts.append('called')
                    self.assertTrue(confirm('Commande proposée : nmap -v -A scanme.nmap.org'))
                    return {'returncode': 0, 'output': 'résultat simulé'}
                with patch('prevost.app.Project', return_value=self.project), \
                     patch.object(Ollama, 'models', side_effect=OSError('modèle indisponible simulé')), \
                     patch.object(Ollama, 'chat') as chat, patch.object(self.project, 'run', side_effect=execute), \
                     patch('builtins.input', side_effect=[request, 'scanme.nmap.org', 'oui', '/quitter']), \
                     contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main(['--project', str(self.root), '--ollama', 'http://127.0.0.1:11434']), 0)
                chat.assert_not_called()
                self.assertEqual(prompts, ['called'])
                self.assertIn('Autorisation distincte', output.getvalue())
                self.assertIn('résultat simulé', output.getvalue())
                self.assertFalse(self.project.conversation())

    def test_refusal_cancellation_and_invalid_target_never_start_process(self):
        with patch('prevost.app.subprocess.Popen') as start, contextlib.redirect_stdout(io.StringIO()):
            with patch('builtins.input', return_value='non'):
                scan_mission(self.project, 'scanme.nmap.org', self.ui, 3)
            with patch('builtins.input', return_value=''):
                scan_mission(self.project, '', self.ui, 3)
            with self.assertRaises(ValueError):
                scan_mission(self.project, 'scanme.nmap.org --script all', self.ui, 3)
            with patch('builtins.input', side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
                scan_mission(self.project, '', self.ui, 3)
        start.assert_not_called()

    def test_terminal_palette_and_failed_resolution_reported_as_no_scan(self):
        with patch.object(self.project, 'run', return_value={
                'returncode': 0, 'output': 'Failed to resolve "scanme.nmap.org".\x1b[31m\n0 IP addresses'}), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            scan_mission(self.project, 'scanme.nmap.org', self.ui, 3)
        text = output.getvalue()
        self.assertIn('\x1b[38;2;0;225;255m', text)
        self.assertIn('\x1b[38;2;255;255;0mExécution Nmap', text)
        self.assertIn('\x1b[40;97m{', text)
        self.assertIn('Aucune cible analysée', text)

    def test_cli_typo_fake_nmap_real_subprocess(self):
        # Exécutable factice : aucune sonde, aucun DNS ; seule la CLI complète est réelle.
        binary_dir = Path(self.tmp.name)/'bin'; binary_dir.mkdir()
        fake = binary_dir/'nmap'
        fake.write_text('#!' + sys.executable + '\nimport sys\nprint("NMAP_SIMULE", repr(sys.argv[1:]))\n')
        fake.chmod(0o700)
        env = {**os.environ, 'PATH': str(binary_dir) + os.pathsep + os.environ.get('PATH', '')}
        commands = 'scam complet\nscanme.nmap.org\noui\n/quitter\n'
        result = subprocess.run([sys.executable, '-B', '-m', 'prevost', '--project', str(self.root),
                                 '--state-dir', str(Path(self.tmp.name)/'cli-state'),
                                 '--ollama', 'http://127.0.0.1:1', '--http-timeout', '.1'],
                                input=commands, text=True, capture_output=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('NMAP_SIMULE', result.stdout)
        self.assertIn("['-v', '-A', 'scanme.nmap.org']", result.stdout)
        self.assertIn('Autorisation distincte', result.stdout)
        self.assertNotIn('je ne peux pas aider', result.stdout)

    def test_model_response_does_not_trigger_command(self):
        with patch('prevost.app.Project', return_value=self.project), \
             patch.object(Ollama, 'models', return_value=['simule']), \
             patch.object(Ollama, 'chat', return_value=iter(['scan complet scanme.nmap.org'])), \
             patch.object(self.project, 'run') as run, \
             patch('builtins.input', side_effect=['Explique Nmap', '/quitter']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--project', str(self.root), '--model', 'simule', '--ollama', 'http://127.0.0.1:11434']), 0)
        run.assert_not_called()
        self.assertEqual(self.project.conversation()[-1]['content'], 'scan complet scanme.nmap.org')


if __name__ == '__main__':
    unittest.main()
