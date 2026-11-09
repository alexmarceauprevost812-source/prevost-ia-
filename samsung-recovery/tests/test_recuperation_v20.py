import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from outils.v20 import recuperation as v20
from prevost_v16 import __main__ as cli
from prevost_v16.core import Store


class RecoveryV20Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        target = self.root / 'outils/v19'
        target.mkdir(parents=True)
        shutil.copy2(v20.ROOT / 'outils/v19/confirmation_utilisateur.json', target)
        self.sysfs = self.root / 'sysfs'
        self.sysfs.mkdir()
        self.calls = []
        self.adb = ''
        self.mounts = ''
        self.gio_error = ''
        self.info_code = 0

    def device(self, port='1-2', serial='SAMSUNG_TEST', triple=('06','01','01')):
        d = self.sysfs / port
        d.mkdir()
        for k, v in {'idVendor':'04e8', 'idProduct':'6860', 'product':'SAMSUNG_Android',
                     'serial':serial, 'busnum':'1', 'devnum':'2'}.items():
            (d / k).write_text(v)
        interface = d / (port + ':1.0')
        interface.mkdir()
        for k, v in zip(('bInterfaceClass','bInterfaceSubClass','bInterfaceProtocol'), triple):
            (interface / k).write_text(v)
        endpoint = interface / 'ep_81'
        endpoint.mkdir()
        (endpoint / 'bEndpointAddress').write_text('81')
        return d

    def runner(self, key, argv, timeout):
        self.calls.append(argv)
        self.assertTrue(v20.allowed(argv))
        self.assertGreater(timeout, 0)
        stdout = self.adb if key == 'adb' else self.mounts if key == 'mtp_mounts' else ('standard::type: 2\nfilesystem::type: mtp' if key == 'mtp_info' else '')
        return {'id':key, 'argv':argv, 'returncode':self.info_code if key == 'mtp_info' else 0,
                'status':'executed', 'stdout':stdout, 'stderr':self.gio_error if key == 'mtp_mounts' else ''}

    def prepare(self, **kwargs):
        return v20.prepare(self.root, sysfs=self.sysfs, runner=self.runner, **kwargs)

    def test_usb_details_endpoints_do_not_fabricate_model_or_android(self):
        self.device()
        r = self.prepare()
        self.assertEqual(r['live']['usb']['devices'][0]['interfaces'][0]['endpoints'][0]['bEndpointAddress'], '81')
        self.assertTrue(r['live']['devices'][0]['mtp_interface_announced'])
        self.assertIsNone(r['live']['model']['observed_exact'])
        self.assertFalse(r['live']['devices'][0]['recovery_transport_observed'])

    def test_only_correlated_recovery_transport_is_reported(self):
        self.device(triple=('ff','42','01'))
        self.adb = 'SAMSUNG_TEST sideload usb:1-2\nUNRELATED recovery usb:9-9'
        r = self.prepare()
        self.assertTrue(r['live']['devices'][0]['recovery_transport_observed'])
        self.assertTrue(r['live']['devices'][0]['adb_interface_announced'])
        self.assertEqual(r['live']['unassociated_adb_count'], 1)
        self.assertFalse(any('shell' in c or 'sideload' in c for c in self.calls))

    def test_unrelated_adb_does_not_establish_samsung_recovery(self):
        self.device()
        self.adb = 'OTHER recovery usb:9-9'
        r = self.prepare()
        self.assertFalse(r['live']['devices'][0]['recovery_transport_observed'])
        self.assertIn('non établi', r['capabilities']['recovery'])

    def test_multiple_phones_keep_states_separate(self):
        self.device()
        self.device('1-3','SECOND')
        self.adb = 'SECOND unauthorized usb:1-3'
        d = self.prepare()['live']['devices']
        self.assertEqual(d[0]['adb_states'], [])
        self.assertEqual(d[1]['adb_states'], ['unauthorized'])

    def test_mtp_queries_only_associated_root_no_file_listing(self):
        self.device()
        self.mounts = 'Mount(0): Samsung -> mtp://SAMSUNG_SAMSUNG_TEST/\nMount(1): Other -> mtp://OTHER/'
        r = self.prepare()
        self.assertTrue(r['live']['devices'][0]['mtp_root_metadata_accessible'])
        info = [c for c in self.calls if c[:2] == ['gio','info']]
        self.assertEqual(info, [['gio','info','-a',v20.MTP_ATTRIBUTES,'mtp://SAMSUNG_SAMSUNG_TEST/']])
        self.assertFalse(any(c[:2] == ['gio','list'] for c in self.calls))

    def test_success_without_attributes_does_not_claim_mtp_access(self):
        self.device()
        self.mounts = 'mtp://SAMSUNG_TEST/'
        def empty_info(key, argv, timeout):
            result = self.runner(key, argv, timeout)
            if key == 'mtp_info':
                result['stdout'] = ''
            return result
        r = v20.prepare(self.root, sysfs=self.sysfs, runner=empty_info)
        self.assertFalse(r['live']['devices'][0]['mtp_root_metadata_accessible'])
        self.assertIn('non établi',r['capabilities']['mtp'])

    def test_mtp_occupied_or_refused_keeps_mount_but_not_access(self):
        self.device()
        self.mounts = 'mtp://SAMSUNG_TEST/'
        self.info_code = 1
        r = self.prepare()
        self.assertTrue(r['live']['devices'][0]['mtp_mount_announced'])
        self.assertFalse(r['live']['devices'][0]['mtp_root_metadata_accessible'])
        self.assertIn('non établi', r['capabilities']['mtp'])

    def test_partial_session_error_is_not_absence_of_mtp(self):
        self.gio_error = 'Operation not permitted'
        r = self.prepare()
        self.assertIn('incomplète',r['capabilities']['mtp'])

    def test_disabled_adb_and_mtp_metadata(self):
        self.device()
        self.mounts = 'mtp://SAMSUNG_TEST/'
        r = self.prepare(probe_adb=False, probe_mtp=False)
        self.assertEqual(r['capabilities']['adb'], 'non sondé')
        self.assertFalse(any(c[0] == 'adb' or c[:2] == ['gio','info'] for c in self.calls))

    def test_fixed_allowlist_rejects_phone_changes_and_shell(self):
        for c in (['adb','shell','getprop'], ['adb','reboot'], ['adb','sideload','x'],
                  ['gio','mount','mtp://SAMSUNG_TEST/'], ['mtp-detect'], ['sudo','lsusb'],
                  ['gio','info','-a','*','file:///tmp/'], ['sh','-c','lsusb']):
            self.assertFalse(v20.allowed(c), c)

    def test_history_reads_only_known_reports_and_whitelisted_fields(self):
        d = self.root / 'rapports/v19/dossier-example'
        d.mkdir(parents=True)
        (d / 'rapport.json').write_text(json.dumps({'version':19,'private':'DO_NOT_COPY',
            'confirmation':{'confirmed_by_user':True, 'screen_text':'Vérifier votre compte Google',
                            'private':'DO_NOT_COPY'}}))
        unrelated = self.root / 'rapports/private.json'
        unrelated.write_text('DO_NOT_READ')
        r = self.prepare()
        self.assertEqual(len(r['historical_evidence']), 1)
        self.assertNotIn('DO_NOT_COPY', json.dumps(r))
        self.assertTrue(r['historical_evidence'][0]['analysis']['google_screen_confirmed_by_user'])
        self.assertEqual(r['preservation']['changed_or_missing'], [])

    def test_missing_confirmation_never_claims_frp(self):
        (self.root / 'outils/v19/confirmation_utilisateur.json').unlink()
        self.assertIn('absente', self.prepare()['capabilities']['frp'])

    def test_report_files_unique_checksums_and_diagnostic_has_no_drafts(self):
        r = self.prepare(diagnostic=True)
        a = v20.save(r, self.root)
        b = v20.save(r, self.root)
        self.assertNotEqual(a,b)
        self.assertEqual(json.loads((a/'rapport.json').read_text())['version'],20)
        self.assertTrue((a/'rapport.txt').is_file())
        self.assertFalse((a/'demande-bell.txt').exists())
        for line in (a/'SHA256SUMS').read_text().splitlines():
            digest, name = line.split('  ')
            self.assertEqual(digest,v20.digest(a/name))

    def test_full_assistant_and_property_drafts(self):
        r = self.prepare()
        out = v20.save(r,self.root)
        self.assertEqual(set(r['assistant']), {'google','samsung','bell','android'})
        self.assertIn('accounts.google.com/signin/recovery', (out/'rapport.txt').read_text())
        self.assertTrue((out/'demande-samsung.txt').is_file())
        self.assertTrue((out/'demande-bell.txt').is_file())
        self.assertIn('aucun effacement',(out/'demande-samsung.txt').read_text().lower())

    def test_report_only_does_not_probe_or_write(self):
        v20.save(self.prepare(),self.root)
        before = v20.inventory(self.root)
        with patch.object(v20,'prepare',side_effect=AssertionError('no probes')), \
             patch.object(v20,'save',side_effect=AssertionError('no write')), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(v20.run(self.root,report_only=True),0)
        self.assertIn('Rapport historique',output.getvalue())
        self.assertEqual(before,v20.inventory(self.root))

    def test_missing_report_returns_nonzero_without_probe(self):
        with patch.object(v20,'prepare',side_effect=AssertionError('no probes')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(v20.run(self.root,report_only=True),1)
        self.assertFalse((self.root/'rapports/v20').exists())

    def test_latest_uses_mtime_and_not_random_suffix_order(self):
        r = self.prepare()
        a,b = v20.save(r,self.root),v20.save(r,self.root)
        os.utime(a/'rapport.json',ns=(1,1))
        os.utime(b/'rapport.json',ns=(2,2))
        self.assertEqual(v20.latest(self.root),b/'rapport.json')

    def test_three_cli_forms_and_flags(self):
        for extra in ([],['--diagnostic'],['--rapport']):
            with patch.object(cli,'Store',return_value=Store(self.root)), patch.object(v20,'run',return_value=0) as run:
                self.assertEqual(cli.main(['recuperation']+extra),0)
                self.assertEqual(run.call_args.kwargs['diagnostic'],'--diagnostic' in extra)
                self.assertEqual(run.call_args.kwargs['report_only'],'--rapport' in extra)
        with patch.object(v20,'run',return_value=1), patch.object(cli,'Store',return_value=Store(self.root)):
            self.assertEqual(cli.main(['recuperation','--rapport']),1)

    def test_flags_conflicts_and_watch_rejected(self):
        for args in (['recuperation','--diagnostic','--rapport'],['recuperation','--watch','2'],
                     ['adb','--rapport'],['recuperation','--serial','ABC']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                cli.main(args)
            self.assertEqual(error.exception.code,2)

    def test_menu_11_reaches_tool(self):
        self.assertEqual(cli.LABELS[10],'Assistant récupération Samsung V20')
        with patch('builtins.input',side_effect=['11','0']), patch.object(v20,'run',return_value=0) as run, \
             contextlib.redirect_stdout(io.StringIO()):
            cli.tui(Store(self.root))
        run.assert_called_once_with(self.root,section='tout')

    def test_export_includes_v20_and_keeps_v17_v19(self):
        out = v20.save(self.prepare(),self.root)
        for name in ('README-V20.md','outils/v20/recuperation.py','rapports/v17/old.txt','rapports/v19/old.txt'):
            p=self.root/name
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text('conserver')
        archive,_=Store(self.root).export()
        with zipfile.ZipFile(archive) as z:
            for name in ('README-V20.md','outils/v20/recuperation.py','rapports/v17/old.txt','rapports/v19/old.txt',str((out/'rapport.txt').relative_to(self.root))):
                self.assertIn(name,z.namelist())


class MtpMetadataTests(unittest.TestCase):
    def test_only_requested_attributes_are_kept(self):
        self.assertEqual(v20.mtp_attributes('name: private\n  standard::type: 2\n  filesystem::readonly: TRUE'),
                         {'standard::type':'2', 'filesystem::readonly':'TRUE'})
