import contextlib
import copy
import errno
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from outils.v21 import diagnostic as v21
from prevost_v16 import __main__ as cli
from prevost_v16.core import Store


def context(seccomp=0, denied=False):
    return {'process_restrictions':{'Seccomp':seccomp,'NoNewPrivs':int(bool(seccomp))},
            'process_status':'lu','loopback_listener':{'status':'refuse' if denied else 'ok',
            'stage':'creation' if denied else 'termine','errno':errno.EPERM if denied else None},
            'dbus_session_address_present':True,'runtime_dir_present':True}


def live_fixture():
    return {'usb':{'status':'ok','devices':[{'port':'1-2','vendor_id':'04e8','product_id':'6860',
        'serial':'HARDWARE_TEST_ONLY','product':'personal_device_label',
        'interfaces':[{'role':'PTP/MTP candidat','bInterfaceClass':'06','bInterfaceSubClass':'01','bInterfaceProtocol':'01'}],
        'node':{'path':'/dev/bus/usb/001/002'}}]},
        'probes':[{'id':'usb','status':'executed','returncode':0,'stdout':'HARDWARE_TEST_ONLY','stderr':''},
                  {'id':'adb','status':'executed','returncode':0,'stdout':'List of devices attached\n','stderr':''},
                  {'id':'mtp_mounts','status':'executed','returncode':0,'stdout':'mtp://HARDWARE_TEST_ONLY/','stderr':''}],
        'adb_devices':[], 'mtp':{'session_query_success':True,'mounts':[]}, 'mtp_metadata':[],
        'devices':[{'port':'1-2','adb_states':[],'mtp_interface_announced':True,'mtp_mount_announced':True,
                    'mtp_root_metadata_accessible':False,'recovery_transport_observed':False}],
        'unassociated_adb_count':0}


class EnvironmentTests(unittest.TestCase):
    def test_socket_permission_before_usb(self):
        def fail(*args): raise PermissionError(errno.EPERM,'blocked')
        r=v21.socket_check(fail)
        self.assertEqual((r['status'],r['stage'],r['errno']),('refuse','creation',1))

    def test_bind_permission_and_cleanup(self):
        sock=Mock(); sock.bind.side_effect=PermissionError(errno.EACCES,'blocked')
        r=v21.socket_check(lambda *args:sock)
        self.assertEqual(r['stage'],'bind_loopback')
        self.assertEqual(r['errno'],errno.EACCES)
        sock.close.assert_called_once()

    def test_socket_success_closes_listener(self):
        sock=Mock()
        r=v21.socket_check(lambda *args:sock)
        self.assertEqual(r['status'],'ok')
        sock.bind.assert_called_once_with(('127.0.0.1',0))
        sock.listen.assert_called_once_with(1)
        sock.close.assert_called_once()

    def test_proc_values_and_env_presence_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'status'
            path.write_text('Name:\tDO_NOT_COPY\nSeccomp:\t2\nNoNewPrivs:\t1\n')
            with patch.dict(os.environ,{'DBUS_SESSION_BUS_ADDRESS':'PRIVATE_DBUS_SENTINEL'}):
                r=v21.environment(path,lambda:{'status':'ok','stage':'termine','errno':None})
            text=json.dumps(r)
            self.assertNotIn('DO_NOT_COPY',text)
            self.assertNotIn('PRIVATE_DBUS_SENTINEL',text)
            self.assertEqual(r['process_restrictions']['Seccomp'],2)

    def test_node_missing_is_visibility_not_unplugged(self):
        r=v21.node_evidence({'node':{'path':'/nonexistent-v21-usb-node'}})
        self.assertEqual(r['status'],'absent_de_cette_vue')


