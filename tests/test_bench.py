import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from prevost import bench
from prevost.app import UI, main

GOOD = {
    'bonjour': {'files': [{'path': 'bonjour.py', 'content': 'print("Bonjour PRÉVOST")\n'}], 'commands': [[sys.executable, 'bonjour.py']],
                'checks': [{'path': 'bonjour.py', 'expected_stdout': 'Bonjour PRÉVOST\n'}]},
    'calcul': {'files': [{'path': 'calcul.py', 'content': 'def additionner(a, b):\n    return a + b\n'},
                         {'path': 'test_calcul.py', 'content': 'import unittest\nfrom calcul import additionner\n\n'
                          'class T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(additionner(2, 3), 5)\n'}],
               'commands': [[sys.executable, '-m', 'unittest', 'test_calcul']],
               'checks': [{'path': 'calcul.py', 'expected_stdout': ''}, {'path': 'test_calcul.py', 'expected_stdout': ''}]},
    'premiers': {'files': [{'path': 'premiers.py', 'content':
                 'def est_premier(n):\n    return n > 1 and all(n % i for i in range(2, int(n ** .5) + 1))\n\n'
                 'if __name__ == "__main__":\n    n = 0\n    for k in range(2, 100):\n        if est_premier(k) and n < 10:\n'
                 '            print(k)\n            n += 1\n'}], 'commands': [],
                 'checks': [{'path': 'premiers.py', 'expected_stdout': '2\n3\n5\n7\n11\n13\n17\n19\n23\n29\n'}]},
    'taches': {'files': [{'path': 'taches.py', 'content':
               'class GestionnaireTaches:\n    def __init__(self):\n        self.t = []\n'
               '    def ajouter(self, titre):\n        self.t.append({"id": len(self.t) + 1, "titre": titre, "termine": False})\n'
               '        return len(self.t)\n    def terminer(self, i):\n        self.t[i - 1]["termine"] = True\n'
               '    def lister(self):\n        return [dict(x) for x in self.t]\n'},
               {'path': 'test_taches.py', 'content': 'import unittest\nfrom taches import GestionnaireTaches\n\n'
                'class T(unittest.TestCase):\n    def test_a(self):\n        g = GestionnaireTaches()\n'
                '        i = g.ajouter("a")\n        g.terminer(i)\n        self.assertTrue(g.lister()[0]["termine"])\n'}],
               'commands': [[sys.executable, '-m', 'unittest', 'test_taches']],
               'checks': [{'path': 'taches.py', 'expected_stdout': ''}, {'path': 'test_taches.py', 'expected_stdout': ''}]},
}


class FakeClient:
    """Modèle simulé : le bon plan pour la mission reconnue dans la demande, ou un plan vide pour « mauvais »."""
    local = True

    def __init__(self, models):
        self.models_ = models
        self.chat_calls = 0

    def models(self):
        return self.models_

    @staticmethod
    def mission(text):
        for key in GOOD:
            if f'{key}.py' in text or (key == 'calcul' and 'additionner' in text) or (key == 'taches' and 'GestionnaireTaches' in text):
                return key
        return None

    def plan(self, model, text):
        key = self.mission(text)
        if model == 'mauvais' or key is None:
            return {'files': [], 'commands': [], 'checks': []}
        return GOOD[key]

    def chat(self, model, messages, structured=False):
        self.chat_calls += 1
        yield json.dumps(self.plan(model, ' '.join(m['content'] for m in messages)))


class FaultyClient(FakeClient):
    """Un modèle qui se trompe à chaque mission : mauvaise sortie, test qui échoue, fonction fausse, classe sans méthodes."""
    def plan(self, model, text):
        key = self.mission(text)
        plan = copy.deepcopy(super().plan('bon', text))
        if key == 'bonjour':
            plan['files'][0]['content'] = 'print("Salut")\n'
        elif key == 'calcul':
            plan['files'][1]['content'] = plan['files'][1]['content'].replace('5)', '6)')
        elif key == 'premiers':
            plan['files'][0]['content'] = 'def est_premier(n):\n    return True\n'
        elif key == 'taches':
            plan['files'][0]['content'] = 'class GestionnaireTaches:\n    pass\n'
        return plan


