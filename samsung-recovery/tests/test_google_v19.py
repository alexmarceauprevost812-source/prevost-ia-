import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from outils.v19 import recuperation_google as v19
from prevost_v16 import __main__ as cli
from prevost_v16.core import Store


class GoogleRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        target = self.root / 'outils/v19'
        target.mkdir(parents=True)
        shutil.copy2(v19.ROOT / 'outils/v19/confirmation_utilisateur.json', target)

    def fixture(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
        return p

    def test_confirmation_has_user_provenance_and_no_invented_technical_flag(self):
        r = v19.prepare(self.root)
        self.assertTrue(r['confirmation']['confirmed_by_user'])
        self.assertEqual(r['confirmation']['screen_text'], 'Vérifier votre compte Google')
        self.assertIsNone(r['confirmation']['observation_time'])
        self.assertIn('Aucun drapeau système FRP mesuré', r['conclusion'])
        self.assertIn('utilisateur', r['confirmation']['source'])

    def test_missing_confirmation_is_not_fabricated(self):
        (self.root / 'outils/v19/confirmation_utilisateur.json').unlink()
        r = v19.prepare(self.root)
        self.assertFalse(r['confirmation']['confirmed_by_user'])
        self.assertIn('ne pas présumer', r['conclusion'])

    def test_403_empty_adb_and_mtp_are_separate_from_user_observation(self):
        self.fixture('rapports/v17/environnement-ubuntu-test.json', {'label':'ubuntu', 'tests':[
            {'id':'adb_devices', 'returncode':0, 'stdout':'List of devices attached\n'},
            {'id':'http_metadata_3', 'returncode':0, 'stdout':'HTTP/1.1 403 Forbidden\n'}]})
        self.fixture('rapports/v18/recovery-ubuntu-test.json', {'label':'ubuntu', 'usb':{'devices':[
            {'vendor_id':'04e8', 'product_id':'6860','serial':'DO_NOT_COPY_SERIAL'}]},
            'probes':[{'id':'adb','returncode':0,'stdout':'List of devices attached\n'},
                      {'id':'mtp_mounts','stdout':'mtp://DO_NOT_COPY_SERIAL/'}]})
        report = v19.prepare(self.root)
        a, b = [e['analysis'] for e in report['evidence']]
        self.assertEqual(a['bmc_http_statuses'], ['403'])
        self.assertTrue(a['adb_list_empty'])
        self.assertTrue(b['mtp_mount_announced'])
        self.assertNotIn('DO_NOT_COPY_SERIAL', json.dumps(report))
        self.assertIn('Observation utilisateur distincte', report['limits'])

    def test_unreadable_json_not_silently_ignored(self):
        p = self.fixture('rapports/v17/environnement-broken.json', {})
        p.write_text('{')
        r = v19.prepare(self.root)
        self.assertEqual(r['evidence'][0]['analysis_error'], 'JSONDecodeError')

    def test_no_process_socket_browser_or_phone_used(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('accès externe interdit pour V19')
        with patch('subprocess.Popen', side_effect=forbidden), patch('subprocess.run', side_effect=forbidden), \
             patch('socket.socket', side_effect=forbidden), patch('webbrowser.open', side_effect=forbidden), \
             patch('prevost_v16.core.Diagnostics.run', side_effect=forbidden), \
             contextlib.redirect_stdout(io.StringIO()):
            out = v19.run(self.root, 'bell')
        self.assertTrue((out / 'brouillon-bell.txt').is_file())

    def test_unique_outputs_checksums_and_preservation(self):
        old = self.fixture('rapports/v17/environnement-test.json', {'tests':[]})
        before = old.read_bytes()
        r = v19.prepare(self.root)
        a = v19.save(r, self.root)
        b = v19.save(r, self.root)
        self.assertNotEqual(a, b)
        self.assertEqual(old.read_bytes(), before)
        self.assertEqual(r['preservation']['changed_or_missing'], [])
        for line in (a / 'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ')
            self.assertEqual(digest, v19.digest(a / name))
        self.assertIn('Aucun drapeau système FRP mesuré', (a / 'rapport.md').read_text())

    def test_section_and_full_saved_report(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            out = v19.run(self.root, 'bell')
        self.assertIn('## Bell', output.getvalue())
        self.assertNotIn('## Android', output.getvalue())
        self.assertIn('## Android', (out / 'rapport.md').read_text())
        self.assertIn('aucun effacement', (out / 'brouillon-samsung.txt').read_text().lower())

    def test_menu_10_cli_and_report_view_use_v19(self):
        self.assertEqual(cli.LABELS[9], 'Récupération Google FRP')
        with patch.object(cli, 'Store', return_value=Store(self.root)), \
             contextlib.redirect_stdout(io.StringIO()), patch.object(v19, 'run') as run:
            self.assertEqual(cli.main(['google-frp', '--section', 'samsung']), 0)
            run.assert_called_once_with(self.root, section='samsung')
        with patch('builtins.input', side_effect=['10','0']), patch.object(v19, 'run') as run, \
             contextlib.redirect_stdout(io.StringIO()):
            cli.tui(Store(self.root), google_section='bell')
            run.assert_called_once_with(self.root, section='bell')
        v19.save(v19.prepare(self.root), self.root)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            cli.execute('rapport', Store(self.root))
        self.assertIn('PRÉVOST V19', output.getvalue())

    def test_watch_is_rejected_for_account_guide(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.main(['google-frp', '--watch', '2'])
        self.assertEqual(error.exception.code, 2)

    def test_export_keeps_previous_versions_and_includes_v19(self):
        for name in ('outils/v19/recuperation_google.py','README-V19.md',
                     'rapports/v17/old.txt','rapports/v18/old.txt','rapports/v19/dossier-example/rapport.md'):
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('conserver')
        archive, checksum = Store(self.root).export()
        self.assertTrue(archive.name.startswith('prevost-samsung-v20-'))
        with zipfile.ZipFile(archive) as z:
            for name in ('outils/v19/recuperation_google.py', 'outils/v19/confirmation_utilisateur.json',
                         'README-V19.md','rapports/v17/old.txt','rapports/v18/old.txt',
                         'rapports/v19/dossier-example/rapport.md'):
                self.assertIn(name, z.namelist())
        self.assertTrue(checksum.is_file())
