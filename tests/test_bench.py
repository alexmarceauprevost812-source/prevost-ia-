import contextlib
import io
import json
import sys
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

    def models(self):
        return self.models_

    def chat(self, model, messages, structured=False):
        text = ' '.join(m['content'] for m in messages)
        if model == 'mauvais':
            yield json.dumps({'files': [], 'commands': [], 'checks': []})
            return
        for key, plan in GOOD.items():
            if f'{key}.py' in text or (key == 'calcul' and 'additionner' in text) or (key == 'taches' and 'GestionnaireTaches' in text):
                yield json.dumps(plan)
                return
        yield json.dumps({'files': [], 'commands': [], 'checks': []})


class BenchTests(unittest.TestCase):
    def run_bench(self, answer, models=('bon',), client=None):
        ui = UI()
        ui.color = False
        prompts = []
        ui.read = lambda prompt='': (prompts.append(prompt), answer)[1]
        client = client or FakeClient(['bon', 'mauvais'])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = bench.main([a for m in models for a in ('--model', m)], ui=ui, client=client)
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
        import tempfile
        with tempfile.TemporaryDirectory() as base:
            good = bench.run_model(client, 'bon', base, 30)
            bad = bench.run_model(client, 'mauvais', base, 30)
        self.assertTrue(all(good.values()), [k for k, v in good.items() if not v])
        self.assertFalse(any(bad.values()))

    def test_missions_run_silently_without_progress_dots(self):
        import tempfile
        client = FakeClient(['bon'])
        with tempfile.TemporaryDirectory() as base, contextlib.redirect_stdout(io.StringIO()) as out:
            bench.run_model(client, 'bon', base, 30)
        self.assertEqual(out.getvalue(), '')

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
