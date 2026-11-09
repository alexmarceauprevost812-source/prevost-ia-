import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from prevost_v16.core import Diagnostics, Runner, Store, interpret, parse_adb, sha256, read, PROPERTIES, SETTINGS
from prevost_v16.__main__ import main, tui, paint, execute


def ok(value=''):
    return {'status': 'ok', 'output': value, 'code': 0}


class FakeRunner:
    def __init__(self, states='ABC device usb:1-2 model:SM_G990W2', maker='samsung', model='SM-G990W2'):
        self.states, self.maker, self.model = states, maker, model
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args == ['adb', 'devices', '-l']:
            return ok('List of devices attached\n' + self.states + '\n')
        if args == ['gio', 'mount', '-li']:
            return ok('Mount(0): SAMSUNG -> mtp://SAMSUNG_ABC/\nMount(1): disk -> file:///secret')
        if args[4] == 'getprop':
            return ok({'ro.product.manufacturer': self.maker, 'ro.product.model': self.model,
                       'ro.build.version.release': '16', 'ro.frp.pst': '/dev/block/frp',
                       'ro.bootmode': 'normal'}.get(args[5], ''))
        return ok('1' if args[-1] == 'secure_frp_mode' else '0')


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sysfs = self.root / 'sysfs'
        self.sysfs.mkdir()
        device = self.sysfs / '1-2'
        device.mkdir()
        for name, value in {'idVendor': '04e8', 'idProduct': '6860', 'serial': 'ABC',
                            'manufacturer': 'Samsung', 'product': 'SAMSUNG Android'}.items():
            (device / name).write_text(value)
        interface = self.sysfs / '1-2:1.0'
        interface.mkdir()
        for name, value in {'bInterfaceClass': '06', 'bInterfaceSubClass': '01',
                            'bInterfaceProtocol': '01'}.items():
            (interface / name).write_text(value)
        self.runner = FakeRunner()
        self.diag = Diagnostics(self.runner, self.sysfs)

    def tearDown(self):
        self.tmp.cleanup()

    def test_usb_descriptors_without_model_invention(self):
        result = self.diag.usb()
        self.assertEqual(result['devices'][0]['product_id'], '6860')
        self.assertNotIn('model', result['devices'][0])
        self.assertEqual(result['devices'][0]['interfaces'][0]['bInterfaceClass'], '06')

    def test_usb_missing(self):
        self.assertEqual(Diagnostics(self.runner, self.root / 'missing').usb()['status'], 'inaccessible')

    def test_unrelated_vendor_ignored(self):
        (self.sysfs / '1-2/idVendor').write_text('1234')
        self.assertEqual(self.diag.usb()['devices'], [])

    def test_mtp_association_and_no_local_disks(self):
        result = self.diag.mtp(self.diag.usb())
        self.assertEqual(result['mounts'][0]['samsung_ports'], ['1-2'])
        self.assertNotIn('secret', json.dumps(result))
        self.assertEqual(result['image_interface_clues'], ['1-2'])

    def test_mtp_bus_address_gvfs(self):
        (self.sysfs / '1-2/busnum').write_text('3')
        (self.sysfs / '1-2/devnum').write_text('25')
        self.diag.runner = lambda args: ok('mtp://[usb:003,025]/')
        result = self.diag.mtp(self.diag.usb())
        self.assertEqual(result['mounts'][0]['samsung_ports'], ['1-2'])
        self.assertEqual(result['mounts'][0]['association'], 'adresse_usb')

    def test_mtp_does_not_match_partial_serial(self):
        self.diag.runner = lambda args: ok('mtp://SAMSUNG_ABCD/')
        result = self.diag.mtp(self.diag.usb())
        self.assertEqual(result['mounts'][0]['samsung_ports'], [])

    def test_mtp_empty_does_not_claim_storage_access(self):
        self.diag.runner = lambda args: ok('')
        result = self.diag.mtp(self.diag.usb())
        self.assertEqual(result['mounts'], [])

    def test_identification_confirmed_and_frp_indeterminate(self):
        result = self.diag.run()
        self.assertTrue(result['identification']['match'])
        self.assertEqual(result['identification']['confidence'], 'elevee_proprietes_android')
        self.assertEqual(result['android']['properties']['ro.build.version.release']['value'], '16')
        self.assertTrue(result['frp_setup']['clues'])
        self.assertIn('indéterminée', result['frp_setup']['conclusion'])
        self.assertIn('global.secure_frp_mode', result['android']['settings'])

    def test_wrong_model(self):
        self.runner.model = 'SM-OTHER'
        self.assertFalse(self.diag.run()['identification']['match'])

    def test_non_samsung_not_collected(self):
        self.runner.maker = 'other'
        report = self.diag.run()
        self.assertEqual(report['android']['status'], 'fabricant_non_confirme')
        self.assertFalse(report['android']['settings'])
        self.assertEqual(len([c for c in self.runner.calls if 'getprop' in c]), 2)

    def test_no_adb_does_not_reuse_old_reports(self):
        self.runner.states = ''
        report = self.diag.run()
        self.assertIsNone(report['identification']['observed_model'])
        self.assertEqual(report['android']['properties'], {})

    def test_unauthorized_and_offline_never_shell(self):
        for state in ('unauthorized', 'offline', 'sideload', 'no permissions'):
            runner = FakeRunner('ABC ' + state + ' usb:1-2')
            report = Diagnostics(runner, self.sysfs).run()
            self.assertFalse(any('shell' in call for call in runner.calls))
            self.assertFalse(report['android']['settings'])

    def test_multiple_devices_requires_selection(self):
        self.runner.states += '\nDEF device model:SM_G990W2'
        self.assertEqual(self.diag.run()['android']['status'], 'selection_ambigue')
        self.assertEqual(self.diag.run('ABC')['android']['status'], 'ok')

    def test_explicit_selection_not_found(self):
        self.assertEqual(self.diag.run('MISSING')['android']['status'], 'aucun_adb_samsung_associe')

    def test_recovery_does_not_query_settings(self):
        self.runner.states = 'ABC recovery usb:1-2'
        report = self.diag.run()
        self.assertEqual(report['recovery']['confirmed_adb'], ['ABC'])
        self.assertFalse(report['android']['settings'])

    def test_sideload_distinct(self):
        self.runner.states = 'ABC sideload usb:1-2'
        result = self.diag.run()['recovery']
        self.assertEqual(result['sideload'], ['ABC'])
        self.assertFalse(result['confirmed_adb'])

    def test_missing_tools_logged(self):
        self.diag.runner = lambda args: {'status': 'outil_absent', 'output': '', 'code': None}
        report = self.diag.run()
        self.assertEqual(len(report['errors']), 2)
        self.assertIsNone(report['identification']['match'])

    def test_denied_empty_null_values(self):
        for output, expected in [('Permission denial: blocked', 'refuse_ou_invalide'),
                                 ('null', 'non_disponible'), ('', 'non_disponible'),
                                 ('x\ny', 'refuse_ou_invalide')]:
            self.diag.runner = lambda args: ok(output)
            self.assertEqual(self.diag.value('ABC', 'getprop', 'ro.product.model')['status'], expected)

    def test_phone_commands_are_read_only_allowlist(self):
        self.diag.run()
        for call in self.runner.calls:
            if call[:1] == ['gio']:
                self.assertEqual(call, ['gio', 'mount', '-li'])
            elif 'shell' in call:
                self.assertEqual(call[:4], ['adb', '-s', 'ABC', 'shell'])
                if call[4] == 'getprop':
                    self.assertIn(call[5], PROPERTIES)
                    self.assertEqual(len(call), 6)
                else:
                    self.assertEqual(call[4:6], ['settings', 'get'])
                    self.assertIn(tuple(call[6:]), SETTINGS)
            else:
                self.assertEqual(call, ['adb', 'devices', '-l'])

    def test_history_reports_preservation_export(self):
        legacy = self.root / 'rapports/v13/History'
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b'legacy sensitive contents')
        store = Store(self.root)
        first = store.save(self.diag.run())
        second = store.save(self.diag.run())
        self.assertNotEqual(first, second)
        self.assertEqual(len(store.history().splitlines()), 2)
        self.assertIn('PRÉVOST', first.with_suffix('.txt').read_text())
        self.assertEqual(len(store.reports()), 2)
        archive, checksum = store.export()
        self.assertEqual(checksum.read_text().split()[0], sha256(archive))
        with zipfile.ZipFile(archive) as z:
            self.assertNotIn('rapports/v13/History', z.namelist())
            for name, digest in json.loads(z.read('MANIFEST-SHA256.json')).items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)
        self.assertEqual(legacy.read_bytes(), b'legacy sensitive contents')

    def test_error_journal(self):
        self.diag.runner = lambda args: {'status': 'delai_depasse', 'output': '', 'code': None}
        store = Store(self.root)
        store.save(self.diag.run())
        errors = [json.loads(line) for line in (store.directory / 'erreurs.jsonl').read_text().splitlines()]
        self.assertEqual(errors[0]['status'], 'delai_depasse')

    def test_tui_all_actions_dispatch(self):
        answers = [str(n) for n in range(1, 9)] + ['0']
        with patch('builtins.input', side_effect=answers), patch('prevost_v16.__main__.execute') as execute_mock, contextlib.redirect_stdout(io.StringIO()):
            tui(Store(self.root))
        self.assertEqual([c.args[0] for c in execute_mock.call_args_list],
                         ['diagnostic', 'mtp', 'adb', 'recovery', 'informations', 'historique', 'rapport', 'export'])

    def test_cli_diagnostic_and_technical_reports(self):
        store = Store(self.root)
        with patch('prevost_v16.__main__.Diagnostics', return_value=self.diag), contextlib.redirect_stdout(io.StringIO()) as output:
            for cmd in ('detect', 'diagnostic', 'usb', 'adb', 'mtp', 'recovery', 'informations'):
                execute(cmd, store)
            for cmd in ('historique', 'rapport', 'export'):
                execute(cmd, store)
        self.assertEqual(len(store.reports()), 7)
        self.assertIn('SM-G990W2', output.getvalue())


