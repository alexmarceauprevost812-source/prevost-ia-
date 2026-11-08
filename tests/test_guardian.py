import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from prevost.guardian import CHECKS, Watch, canonical, collect, probe, recommendations


class GuardianTests(unittest.TestCase):
    def report(self):
        return {'date': 'test', 'controles': {
            'disque': {'status': 'observe', 'pourcentage_libre': 50},
            'ports': {'status': 'observe', 'sortie': 'tcp LISTEN 0 128 127.0.0.1:1234 *:*\n'},
            'services': {'status': 'observe', 'sortie': ''}}}

    def test_netlink_refusal_even_exit_zero(self):
        response = subprocess.CompletedProcess([], 0, '', 'Cannot open netlink socket: Operation not permitted')
        with patch('prevost.guardian.subprocess.run', return_value=response):
            self.assertEqual(probe(['ss'])['status'], 'indisponible')

    def test_missing_program(self):
        with patch('prevost.guardian.subprocess.run', side_effect=FileNotFoundError('absent')):
            self.assertEqual(probe(['absent'])['status'], 'indisponible')

    def test_dedup_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            watcher = Watch(directory)
            report = self.report()
            self.assertEqual(watcher.update(report), [])
            changed = copy.deepcopy(report)
            changed['controles']['ports']['sortie'] += 'udp UNCONN 0 0 127.0.0.1:5678 *:*\n'
            self.assertEqual(len(watcher.update(changed)), 1)
            self.assertEqual(Watch(directory).update(changed), [])
            entries = [json.loads(line) for line in watcher.journal.read_text().splitlines()]
            self.assertEqual(sum(row['type'] == 'alerte' for row in entries), 1)
            self.assertEqual(watcher.state.stat().st_mode & 0o777, 0o600)

    def test_initial_failure_alert_and_no_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.report()
            report['controles']['ports'] = {'status': 'indisponible', 'erreur': 'refus'}
            watcher = Watch(directory)
            self.assertEqual(len(watcher.update(report)), 1)
            self.assertEqual(watcher.update(report), [])
            rec = recommendations(report)
            self.assertIn('santé inconnue', rec[0]['constat'])
            self.assertIn('Aucun changement', rec[0]['retour_arriere'])

    def test_disk_threshold_and_stable_order(self):
        a = {'status': 'observe', 'sortie': 'a\nb\n'}
        b = {'status': 'observe', 'sortie': 'b\na\n'}
        self.assertEqual(canonical('ports', a), canonical('ports', b))
        self.assertFalse(canonical('disque', {'status': 'observe', 'pourcentage_libre': 50})['espace_faible'])
        self.assertTrue(canonical('disque', {'status': 'observe', 'pourcentage_libre': 5})['espace_faible'])

    def test_only_fixed_local_commands(self):
        calls = []
        def run(argv):
            calls.append(argv)
            return {'status': 'observe', 'sortie': ''}
        report = collect(run=run)
        self.assertEqual(calls, list(CHECKS.values()))
        self.assertEqual(report['appareil']['id'], 'pc-local')
        self.assertIn('non explorés', report['appareil']['reseaux_voisins'])


if __name__ == '__main__':
    unittest.main()
