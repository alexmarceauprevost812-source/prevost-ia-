import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time
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

    def test_two_different_checks_for_the_same_file_are_refused_before_writing(self):
        # Cas réel observé avec qwen3:8b : un programme sans argument n'a qu'une sortie.
        contradictory = json.dumps({'files': [{'path': 'p.py', 'content': 'print("ok")\n'}],
            'checks': [{'path': 'p.py', 'expected_stdout': 'ok\n'}, {'path': 'p.py', 'expected_stdout': 'Erreur\n'}]})
        model = Script(contradictory, plan())
        result = self.run_mission(model)
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertEqual(len(self.written_proposals()), 1)
        self.assertIn('Deux contrôles différents pour p.py', model.calls[1][-1]['content'])
        # Deux contrôles identiques restent acceptés.
        same = json.dumps({'files': [{'path': 'p.py', 'content': 'print("ok")\n'}],
            'checks': [{'path': 'p.py', 'expected_stdout': 'ok\n'}] * 2})
        model = Script(same)
        self.assertEqual(self.run_mission(model)['status'], 'double_verification_reussie')
        self.assertEqual(len(model.calls), 1)

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

    def test_slow_human_confirmation_does_not_eat_the_execution_budget(self):
        # Régression : lire le code avant de répondre « oui » ne doit pas faire expirer le contrôle.
        def slow_confirm(text):
            self.proposals.append(text)
            if text.startswith('Action sensible'):
                time.sleep(1.8)
            return True
        self.ui.confirm = slow_confirm
        result = self.run_mission(Script(plan()), timeout=1.5)
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertEqual(self.outcomes(), ['double_verification_reussie'])

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

    # --- Suites du test réel du 9 nov. : « \\n » final, message exact, fichier identique ------------

    def test_missing_final_newline_in_announced_output_is_accepted(self):
        result = self.run_mission(Script(plan(expected='ok')))
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertEqual(result['attempts'], 1)

    def test_only_one_missing_final_newline_is_tolerated(self):
        from prevost.tools import same_output
        self.assertTrue(same_output('ok\n', 'ok\n'))
        self.assertTrue(same_output('ok\n', 'ok'))
        self.assertFalse(same_output('ok\n\n', 'ok'))   # deux sauts de ligne réels : pas la même sortie
        self.assertFalse(same_output('ok', 'ok\n'))     # l’annonce ajoute un saut qui n’existe pas
        self.assertFalse(same_output('ok\n', 'okk'))
        self.assertFalse(same_output('a\nb\n', 'a\nc'))
        self.assertFalse(same_output('', 'x'))

    def test_wrong_output_still_fails_even_without_final_newline(self):
        result = self.run_mission(Script(plan(code='print("ok\\n")\n', expected='ok')), corrections=0)
        self.assertNotEqual(result['status'], 'double_verification_reussie')
        self.assertEqual(self.outcomes(), ['echec'])

    def test_interruption_after_an_earlier_write_does_not_claim_nothing_was_written(self):
        model = Script(plan(expected='faux\n'), 'pas du json', 'toujours pas du json')
        self.assertIsNone(self.run_mission(model, corrections=2))
        self.assertTrue((self.root/'p.py').exists())
        self.assertIn('fichiers déjà écrits par les tentatives précédentes : p.py', self.output)
        self.assertIn('/annuler FICHIER', self.output)
        self.assertNotIn('Rien n’a été écrit', self.output)
        self.assertEqual(self.outcomes(), ['plan_invalide'])

    def test_identical_file_needs_no_confirmation_and_makes_no_backup(self):
        self.assertTrue(self.project.write('p.py', 'a = 1\n', self.confirm))
        self.assertEqual(len(self.proposals), 1)
        self.assertTrue(self.project.write('p.py', 'a = 1\n', self.confirm))
        self.assertEqual(len(self.proposals), 1)           # aucune nouvelle confirmation
        self.assertEqual(self.project.backups('p.py'), [])  # aucune sauvegarde inutile

    def test_identical_file_is_shown_as_unchanged_and_not_asked_in_a_mission(self):
        from prevost.app import describe_plan
        (self.root/'p.py').write_text('print("ok")\n', encoding='utf-8')
        files = [{'path': 'p.py', 'content': 'print("ok")\n'}]
        self.assertIn('p.py : inchangé', describe_plan(self.project, files, [], []))
        result = self.run_mission(Script(plan()))
        self.assertEqual(result['status'], 'double_verification_reussie')
        self.assertIn('identique à la version actuelle, rien à écrire', self.output)
        self.assertEqual(self.written_proposals(), [])
        self.assertEqual(self.project.backups('p.py'), [])

    def test_restoring_a_backup_identical_to_the_file_does_nothing(self):
        self.project.write('p.py', 'v1\n', self.confirm)
        self.project.write('p.py', 'v2\n', self.confirm)
        self.project.write('p.py', 'v1\n', self.confirm)
        found = self.project.backups('p.py')               # [v2, v1] : le fichier actuel vaut v1
        before = len(self.proposals)
        self.assertIsNone(self.project.restore('p.py', found[1], self.confirm))
        self.assertEqual(len(self.proposals), before)
        self.assertEqual((self.root/'p.py').read_text(encoding='utf-8'), 'v1\n')


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

    def test_coder_without_a_request_is_refused_before_calling_the_model(self):
        with patch('prevost.app.code_mission') as mission:
            status, output = self.session(['/coder', '/coder   ', '/quitter'])
        self.assertEqual(status, 0)
        mission.assert_not_called()
        self.assertEqual(output.count('Usage : /coder DEMANDE'), 2)

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