class UtilityTests(unittest.TestCase):
    def test_parse_adb_states(self):
        rows = parse_adb('List of devices attached\nA unauthorized usb:1-2\nB no permissions (x)\nC device model:SM_G990W2\n* daemon started successfully\n')
        self.assertEqual([r['state'] for r in rows], ['unauthorized', 'no_permissions', 'device'])

    def test_frp_unknown_and_zero_never_absent(self):
        for settings in ({}, {'global.secure_frp_mode': {'status': 'ok', 'value': '0'}}):
            result = interpret({}, settings)
            self.assertEqual(result['clues'], [])
            self.assertIn('indéterminée', result['conclusion'])

    def test_runner_missing(self):
        with patch('shutil.which', return_value=None):
            self.assertEqual(Runner()(['adb'])['status'], 'outil_absent')

    def test_runner_timeout(self):
        with patch('shutil.which', return_value='/usr/bin/adb'), patch('subprocess.run', side_effect=subprocess.TimeoutExpired('adb', 12)):
            self.assertEqual(Runner()(['adb'])['status'], 'delai_depasse')

    def test_runner_return_code_and_no_stderr(self):
        with patch('shutil.which', return_value='/usr/bin/adb'), patch('subprocess.run', return_value=subprocess.CompletedProcess(['adb'], 1, '', 'sensitive')):
            result = Runner()(['adb'])
            self.assertEqual(result['status'], 'erreur_commande')
            self.assertNotIn('sensitive', str(result))

    def test_runner_adb_server_permission_error(self):
        with patch('shutil.which', return_value='/usr/bin/adb'), patch('subprocess.run', return_value=subprocess.CompletedProcess(['adb'], 1, '', 'Operation not permitted')):
            self.assertEqual(Runner()(['adb'])['status'], 'adb_permission_refusee')

    def test_runner_oserror(self):
        with patch('shutil.which', return_value='/usr/bin/adb'), patch('subprocess.run', side_effect=PermissionError()):
            self.assertEqual(Runner()(['adb'])['status'], 'PermissionError')

    def test_read_unavailable(self):
        self.assertIsNone(read('/nonexistent-prevost-file'))

    def test_no_color_redirect(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(paint('x', 'red'), 'x')

    def test_watch_stops_on_interrupt(self):
        with patch('prevost_v16.__main__.execute') as action, patch('prevost_v16.__main__.time.sleep', side_effect=KeyboardInterrupt), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['usb', '--watch', '2']), 130)
            action.assert_called_once()

    def test_cli_error_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            with patch('prevost_v16.__main__.Store', return_value=store), patch('prevost_v16.__main__.execute', side_effect=OSError('disque inaccessible')), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['diagnostic']), 1)
            self.assertIn('disque inaccessible', (store.directory / 'erreurs.jsonl').read_text())

    def test_lexos_palette(self):
        with patch('sys.stdout.isatty', return_value=True), patch('os.environ.get', return_value=None):
            for color, code in [('red', 31), ('white', 97), ('yellow', 93), ('sky', 96)]:
                self.assertIn(f'40;{code}m', paint('LexOS', color))

    def test_cli_invalid_watch(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(['export', '--watch', '3'])
        self.assertEqual(error.exception.code, 2)

    def test_tui_invalid_then_eof(self):
        with patch('builtins.input', side_effect=['bad', EOFError()]), contextlib.redirect_stdout(io.StringIO()) as output:
            tui(Store('/tmp/unused-prevost'))
        self.assertIn('Choix invalide', output.getvalue())


if __name__ == '__main__':
    unittest.main()
