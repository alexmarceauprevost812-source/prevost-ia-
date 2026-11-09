import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from outils.v17 import diagnostic_environnement as env


class EnvironmentTests(unittest.TestCase):
    def test_real_process_success(self):
        r = env.run_command('ok', [sys.executable, '-c', "print('mesure')"])
        self.assertEqual(r['returncode'], 0)
        self.assertEqual(r['stdout'].strip(), 'mesure')

    def test_real_process_failure(self):
        r = env.run_command('fail', [sys.executable, '-c', "import sys;print('échec',file=sys.stderr);sys.exit(7)"])
        self.assertEqual(r['returncode'], 7)
        self.assertIn('échec', r['stderr'])

    def test_absent_command_not_invented_code(self):
        r = env.run_command('missing', ['/nonexistent-prevost-command'])
        self.assertIsNone(r['returncode'])
        self.assertEqual(r['status'], 'not_started')

    def test_real_process_timeout(self):
        r = env.run_command('timeout', [sys.executable, '-c', 'import time;time.sleep(10)'], timeout=0.05)
        self.assertTrue(r['timed_out'])
        self.assertEqual(r['returncode'], -9)

    def test_fixed_commands_no_phone_mutation_or_credentials(self):
        commands = env.commands()
        adb = [argv for _, argv in commands if argv[0] == 'adb']
        self.assertEqual(adb, [['adb', 'version'], ['adb', 'devices', '-l']])
        for _, argv in commands:
            self.assertNotIn('sudo', argv)
            if argv[0] == 'curl':
                self.assertEqual(argv[1], '-q')
                self.assertIn('--head', argv)
                self.assertNotIn('--user', argv)
                self.assertNotIn('--cookie', argv)

    def test_proxy_values_are_never_recorded(self):
        with patch.dict(os.environ, {'HTTPS_PROXY': 'https://secret-personal-value.invalid'}):
            context = env.context()
        self.assertTrue(context['proxy_variables_present_only']['HTTPS_PROXY'])
        self.assertNotIn('secret-personal-value', json.dumps(context))

    def test_preserve_and_detect_changed_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'rapports').mkdir()
            old = root / 'rapports/old.txt'
            old.write_text('original')
            before = env.inventory(root)
            self.assertEqual(env.verify_inventory(root, before)['changed_or_missing'], [])
            old.write_text('changed')
            self.assertEqual(env.verify_inventory(root, before)['changed_or_missing'], ['rapports/old.txt'])

    def test_compare_measured_codes_and_hash(self):
        a = {'label': 'codex', 'started_at': 'a', 'script_sha256': '1',
             'tests': [{'id': 'adb_devices', 'returncode': 1}]}
        b = {'label': 'ubuntu', 'started_at': 'b', 'script_sha256': '1',
             'tests': [{'id': 'adb_devices', 'returncode': 0}]}
        result = env.compare(a, b)
        self.assertTrue(result['script_hashes_equal'])
        self.assertEqual(result['rows'][0], {'id': 'adb_devices', 'codex': 1, 'ubuntu': 0})

    def test_classification_dns_is_not_frp(self):
        result = env.classify([{'id': 'http_metadata_1', 'returncode': 6}])
        self.assertTrue(any('aucun statut HTTP' in s for s in result))
        self.assertTrue(any('ne prouve pas un refus FRP' in s for s in result))

    def test_classification_adb_permission(self):
        result = env.classify([{'id': 'adb_devices', 'returncode': 1, 'stderr': 'Operation not permitted'}])
        self.assertTrue(any('erreur de permission' in s for s in result))

    def test_save_exclusive_reports_and_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            report = {'label': 'codex', 'started_at': 'now', 'findings': [], 'context': {},
                      'tests': [], 'preservation': {'changed_or_missing': []}}
            p = env.save_report(report, Path(folder))
            q = env.save_report(report, Path(folder))
            self.assertNotEqual(p, q)
            self.assertEqual(json.loads(p.read_text())['label'], 'codex')
            self.assertEqual(p.with_suffix('.json.sha256').read_text().split()[0], env.digest(p))
            self.assertIn('DIAGNOSTIC ENVIRONNEMENT', p.with_suffix('.txt').read_text())

    def test_main_same_commands_local_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(env, 'ROOT', root), patch.object(env, 'commands', return_value=[('ok', [sys.executable, '--version'])]), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(env.main(['--label', 'codex']), 0)
                self.assertEqual(env.main(['--label', 'ubuntu']), 0)
            report = json.loads(next((root / 'rapports/v17').glob('environnement-ubuntu-*.json')).read_text())
            self.assertTrue(report['comparison']['script_hashes_equal'])
            self.assertEqual(report['preservation']['changed_or_missing'], [])


if __name__ == '__main__':
    unittest.main()
