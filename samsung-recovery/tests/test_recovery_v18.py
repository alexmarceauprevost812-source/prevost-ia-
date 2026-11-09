import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from outils.v18 import diagnostic_recovery as v18
from prevost_v16 import __main__ as cli


class RecoveryTests(unittest.TestCase):
    def usb(self, roles=()):
        return {'devices': [{'interfaces': [{'role': r} for r in roles]}]}

    def test_empty_adb_and_mtp_do_not_prove_frp_or_recovery(self):
        r = v18.classify(self.usb(['PTP/MTP candidat']),
                         {'returncode': 0, 'stdout': 'List of devices attached\n'})
        self.assertIn('Android probable', r['mode'])
        self.assertIn('liste vide', r['adb'])
        self.assertIn('indéterminé', r['frp'])

    def test_failed_adb_does_not_parse_untrusted_output(self):
        r = v18.classify(self.usb(), {'returncode': 1, 'stdout': 'serial sideload'})
        self.assertEqual(r['adb_states'], [])
        self.assertEqual(r['mode'], 'indéterminé')

    def test_sideload_and_multiple_devices(self):
        r = v18.classify(self.usb(), {'returncode': 0, 'stdout': 'serial sideload'})
        self.assertIn('Recovery annoncé', r['mode'])
        r = v18.classify(self.usb(), {'returncode': 0, 'stdout': 'a sideload\nb device'})
        self.assertEqual(r['mode'], 'indéterminé')

    def test_real_sysfs_fixture_and_no_adb_confusion(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            dev = root / '1-2'
            dev.mkdir()
            for key, value in {'idVendor':'04e8', 'idProduct':'6860', 'busnum':'1', 'devnum':'2'}.items():
                (dev / key).write_text(value)
            iface = dev / '1-2:1.0'
            iface.mkdir()
            for key, value in {'bInterfaceClass':'ff', 'bInterfaceSubClass':'40', 'bInterfaceProtocol':'02'}.items():
                (iface / key).write_text(value)
            r = v18.usb_interfaces(root)
            self.assertEqual(r['devices'][0]['interfaces'][0]['role'], 'autre')
            (iface / 'bInterfaceSubClass').write_text('42')
            (iface / 'bInterfaceProtocol').write_text('01')
            self.assertEqual(v18.usb_interfaces(root)['devices'][0]['interfaces'][0]['role'], 'ADB annoncé')

    def test_mounted_device_skips_session_and_preserves_reports(self):
        calls = []
        def runner(key, argv, **kwargs):
            calls.append(argv)
            return {'id': key, 'returncode': 0, 'stdout': 'mtp://host/' if key == 'mtp_mounts' else '', 'stderr': ''}
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'rapports/v17').mkdir(parents=True)
            (root / 'rapports/v17/old.txt').write_text('conserver')
            with patch.object(v18, 'usb_interfaces', return_value=self.usb()):
                report = v18.collect(root=root, runner=runner)
            self.assertEqual(report['preservation']['changed_or_missing'], [])
            self.assertEqual(calls, [['lsusb', '-d', '04e8:'], ['adb', 'devices', '-l'], ['gio', 'mount', '-li']])
            a = v18.save(report, root)
            b = v18.save(report, root)
            self.assertNotEqual(a, b)
            self.assertEqual(json.loads(a.read_text())['version'], 18)
            self.assertEqual(a.with_suffix('.json.sha256').read_text().split()[0], v18.env.digest(a))

    def test_menu_and_direct_command_route(self):
        self.assertEqual(cli.LABELS[8], 'Diagnostic Recovery V18 (USB / MTP / ADB)')
        with patch.object(v18, 'main') as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['recovery-v18']), 0)
            run.assert_called_once_with(['--label', 'local', '--delai', '15'])
        with patch('builtins.input', side_effect=['9', '0']), patch.object(v18, 'main') as run, contextlib.redirect_stdout(io.StringIO()):
            cli.main([])
            run.assert_called_once()


class ParameterTests(unittest.TestCase):
    def test_safe_parameters_reach_main_module(self):
        with patch.object(v18, 'main') as run, contextlib.redirect_stdout(io.StringIO()):
            cli.main(['recovery-v18', '--label', 'ubuntu', '--sans-adb', '--sans-mtp', '--delai', '3'])
        run.assert_called_once_with(['--label', 'ubuntu', '--delai', '3', '--sans-mtp', '--sans-adb'])

    def test_disabled_adb_does_not_run(self):
        calls = []
        def runner(key, argv, **kwargs):
            calls.append(argv)
            self.assertEqual(kwargs['timeout'], 3)
            return {'id': key, 'returncode': 0, 'stdout': '', 'stderr': ''}
        with tempfile.TemporaryDirectory() as name:
            with patch.object(v18, 'usb_interfaces', return_value={'devices': []}):
                report = v18.collect(root=Path(name), runner=runner, probe_adb=False, probe_mtp=False, timeout=3)
        self.assertFalse(any(c[0] in ('adb', 'mtp-detect') for c in calls))
        self.assertEqual(report['findings']['adb'], 'non sondé')

    def test_export_includes_v18_sources_and_latest_report(self):
        import zipfile
        from prevost_v16.core import Store
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for file in ('outils/v18/diagnostic_recovery.py', 'README-V18.md', 'rapports/v18/recovery-test.txt'):
                path = root / file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('contenu vérifié')
            store = Store(root)
            archive, checksum = store.export()
            with zipfile.ZipFile(archive) as z:
                self.assertIn('outils/v18/diagnostic_recovery.py', z.namelist())
                self.assertIn('rapports/v18/recovery-test.txt', z.namelist())
            self.assertTrue(checksum.is_file())
            with contextlib.redirect_stdout(io.StringIO()) as output:
                cli.execute('rapport', store)
            self.assertIn('contenu vérifié', output.getvalue())
