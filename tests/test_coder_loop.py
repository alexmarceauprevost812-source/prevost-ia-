import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from prevost.app import Ollama, Project, UI, code_mission, main
from prevost.memory import ProjectMemory


def plan(path='p.py', code='print("ok")\n', expected='ok\n', commands=None):
    body = {'files': [{'path': path, 'content': code}], 'commands': commands or []}
    if expected is not None:
        body['checks'] = [{'path': path, 'expected_stdout': expected}]
    return json.dumps(body)


class Script:
    """Modèle simulé : réponses dans l’ordre ; sert la dernière en boucle si repeat."""
    def __init__(self, *answers, repeat=False):
        self.answers, self.repeat, self.calls = list(answers), repeat, []

    def chat(self, model, messages, structured=False):
        self.calls.append(messages)
        yield self.answers[0] if self.repeat else self.answers.pop(0)


class CoderLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'project'
        self.root.mkdir()
        self.state = Path(self.tmp.name)/'state'
        self.project = Project(self.root, self.state)
        self.memory = ProjectMemory(self.project.state)
        self.proposals = []
        self.ui = UI()
        self.answers = []
        self.ui.confirm = self.confirm

    def confirm(self, text):
        self.proposals.append(text)
        return self.answers.pop(0) if self.answers else True

    def run_mission(self, model, request='Faire p.py', **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = code_mission(model, 'simulé', self.project, request, self.ui, kwargs.pop('timeout', 5),
                                  memory=self.memory, **kwargs)
        self.output = output.getvalue()
        return result

    def outcomes(self):
        return [m['status'] for m in json.loads(self.memory.path.read_text(encoding='utf-8'))['missions']]

    def written_proposals(self):
        return [p for p in self.proposals if p.startswith('Proposition de fichier')]

    # --- Mission 2 : refus avant écriture -------------------------------------------------

    def test_truncated_json_is_retried_once_and_nothing_is_written_before(self):
        model = Script(plan()[:40], plan())
        result = self.run_mission(model)
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertEqual(len(model.calls), 2)
        self.assertIn('JSON invalide ou tronqué', model.calls[1][-1]['content'])
        self.assertIn('Plan refusé avant écriture', self.output)
        self.assertEqual(len(self.written_proposals()), 1)
        self.assertEqual(result['attempts'], 1)

    def test_truncated_json_twice_stops_without_any_write(self):
        model = Script(plan()[:40], plan()[:50])
        self.assertIsNone(self.run_mission(model))
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(self.proposals, [])
        self.assertFalse((self.root/'p.py').exists())
        self.assertIn('Rien n’a été écrit', self.output)
        self.assertEqual(self.outcomes(), ['plan_invalide'])

    def test_python_file_that_does_not_compile_never_reaches_the_disk(self):
        broken = plan(code='def f(:\n    pass\n', expected='')
        model = Script(broken, plan())
        result = self.run_mission(model)
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertTrue(all('def f(:' not in p for p in self.proposals))
        self.assertEqual((self.root/'p.py').read_text(), 'print("ok")\n')
        self.assertIn('p.py ne compile pas', model.calls[1][-1]['content'])
        self.assertIn('donnée non fiable', model.calls[1][-1]['content'])

    def test_invalid_json_file_is_refused_before_writing(self):
        bad = json.dumps({'files': [{'path': 'data.json', 'content': '{"a": '}]})
        model = Script(bad, bad)
        self.assertIsNone(self.run_mission(model))
        self.assertFalse((self.root/'data.json').exists())

    def test_test_request_without_command_or_check_is_retried(self):
        silent = json.dumps({'files': [{'path': 'p.py', 'content': 'print("ok")\n'}]})
        model = Script(silent, plan())
        result = self.run_mission(model, request='Fais p.py, lance-le et teste-le')
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertIn('lancement ou un test', model.calls[1][-1]['content'])

    def test_plain_request_without_command_is_accepted_as_before(self):
        silent = json.dumps({'files': [{'path': 'p.py', 'content': 'print("ok")\n'}]})
        model = Script(silent)
        result = self.run_mission(model, request='Écris p.py')
        self.assertEqual(result['status'], 'verification_incomplete')
        self.assertEqual(len(model.calls), 1)

    def test_check_or_command_on_unknown_file_is_refused_before_writing(self):
        wrong_check = json.dumps({'files': [{'path': 'p.py', 'content': 'print("ok")\n'}],
                                  'checks': [{'path': 'autre.py', 'expected_stdout': 'ok\n'}]})
        wrong_command = json.dumps({'files': [{'path': 'p.py', 'content': 'print("ok")\n'}],
                                    'commands': [['python3', 'autre.py']]})
        for bad in (wrong_check, wrong_command):
            with self.subTest(bad=bad):
                model = Script(bad, bad)
                self.assertIsNone(self.run_mission(model))
                self.assertEqual(self.proposals, [])
                self.assertFalse((self.root/'p.py').exists())

    def test_dangerous_path_is_not_retried(self):
        bad = json.dumps({'files': [{'path': '../dehors.py', 'content': 'pass\n'}]})
        model = Script(bad, plan())
        with self.assertRaises(ValueError):
            self.run_mission(model)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(self.outcomes(), ['erreur'])

    # --- Mission 1 : boucle de correction -------------------------------------------------

    def test_failed_check_triggers_a_confirmed_correction_with_evidence(self):
        model = Script(plan(code='print("faux")\n'), plan())
        result = self.run_mission(model)
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertEqual((result['attempts'], result['corrections_used']), (2, 1))
        self.assertEqual(len(model.calls), 2)
        feedback = model.calls[1][-1]['content']
        self.assertIn('faux', feedback)
        self.assertIn('donnée non fiable', feedback)
        # Chaque tentative redemande un « oui » pour le fichier.
        self.assertEqual(len(self.written_proposals()), 2)
        self.assertEqual((self.root/'p.py').read_text(), 'print("ok")\n')
        self.assertEqual(self.outcomes(), ['double_verification_reussie'])
        self.assertIn('Correction 1/2', self.output)

    def test_failed_command_triggers_correction(self):
        failing = plan(code='import sys\nsys.exit(3)\n', expected=None, commands=[[sys.executable, 'p.py']])
        fixed = plan(code='print("ok")\n', commands=[[sys.executable, 'p.py']])
        model = Script(failing, fixed)
        result = self.run_mission(model)
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertIn('code retour 3', model.calls[1][-1]['content'])

    def test_corrections_are_capped(self):
        for corrections, calls in ((0, 1), (1, 2), (2, 3)):
            with self.subTest(corrections=corrections):
                self.memory.clear()
                model = Script(plan(code='print("faux")\n'), repeat=True)
                result = self.run_mission(model, corrections=corrections)
                self.assertEqual(len(model.calls), calls)
                self.assertEqual(result['status'], 'verification_incomplete')
                self.assertEqual(self.outcomes(), ['echec_apres_corrections' if corrections else 'echec'])
                self.assertIn('Mission interrompue : échec', self.output)

    def test_refused_file_stops_without_correction(self):
        self.answers = [False]
        model = Script(plan(), repeat=True)
        self.assertIsNone(self.run_mission(model))
        self.assertEqual(len(model.calls), 1)
        self.assertFalse((self.root/'p.py').exists())
        self.assertEqual(self.outcomes(), ['fichier_refuse'])

    def test_unconfirmed_command_stops_without_correction(self):
        self.answers = [True, False]  # fichier accepté, commande refusée
        model = Script(plan(commands=[[sys.executable, 'p.py']]), repeat=True)
        self.assertIsNone(self.run_mission(model))
        self.assertEqual(len(model.calls), 1)
        self.assertIn('exactement « oui »', self.output)
        self.assertEqual(self.outcomes(), ['non_confirme'])

    def test_unconfirmed_check_stops_without_correction(self):
        self.answers = [True, False]  # fichier accepté, python.run refusé
        model = Script(plan(), repeat=True)
        self.run_mission(model)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(self.outcomes(), ['non_confirme'])

    def test_timeout_stops_without_correction(self):
        slow = plan(code='import time\ntime.sleep(5)\n', expected=None, commands=[[sys.executable, 'p.py']])
        model = Script(slow, repeat=True)
        self.assertIsNone(self.run_mission(model, timeout=.3))
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(self.outcomes(), ['delai_depasse'])

    def test_correction_that_is_itself_broken_gets_one_retry_only(self):
        model = Script(plan(code='print("faux")\n'), plan()[:30], plan()[:35])
        result = self.run_mission(model)
        self.assertEqual(len(model.calls), 3)
        self.assertEqual(self.outcomes(), ['plan_invalide'])
        self.assertIsNone(result)

    # --- Mission 3 : mémoire --------------------------------------------------------------

    def test_memory_is_injected_labelled_and_records_every_outcome(self):
        self.memory.add_note('Toujours utiliser unittest.')
        model = Script(plan())
        self.run_mission(model)
        injected = [m for m in model.calls[0] if m['role'] == 'user' and m['content'].startswith('MÉMOIRE DU PROJET')]
        self.assertEqual(len(injected), 1)
        self.assertIn('non fiables', injected[0]['content'])
        self.assertIn('Toujours utiliser unittest.', injected[0]['content'])
        self.assertLessEqual(len(injected[0]['content'].encode()), 2048)
        # La mission suivante voit le bilan de la précédente.
        model = Script(plan())
        self.run_mission(model, request='Refaire p.py')
        block = next(m for m in model.calls[0] if m['content'].startswith('MÉMOIRE DU PROJET'))['content']
        self.assertIn('[double_verification_reussie]', block)
        self.assertIn('Faire p.py', block)

    def test_memory_never_keeps_outputs_code_or_secrets(self):
        code = 'print("SORTIE_SECRETE_XYZ")\n'
        model = Script(plan(code=code, expected='SORTIE_SECRETE_XYZ\n'))
        self.run_mission(model, request='Fais p.py avec mon mot de passe hunter2')
        raw = self.memory.path.read_text(encoding='utf-8')
        self.assertNotIn('SORTIE_SECRETE_XYZ', raw)
        self.assertNotIn('hunter2', raw)
        self.assertNotIn('print(', raw)
        self.assertEqual(self.memory.path.parent, self.project.state)
        self.assertFalse((self.root/'memory.json').exists())

    def test_default_memory_lives_in_private_state_dir(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code_mission(Script(plan()), 'simulé', self.project, 'Faire p.py', self.ui, 5)
        self.assertTrue((self.project.state/'memory.json').exists())
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ['p.py'])


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'project'
        self.root.mkdir()
        self.project = Project(self.root, Path(self.tmp.name)/'state')

    def session(self, inputs, extra=()):
        with patch('prevost.app.Project', return_value=self.project), patch.object(Ollama, 'models', return_value=['simule']), \
             patch('builtins.input', side_effect=inputs), contextlib.redirect_stdout(io.StringIO()) as output:
            status = main(['--project', str(self.root), '--model', 'simule', '--ollama', 'http://127.0.0.1:11434', *extra])
        return status, output.getvalue()

    def test_memoire_commands(self):
        status, output = self.session(['/memoire', '/memoire note Utiliser unittest', '/memoire',
                                       '/memoire effacer', 'non', '/memoire effacer', 'oui', '/memoire', '/quitter'])
        self.assertEqual(status, 0)
        self.assertIn('Mémoire du projet vide.', output)
        self.assertIn('Note ajoutée : Utiliser unittest', output)
        self.assertIn('Mémoire conservée.', output)
        self.assertIn('Mémoire du projet effacée.', output)
        self.assertFalse(ProjectMemory(self.project.state).path.exists())

    def test_memoire_refuses_secret_and_bad_usage_without_saving(self):
        status, output = self.session(['/memoire note mon mot de passe est abc', '/memoire n’importe quoi', '/quitter'])
        self.assertEqual(status, 0)
        self.assertIn('ressemble à un secret', output)
        self.assertIn('Usage : /memoire', output)
        self.assertFalse(ProjectMemory(self.project.state).path.exists())

    def test_corrections_option_is_passed_and_validated(self):
        with patch('prevost.app.code_mission') as mission:
            self.session(['/coder fais p.py', '/quitter'], extra=['--corrections', '1'])
        self.assertEqual(mission.call_args.kwargs['corrections'], 1)
        with patch('prevost.app.code_mission') as mission:
            self.session(['/coder fais p.py', '/quitter'])
        self.assertEqual(mission.call_args.kwargs['corrections'], 2)
        status, output = self.session([], extra=['--corrections', '9'])
        self.assertEqual(status, 1)
        self.assertIn('--corrections', output)


if __name__ == '__main__':
    unittest.main()