class ClassificationTests(unittest.TestCase):
    def codes(self,env=None,node=None,live=None):
        live=live or live_fixture()
        return {f['code'] for f in v21.findings(live,env or context(),[node or {'status':'visible','read_access':True,'write_access':True}],v21.associate(live))}

    def test_sandbox_evidence_independent_of_ubuntu_label(self):
        codes=self.codes(context(2,True))
        self.assertIn('restriction_locale_observee',codes)
        self.assertIn('seccomp_actif',codes)
        self.assertNotIn('acces_noeud_usb_refuse',codes)

    def test_host_node_denial_without_socket_restriction(self):
        codes=self.codes(node={'status':'visible','read_access':False,'write_access':False})
        self.assertIn('acces_noeud_usb_refuse',codes)
        self.assertNotIn('restriction_locale_observee',codes)

    def test_seccomp_alone_does_not_claim_denied_socket(self):
        codes=self.codes(context(2))
        self.assertIn('seccomp_actif',codes)
        self.assertNotIn('restriction_locale_observee',codes)

    def test_adb_unauthorized_is_distinct_from_frp(self):
        live=live_fixture()
        live['adb_devices']=[{'serial':'HARDWARE_TEST_ONLY','state':'unauthorized','usb':'1-2'}]
        self.assertIn('adb_etat_unauthorized',self.codes(live=live))
        self.assertNotIn('serveur_adb_indisponible',self.codes(live=live))

    def test_adb_no_permissions_has_its_own_classification(self):
        live=live_fixture()
        live['adb_devices']=[{'serial':'HARDWARE_TEST_ONLY','state':'no_permissions','usb':'1-2'}]
        self.assertIn('adb_etat_no_permissions',self.codes(live=live))

    def test_adb_server_error_not_phone_denial(self):
        live=live_fixture()
        live['probes'][1].update(returncode=1,stderr='could not install smartsocket listener: Operation not permitted')
        codes=self.codes(context(2,True),live=live)
        self.assertIn('serveur_adb_indisponible',codes)
        self.assertNotIn('adb_etat_unauthorized',codes)

    def test_missing_tool_and_timeout_recorded(self):
        live=live_fixture()
        live['probes'][0].update(status='not_started',returncode=None)
        live['probes'][2].update(status='timeout',timed_out=True,returncode=-9)
        codes=self.codes(live=live)
        self.assertIn('outil_non_demarre',codes)
        self.assertIn('sonde_expiree',codes)

    def test_duplicate_serial_without_port_is_ambiguous(self):
        live=live_fixture()
        second=copy.deepcopy(live['usb']['devices'][0]); second['port']='1-3'
        live['usb']['devices'].append(second)
        live['adb_devices']=[{'serial':'HARDWARE_TEST_ONLY','state':'sideload','usb':None}]
        self.assertIsNone(v21.associate(live)[0]['port'])
        live['adb_devices'][0]['usb']='1-3'
        self.assertEqual(v21.associate(live)[0]['port'],'1-3')

    def test_explicit_unmatched_port_never_falls_back_to_serial(self):
        live=live_fixture()
        live['adb_devices']=[{'serial':'HARDWARE_TEST_ONLY','state':'recovery','usb':'9-9'}]
        self.assertIsNone(v21.associate(live)[0]['port'])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        dest=self.root/'outils/v19';dest.mkdir(parents=True)
        shutil.copy2(v21.ROOT/'outils/v19/confirmation_utilisateur.json',dest)

    def prepare(self,**kwargs):
        live=live_fixture()
        with patch.object(v21.v20,'collect',return_value=live),patch.object(v21,'node_evidence',return_value={'status':'visible','read_access':True,'write_access':True}):
            return v21.prepare(self.root,environment_reader=lambda:context(2,True),**kwargs)

    def test_share_omits_serial_paths_uris_raw_outputs_and_private_context(self):
        r=self.prepare(label='ubuntu')
        r['environment']['private']='HARDWARE_TEST_ONLY'
        r['findings'][0]['extra']='HARDWARE_TEST_ONLY'
        r['historical_evidence'].append({'path':'/home/PRIVATE_USER/file-HARDWARE_TEST_ONLY.json','analysis':{'version':19}})
        r['confirmation']['private']='HARDWARE_TEST_ONLY'
        r['live']['probes'][1]['stderr']='IP_ADDRESS_SENTINEL username PRIVATE_USER'
        r['live']['usb']['devices'][0]['interfaces'][0]['interface']='HARDWARE_TEST_ONLY'
        public=v21.share(r)
        text=v21.text_report(public)
        for forbidden in ('HARDWARE_TEST_ONLY','PRIVATE_USER','IP_ADDRESS_SENTINEL','mtp://','/dev/bus/usb','personal_device_label','owner_uid','argv','stdout','stderr'):
            # The schema explicitly documents that stdout/stderr are absent; test data fields instead.
            if forbidden in ('stdout','stderr'): continue
            self.assertNotIn(forbidden,text)
        self.assertNotIn('stdout',public['probes'][0])
        self.assertNotIn('stderr',public['probes'][0])
        self.assertEqual(public['devices'][0]['device'],'Samsung-1')
        self.assertEqual(public['phone_data_access'],'non_teste')
        self.assertIn('restriction_locale_observee',{f['code'] for f in public['findings']})

    def test_shared_context_whitelist_and_unknown_label(self):
        r=self.prepare(label='SENSITIVE_USER_LABEL')
        public=v21.share(r)
        self.assertEqual(public['label'],'non_precise')
        self.assertNotIn('SENSITIVE_USER_LABEL',json.dumps(public))

    def test_invalid_usb_strings_are_not_shared(self):
        r=self.prepare()
        r['live']['usb']['devices'][0]['product_id']='SENSITIVE_ID'
        r['live']['usb']['devices'][0]['interfaces'][0]['bInterfaceClass']='SENSITIVE_ID'
        self.assertNotIn('SENSITIVE_ID',json.dumps(v21.share(r)))

    def test_archive_contains_only_shared_data_and_checksum_matches(self):
        r=self.prepare()
        a=v21.save(r,self.root); b=v21.save(r,self.root)
        self.assertNotEqual(a,b)
        self.assertEqual((a.stat().st_mode & 0o777),0o700)
        self.assertEqual(((a/'rapport-prive.json').stat().st_mode & 0o777),0o600)
        private=(a/'rapport-prive.json').read_text()
        self.assertIn('HARDWARE_TEST_ONLY',private)
        with zipfile.ZipFile(a/'partage.zip') as z:
            self.assertNotIn('rapport-prive.json',z.namelist())
            for name in z.namelist():
                self.assertNotIn('HARDWARE_TEST_ONLY',z.read(name).decode())
            for line in z.read('SHA256SUMS').decode().splitlines():
                import hashlib
                value,name=line.split('  ')
                self.assertEqual(value,hashlib.sha256(z.read(name)).hexdigest())
        for line in (a/'SHA256SUMS').read_text().splitlines():
            value,name=line.split('  ')
            self.assertEqual(value,v21.digest(a/name))

    def test_report_only_defaults_to_share_no_probe_or_write(self):
        out=v21.save(self.prepare(),self.root)
        before=v21.inventory(self.root)
        with patch.object(v21,'prepare',side_effect=AssertionError('no probes')),patch.object(v21,'save',side_effect=AssertionError('no writes')),contextlib.redirect_stdout(io.StringIO()) as capture:
            self.assertEqual(v21.run(self.root,report_only=True),0)
        self.assertNotIn('HARDWARE_TEST_ONLY',capture.getvalue())
        self.assertEqual(before,v21.inventory(self.root))
        with contextlib.redirect_stdout(io.StringIO()) as capture:
            v21.run(self.root,report_only=True,private=True)
        self.assertIn('HARDWARE_TEST_ONLY',capture.getvalue())

    def test_missing_report_does_not_start_diagnostic(self):
        with patch.object(v21,'prepare',side_effect=AssertionError('no probes')),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(v21.run(self.root,report_only=True),1)

    def test_preservation_including_old_report_bytes(self):
        old=self.root/'rapports/v20/old.txt';old.parent.mkdir(parents=True);old.write_text('conserver')
        r=self.prepare();v21.save(r,self.root)
        self.assertEqual(old.read_text(),'conserver')
        self.assertEqual(r['preservation']['changed_or_missing'],[])

    def test_cli_flags_and_menu_12(self):
        with patch.object(cli,'Store',return_value=Store(self.root)),patch.object(v21,'run',return_value=0) as run:
            self.assertEqual(cli.main(['diagnostic-v21','--rapport','--prive']),0)
            self.assertTrue(run.call_args.kwargs['report_only'])
            self.assertTrue(run.call_args.kwargs['private'])
        self.assertEqual(cli.LABELS[11],'DIAGNOSTIC SAMSUNG V21')
        with patch('builtins.input',side_effect=['12','0']),patch.object(v21,'run',return_value=0) as run,contextlib.redirect_stdout(io.StringIO()):
            cli.tui(Store(self.root))
        run.assert_called_once_with(self.root)

    def test_cli_rejects_incompatible_modes(self):
        for args in (['diagnostic-v21','--watch','2'],['diagnostic-v21','--serial','x'],['diagnostic-v21','--diagnostic'],['diagnostic-v21','--prive','--partage']):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit): cli.main(args)

    def test_export_includes_v21_and_legacy_files(self):
        out=v21.save(self.prepare(),self.root)
        for name in ('README-V21.md','outils/v21/diagnostic.py','rapports/v17/old.txt'):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('source')
        archive,_=Store(self.root).export()
        with zipfile.ZipFile(archive) as z:
            for name in ('README-V21.md','outils/v21/diagnostic.py','rapports/v17/old.txt',str((out/'partage/rapport.txt').relative_to(self.root))):
                self.assertIn(name,z.namelist())