class FlakyClient(FaultyClient):
    """Se trompe pendant tout le premier essai de chaque mission (proposition initiale et deux corrections), puis réussit."""
    def __init__(self, models):
        super().__init__(models)
        self.calls = {}

    def plan(self, model, text):
        key = self.mission(text)
        self.calls[key] = self.calls.get(key, 0) + 1
        return super().plan(model, text) if self.calls[key] <= 3 else FakeClient.plan(self, 'bon', text)


class BenchTests(unittest.TestCase):
    def run_bench(self, answer, models=('bon',), client=None, extra=()):
        ui = UI()
        ui.color = False
        prompts = []
        ui.read = lambda prompt='': (prompts.append(prompt), answer)[1]
        client = client or FakeClient(['bon', 'mauvais'])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = bench.main([a for m in models for a in ('--model', m)] + list(extra), ui=ui, client=client)
        return code, out.getvalue(), prompts

    def test_single_explicit_confirmation_then_real_table(self):
        code, text, prompts = self.run_bench('oui', ('bon', 'mauvais'))
        self.assertEqual(code, 0)
        self.assertEqual(len(prompts), 1)
        self.assertIn('une seule confirmation', text)
        self.assertIn('bonjour — sortie exacte « Bonjour PRÉVOST »', text)
        good_rows = [line for line in text.splitlines() if line.startswith('Total')]
        self.assertEqual(len(good_rows), 1)
        self.assertRegex(good_rows[0], r'Total\s+\| 19/19\s+\| 0/19')
        self.assertIn('ÉCHEC', text)
        self.assertEqual(text.count('OK') >= 4, True)

    def test_bad_model_fails_every_criterion_and_good_model_passes_independent_checks(self):
        client = FakeClient(['bon', 'mauvais'])
        with tempfile.TemporaryDirectory() as base:
            good = bench.run_model(client, 'bon', base, 30)
            bad = bench.run_model(client, 'mauvais', base, 30)
        self.assertEqual(len(good), 19)
        # '' = critère satisfait ; sinon la raison de l'échec
        self.assertEqual([k for k, reasons in good.items() if reasons != ['']], [])
        self.assertEqual([k for k, reasons in bad.items() if len(reasons) != 1 or not reasons[0]], [])

    def test_missions_run_silently_without_progress_dots(self):
        client = FakeClient(['bon'])
        with tempfile.TemporaryDirectory() as base, contextlib.redirect_stdout(io.StringIO()) as out:
            bench.run_model(client, 'bon', base, 30)
        self.assertEqual(out.getvalue(), '')

    def test_failures_come_with_the_real_reason(self):
        with tempfile.TemporaryDirectory() as base:
            results = bench.run_model(FaultyClient(['faux']), 'faux', base, 30)
        reason = lambda mission, label: results[(mission, label)][0]
        self.assertEqual(reason('bonjour', 'fichier bonjour.py créé'), '')
        self.assertIn("'Salut\\n'", reason('bonjour', 'sortie exacte « Bonjour PRÉVOST »'))
        self.assertIn("'Bonjour PRÉVOST\\n'", reason('bonjour', 'sortie exacte « Bonjour PRÉVOST »'))
        self.assertIn('AssertionError: 5 != 6', reason('calcul', 'tests unitaires réussis'))
        self.assertIn("no attribute 'ajouter'", reason('taches', 'ajouter, lister et terminer fonctionnent'))
        self.assertIn('AttributeError', reason('taches', 'tests unitaires réussis'))
        self.assertEqual(reason('calcul', 'syntaxe valide'), '')
        # contrôle interne : la raison dit pourquoi le bilan n'est pas « réussi » et ce que PRÉVOST a constaté
        internal = reason('taches', 'contrôle interne du modèle réussi')
        self.assertIn('pas de bilan', internal)
        self.assertIn('AttributeError', internal)
        self.assertIn('Salut', reason('bonjour', 'contrôle interne du modèle réussi'))

    def test_missing_files_are_reported_as_missing_not_as_python_errors(self):
        with tempfile.TemporaryDirectory() as base:
            results = bench.run_model(FakeClient(['mauvais']), 'mauvais', base, 30)
        self.assertEqual(results[('bonjour', 'fichier bonjour.py créé')], ['fichier absent : bonjour.py'])
        self.assertEqual(results[('bonjour', 'sortie exacte « Bonjour PRÉVOST »')], ['bonjour.py absent'])
        self.assertEqual(results[('calcul', 'tests unitaires réussis')], ['test_calcul.py absent'])
        self.assertIn('sans_modification', results[('premiers', 'contrôle interne du modèle réussi')][0])
        self.assertNotIn('/tmp', ''.join(r for reasons in results.values() for r in reasons))

    def test_a_mission_that_raises_fails_its_criteria_with_the_error(self):
        class Broken(FakeClient):
            def chat(self, model, messages, structured=False):
                raise RuntimeError('Ollama injoignable')
                yield

        with tempfile.TemporaryDirectory() as base:
            results = bench.run_model(Broken(['x']), 'x', base, 30)
        self.assertIn('mission en erreur : RuntimeError : Ollama injoignable',
                      results[('bonjour', 'contrôle interne du modèle réussi')][0])
        self.assertTrue(all(reasons[0] for reasons in results.values()))

    def test_failure_report_is_printed_after_the_table(self):
        code, text, _ = self.run_bench('oui', ('bon', 'mauvais'))
        self.assertEqual(code, 0)
        self.assertIn('Raisons des échecs — mauvais', text)
        self.assertNotIn('Raisons des échecs — bon', text)
        self.assertIn('fichier absent : bonjour.py', text)
        self.assertLess(text.index('Total'), text.index('Raisons des échecs'))

    def test_no_failure_section_when_everything_passes(self):
        code, text, _ = self.run_bench('oui', ('bon',))
        self.assertEqual(code, 0)
        self.assertNotIn('Raisons des échecs', text)

    def test_progress_lines_are_printed_for_each_mission(self):
        code, text, _ = self.run_bench('oui', ('bon',))
        self.assertIn('Modèle bon : 4 missions × 1 essai(s)', text)
        for name, total in (('bonjour', 4), ('calcul', 5), ('premiers', 5), ('taches', 5)):
            self.assertIn(f'  {name}…', text)
            self.assertRegex(text, rf'  {name} : {total}/{total} critères en \d+ s')
        self.assertLess(text.index('  bonjour…'), text.index('  taches : 5/5'))
        self.assertLess(text.index('  taches : 5/5'), text.index('Critère'))

    def test_progress_is_flushed_so_redirected_output_shows_it_live(self):
        class Spy(io.StringIO):
            flushes = 0

            def flush(self):
                Spy.flushes += 1
                super().flush()

        ui = UI()
        ui.color = False
        ui.read = lambda prompt='': 'oui'
        with contextlib.redirect_stdout(Spy()):
            bench.main(['--model', 'bon'], ui=ui, client=FakeClient(['bon']))
        self.assertGreaterEqual(Spy.flushes, 9)  # 1 ligne de modèle + 2 par mission

    def test_several_trials_give_a_success_rate(self):
        client = FakeClient(['bon'])
        code, text, prompts = self.run_bench('oui', ('bon',), client=client, extra=('--essais', '3'))
        self.assertEqual(code, 0)
        self.assertEqual(len(prompts), 1)
        self.assertIn('3 essai(s) par mission', text)
        self.assertIn('bonjour (essai 3/3)', text)
        self.assertRegex(text, r'bonjour — sortie exacte « Bonjour PRÉVOST »\s+\| 3/3')
        self.assertRegex(text, r'Total\s+\| 57/57 \(100 %\)')
        self.assertIn('  bon — bonjour 3/3, calcul 3/3, premiers 3/3, taches 3/3', text)
        self.assertNotIn('OK', [cell.strip() for line in text.splitlines() for cell in line.split('|')])
        self.assertEqual(client.chat_calls, 12)  # 4 missions × 3 essais, aucune correction nécessaire

    def test_flaky_model_gets_a_partial_rate_and_grouped_reasons(self):
        client = FlakyClient(['capricieux'])
        code, text, _ = self.run_bench('oui', ('capricieux',), client=client, extra=('--essais', '2'))
        self.assertEqual(code, 0)
        self.assertRegex(text, r'bonjour — fichier bonjour\.py créé\s+\| 2/2')
        self.assertRegex(text, r'bonjour — sortie exacte « Bonjour PRÉVOST »\s+\| 1/2')
        self.assertRegex(text, r'Total\s+\| 28/38 \(74 %\)')
        self.assertIn('  capricieux — bonjour 1/2, calcul 1/2, premiers 1/2, taches 1/2', text)
        self.assertIn("essai 1 : sortie obtenue 'Salut\\n'", text)
        self.assertNotIn('essai 2 :', text)
        self.assertNotIn('essais 1, 2', text)

    def test_identical_reasons_are_grouped_across_trials(self):
        client = FakeClient(['mauvais'])
        code, text, _ = self.run_bench('oui', ('mauvais',), client=client, extra=('--essais', '2'))
        self.assertIn('essais 1, 2 : fichier absent : bonjour.py', text)
        self.assertEqual(text.count('fichier absent : bonjour.py'), 1)

    def test_each_trial_runs_in_a_fresh_folder_with_its_own_state(self):
        folders = []
        real = bench.Project

        def spy(folder, state=None):
            folders.append((Path(folder), Path(state)))
            return real(folder, state=state)

        with patch('prevost.bench.Project', side_effect=spy), tempfile.TemporaryDirectory() as base:
            bench.run_model(FakeClient(['bon']), 'bon', base, 30, trials=2)
        self.assertEqual(len(folders), 8)
        self.assertEqual(len({f for f, _ in folders}), 8)
        self.assertEqual(len({s for _, s in folders}), 8)

    def test_trial_count_is_validated_before_any_confirmation(self):
        for bad in ('0', '11', '-1'):
            with self.subTest(essais=bad):
                code, text, prompts = self.run_bench('oui', ('bon',), extra=('--essais', bad))
                self.assertEqual(code, 1)
                self.assertEqual(prompts, [])
                self.assertIn('Nombre d’essais requis : de 1 à 10', text)

    def test_one_trial_by_default_suggests_confirming_with_more(self):
        _, text, _ = self.run_bench('oui', ('bon',))
        self.assertIn('--essais 3', text)
        _, text, _ = self.run_bench('oui', ('bon',), extra=('--essais', '2'))
        self.assertNotIn('--essais 3', text)

    def test_refusal_runs_nothing(self):
        for answer in ('non', 'Oui', 'OUI', 'o', ''):
            with self.subTest(answer=answer), patch('prevost.bench.run_model') as run:
                code, text, _ = self.run_bench(answer)
                self.assertEqual(code, 1)
                run.assert_not_called()
                self.assertIn('refusé', text)

    def test_unknown_model_is_rejected_before_confirmation(self):
        code, text, prompts = self.run_bench('oui', ('inconnu',))
        self.assertEqual(code, 1)
        self.assertEqual(prompts, [])
        self.assertIn('Modèle absent', text)

    def test_model_all_and_dispatch_from_main(self):
        with patch('prevost.bench.main', return_value=0) as bench_main:
            self.assertEqual(main(['bench', '--model', 'x']), 0)
        bench_main.assert_called_once_with(['--model', 'x'])
        code, text, _ = self.run_bench('oui', ('tous',))
        self.assertIn('bon', text)
        self.assertIn('mauvais', text)
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
