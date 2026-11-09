"""Données réseau simulées uniquement : aucun paquet de découverte émis."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from prevost.app import UI
from prevost import network as net


XML = '''<nmaprun><host><status state="up" reason="arp-response"/>
<address addr="192.168.50.2" addrtype="ipv4"/>
<address addr="AA:BB:CC:DD:EE:01" addrtype="mac"/>
<hostnames><hostname name="poste-simule"/></hostnames></host>
<runstats><finished exit="success"/></runstats></nmaprun>'''


def connection():
    identity = {'uuid': 'profil-simule', 'interface': 'eth0', 'type': 'ethernet',
                'gateway': '192.168.50.1', 'gateway_mac': 'aa:bb:cc:dd:ee:ff',
                'subnets': ['192.168.50.0/24'], 'bssid': None}
    return {'id': net.digest(identity), 'identity': identity, 'name': 'Réseau simulé', 'activation': '/active/1'}


def observation(ip='192.168.50.2', mac='aa:bb:cc:dd:ee:01', name=None):
    return {'ip': ip, 'mac': mac, 'name': name, 'source': 'simulation', 'certainty': 'simulée'}


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = net.Store(Path(self.tmp.name)/'private')
        self.connection = connection()
        self.store.remember(self.connection)
        self.ui = UI()
        self.ui.color = False
        self.ui.show = lambda _: None

    def approve(self):
        self.store.decide(self.connection, '192.168.50.0/24')

    def row(self):
        return self.store.read()['networks'][self.connection['id']]

    def test_device_inventory_ids_presence_sorting_and_cli_without_scan(self):
        self.approve()
        self.store.record(self.connection, '192.168.50.0/24', [
            observation('192.168.50.10'), observation('192.168.50.2')])
        first = net.device_inventory(self.store.read())
        self.assertEqual([r['ip'] for r in first], ['192.168.50.2', '192.168.50.10'])
        self.assertTrue(all(r['observed_last_scan'] for r in first))
        self.assertTrue(all(r['network_id'] == self.connection['id'] for r in first))
        self.store.record(self.connection, '192.168.50.0/24', [observation('192.168.50.2')])
        rows = net.device_inventory(self.store.read())
        self.assertEqual([r['id'] for r in rows], [r['id'] for r in first])
        self.assertEqual([r['observed_last_scan'] for r in rows], [True, False])
        with patch.object(net, 'connections') as connected, patch.object(net, 'discover') as scan, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(net.main(['appareils', '--state-dir', str(self.store.directory)]), 0)
        self.assertEqual(json.loads(output.getvalue()), rows)
        connected.assert_not_called()
        scan.assert_not_called()

    def test_unknown_is_prompted_once_even_after_restart(self):
        other = connection()
        other['id'] = 'nouvelle-connexion-simulee'
        with patch.object(self.ui, 'read', return_value='192.168.50.0/24') as read, patch.object(self.ui, 'confirm', return_value=False) as confirm:
            for store in (self.store, net.Store(self.store.directory)):
                net.cycle(store, self.ui, connected=lambda: [other], scan=lambda *_: self.fail('découverte sans accord'), interactive=True)
        self.assertEqual(read.call_count, 1)
        self.assertEqual(confirm.call_count, 1)
        self.assertEqual(self.store.read()['networks'][other['id']]['decision'], 'denied')

    def test_interrupted_prompt_remains_denied(self):
        with patch.object(self.ui, 'read', side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            net.approve(self.store, self.connection, self.ui)
        self.assertEqual(self.row()['decision'], 'denied')

    def test_unattended_unknown_stays_pending(self):
        other = connection(); other['id'] = 'autre'
        with patch.object(self.ui, 'read', side_effect=AssertionError('pas de saisie')):
            net.cycle(self.store, self.ui, connected=lambda: [other], scan=lambda *_: self.fail('non autorisé'), interactive=False)
        self.assertEqual(self.store.read()['networks']['autre']['decision'], 'pending')

    def test_explicit_approval_and_automatic_discovery(self):
        with patch.object(self.ui, 'confirm', return_value=True):
            net.approve(self.store, self.connection, self.ui, '192.168.50.0/25')
        calls = []
        def scan(connection, scope, guard):
            self.assertFalse(guard.is_set())
            calls.append(scope)
            return [observation()]
        for _ in range(2):
            net.cycle(self.store, self.ui, connected=lambda: [self.connection], scan=scan, interactive=False)
        self.assertEqual(calls, ['192.168.50.0/25']*2)
        self.assertEqual(self.row()['scans'], 2)
        self.assertEqual(self.row()['last_comparison']['new'], [])

    def test_scope_rejects_remote_huge_ipv6_or_options(self):
        for scope in ['192.168.51.0/24', '192.168.0.0/16', '0.0.0.0/0', '::/64', '--script=default', '192.168.50.1/24']:
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                net.scope_for(self.connection, scope)
        self.assertEqual(net.scope_for(self.connection, '192.168.50.2/32'), '192.168.50.2/32')

    def test_first_last_sources_names_and_new_candidates(self):
        self.approve()
        self.store.record(self.connection, self.row()['scope'], [observation(name='premier')], '2026-01-01')
        self.store.record(self.connection, self.row()['scope'], [observation(name='second'), observation('192.168.50.3')], '2026-01-02')
        row = self.row()
        first = next(d for d in row['devices'].values() if d['ip'].endswith('.2'))
        self.assertEqual((first['first_seen'], first['last_seen']), ('2026-01-01', '2026-01-02'))
        self.assertEqual(first['names'], ['premier', 'second'])
        self.assertEqual(first['sources']['simulation']['last_seen'], '2026-01-02')
        self.assertEqual(len(row['last_comparison']['new']), 1)
        self.assertTrue(all(d['status'] == 'a_valider' for d in row['devices'].values()))

    def test_no_merge_ip_reuse_mac_change_or_missing_mac(self):
        self.approve()
        observations = [observation(), observation(mac=None), observation(mac='aa:bb:cc:dd:ee:02'), observation('192.168.50.3')]
        self.store.record(self.connection, self.row()['scope'], observations)
        self.assertEqual(len(self.row()['devices']), 4)
        self.assertTrue(any('incertaine' in d['identity_confidence'] for d in self.row()['devices'].values()))

    def test_absence_is_not_deletion_and_reappearance_not_new(self):
        self.approve()
        scope = self.row()['scope']
        self.store.record(self.connection, scope, [observation()])
        self.store.record(self.connection, scope, [])
        self.assertEqual(len(self.row()['devices']), 1)
        self.assertEqual(len(self.row()['last_comparison']['not_observed']), 1)
        self.store.record(self.connection, scope, [observation()])
        self.assertEqual(self.row()['last_comparison']['new'], [])
        self.assertEqual(len(self.row()['last_comparison']['reappeared']), 1)

    def test_incomplete_or_failed_scan_preserves_snapshot(self):
        self.approve()
        self.store.record(self.connection, self.row()['scope'], [observation()])
        before = self.row()
        def fail(*_):
            raise OSError('échec simulé')
        net.cycle(self.store, self.ui, connected=lambda: [self.connection], scan=fail)
        self.assertEqual(self.row()['devices'], before['devices'])
        self.assertEqual(self.row()['previous'], before['previous'])
        self.assertEqual(self.row()['scans'], 1)
        with self.assertRaises(ValueError):
            net.parse_hosts(XML.replace('exit="success"', 'exit="error"'), self.row()['scope'])

    def test_xml_rejects_out_of_scope_and_down_hosts(self):
        with self.assertRaises(ValueError):
            net.parse_hosts(XML.replace('192.168.50.2', '203.0.113.1'), '192.168.50.0/24')
        self.assertEqual(net.parse_hosts(XML.replace('state="up"', 'state="down"'), '192.168.50.0/24'), [])

    def test_discovery_fixed_arp_only_and_uncertain_cache(self):
        self.approve()
        calls = []
        def execute(argv, **kwargs):
            calls.append(argv)
            return XML if argv[0] == 'nmap' else json.dumps([
                {'dst': '192.168.50.4', 'lladdr': 'aa:bb:cc:dd:ee:04', 'state': ['STALE']},
                {'dst': '203.0.113.1', 'lladdr': 'aa:bb:cc:dd:ee:05', 'state': ['REACHABLE']}])
        guard = net.Guard(self.store, self.connection, self.row()['scope'], lambda: [self.connection])
        with patch('pathlib.Path.open', return_value=io.StringIO('192.168.50.2 nom-local\n')):
            # Ne pas utiliser le Store dans ce patch du fichier hosts.
            class Allowed:
                def is_set(self): return False
            result = net.discover(self.connection, '192.168.50.0/24', Allowed(), execute)
        self.assertIn('-sn', calls[0]); self.assertIn('-n', calls[0])
        self.assertIn('-PR', calls[0]); self.assertIn('--send-eth', calls[0])
        self.assertNotIn('-sV', calls[0]); self.assertNotIn('--script', calls[0])
        self.assertEqual(calls[0][-1], '192.168.50.0/24')
        self.assertEqual(result[0]['name'], 'poste-simule')
        self.assertTrue(any(d['name'] == 'nom-local' and d['source'] == '/etc/hosts local' for d in result))
        self.assertTrue(any(d['ip'].endswith('.4') and 'incertaine' in d['certainty'] for d in result))
        self.assertFalse(any(d['ip'].startswith('203.') for d in result))

    def test_stop_revoke_and_changed_connection_cancel(self):
        self.approve()
        for action in ('stop', 'revoke', 'disconnect'):
            with self.subTest(action=action):
                self.store.stop_path.unlink(missing_ok=True)
                self.approve()
                current = [self.connection]
                guard = net.Guard(self.store, self.connection, self.row()['scope'], lambda: current)
                self.assertFalse(guard.is_set())
                if action == 'stop': self.store.stop()
                elif action == 'revoke': self.store.revoke(self.connection['id'])
                else: current.clear()
                guard.checked = 0
                self.assertTrue(guard.is_set())

    def test_revoke_during_scan_does_not_resurrect_approval(self):
        self.approve()
        def scan(*_):
            self.store.revoke(self.connection['id'])
            return [observation()]
        net.cycle(self.store, self.ui, connected=lambda: [self.connection], scan=scan)
        self.assertEqual(self.row()['decision'], 'revoked')
        self.assertEqual(self.row()['devices'], {})
        with self.assertRaises(ValueError):
            self.store.record(self.connection, '192.168.50.0/24', [observation()])

    def test_stop_prevents_all_scans(self):
        self.approve(); self.store.stop()
        net.cycle(self.store, self.ui, connected=lambda: [self.connection], scan=lambda *_: self.fail('veille arrêtée'))
        self.assertEqual(self.row()['scans'], 0)

    def test_private_modes_and_outside_git(self):
        self.store.stop()
        self.assertEqual(self.store.directory.stat().st_mode & 0o777, 0o700)
        for path in self.store.directory.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        repository = Path(self.tmp.name)/'repo'
        (repository/'.git').mkdir(parents=True)
        (repository/'.git/HEAD').write_text('ref: refs/heads/main\n')
        with self.assertRaises(ValueError): net.Store(repository/'state')
        link = Path(self.tmp.name)/'alias'; link.symlink_to(self.store.directory)
        with self.assertRaises(ValueError): net.Store(link)
        self.store.path.unlink(); self.store.path.symlink_to(repository/'fake')
        with self.assertRaises(ValueError): self.store.read()

    def test_failed_transaction_does_not_modify_state(self):
        before = self.store.path.read_text()
        self.approve()
        approved = self.store.path.read_text()
        with self.assertRaises(ValueError):
            self.store.record(self.connection, '192.168.50.0/24', [observation(), observation('203.0.113.2')])
        self.assertEqual(self.store.path.read_text(), approved)
        self.assertNotEqual(before, approved)

    def test_local_identity_collection_without_secret_access(self):
        def execute(argv, **kwargs):
            if argv[0] == 'ip' and 'address' in argv:
                return json.dumps([{'ifname': 'eth0', 'addr_info': [{'local': '192.168.50.10', 'prefixlen': 24, 'scope': 'global'}]}])
            if argv[0] == 'ip':
                return json.dumps([{'dst': '192.168.50.1', 'lladdr': 'aa:bb:cc:dd:ee:ff', 'state': ['STALE']}])
            self.assertNotIn('--show-secrets', argv)
            return 'GENERAL.CON-UUID:profil-simule\nGENERAL.TYPE:ethernet\nGENERAL.CONNECTION:Réseau simulé\nGENERAL.CON-PATH:/active/1\nIP4.GATEWAY:192.168.50.1\n'
        with patch.object(net, 'run', side_effect=execute):
            self.assertEqual(net.connections()[0]['id'], self.connection['id'])

    def test_changed_bssid_or_gateway_changes_identity(self):
        original = self.connection['identity']
        for field, value in [('gateway_mac', '00:11:22:33:44:55'), ('bssid', '11:22:33:44:55:66'), ('uuid', 'autre')]:
            changed = {**original, field: value}
            self.assertNotEqual(net.digest(original), net.digest(changed))

    def test_unidentifiable_ethernet_is_not_assumed_approved(self):
        responses = [json.dumps([{'ifname': 'eth0', 'addr_info': [
            {'local': '192.168.50.10', 'prefixlen': 24, 'scope': 'global'}]}]),
            'GENERAL.CON-UUID:profil\nGENERAL.TYPE:ethernet\nIP4.GATEWAY:192.168.50.1\n', '[]']
        with patch.object(net, 'run', side_effect=responses), self.assertRaises(ValueError):
            net.connections()

    def test_wifi_metadata_is_identified_but_not_approved(self):
        responses = [json.dumps([{'ifname': 'wlan0', 'addr_info': [
            {'local': '192.168.50.10', 'prefixlen': 24, 'scope': 'global'}]}]),
            'GENERAL.CON-UUID:wifi-profil\nGENERAL.TYPE:wifi\nGENERAL.CONNECTION:Maison\nIP4.GATEWAY:192.168.50.1\n',
            '*:aa:bb:cc:dd:ee:ff\n :00:11:22:33:44:55\n', '[]']
        with patch.object(net, 'run', side_effect=responses):
            connection = net.connections()[0]
        self.assertEqual(connection['identity']['bssid'], 'aa:bb:cc:dd:ee:ff')
        self.store.remember(connection)
        self.assertEqual(self.store.read()['networks'][connection['id']]['decision'], 'pending')

    def test_monitor_events_and_stop_cleanup_simulated_networkmanager(self):
        popen = subprocess.Popen
        children = []
        def start(argv, **kwargs):
            self.assertEqual(argv, ['nmcli', 'monitor'])
            child = popen([sys.executable, '-c',
                           'import time; print("événement simulé", flush=True); time.sleep(20)'], **kwargs)
            children.append(child)
            return child
        with patch.object(net.subprocess, 'Popen', side_effect=start):
            updates = net.events(self.store, 60)
            next(updates)  # État initial.
            next(updates)  # Message simulé du moniteur.
            self.store.stop()
            with self.assertRaises(StopIteration): next(updates)
        self.assertIsNotNone(children[0].poll())

    def test_monitor_failure_does_not_claim_watch_is_active(self):
        popen = subprocess.Popen
        def start(argv, **kwargs):
            child = popen([sys.executable, '-c', 'raise SystemExit(1)'], **kwargs)
            child.wait(timeout=2)
            return child
        with patch.object(net.subprocess, 'Popen', side_effect=start):
            updates = net.events(self.store, 60)
            next(updates)
            with self.assertRaises(OSError): next(updates)

    def test_keyboard_cancellation_stops_remaining_networks(self):
        self.approve()
        guard = net.Guard(self.store, self.connection, self.row()['scope'], lambda: [self.connection])
        guard.set()
        self.assertTrue(self.store.stop_path.exists())
        self.assertTrue(guard.is_set())

    def test_revocation_terminates_running_process_without_network(self):
        self.approve()
        guard = net.Guard(self.store, self.connection, self.row()['scope'], lambda: [self.connection])
        timer = threading.Timer(.1, lambda: self.store.revoke(self.connection['id']))
        timer.start()
        try:
            result = net.process([sys.executable, '-c', 'import time; time.sleep(20)'], timeout=3, cancel=guard)
        finally:
            timer.cancel()
            timer.join()
        self.assertEqual(result['status'], 'cancelled')
        self.assertIsNotNone(result['returncode'])
        self.assertLess(result['duration'], 2)

    def test_stop_interrupts_pending_terminal_prompt(self):
        self.store.stop()
        ui = net.NetworkUI(self.store)
        ui.color = True
        with patch('sys.stdin.isatty', return_value=True), patch('selectors.DefaultSelector'):
            with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(KeyboardInterrupt):
                ui.read('Périmètre > ')
        self.assertTrue(output.getvalue().endswith('\x1b[0m'))

    def test_second_watcher_is_rejected(self):
        import fcntl
        with self.store.open_private('watch.lock') as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = net.main(['une-fois', '--state-dir', str(self.store.directory)])
        self.assertEqual(result, 1)
        self.assertIn('Une veille utilise déjà', output.getvalue())

    def test_cli_stop_and_revoke(self):
        self.approve()
        args = ['--state-dir', str(self.store.directory)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(net.main(['arreter', *args]), 0)
            self.assertEqual(net.main(['retirer', '--network', self.connection['id'], *args]), 0)
        self.assertTrue(self.store.stop_path.exists())
        self.assertEqual(self.row()['decision'], 'revoked')

    def test_cli_once_simulated_success_and_failure(self):
        self.approve()
        args = ['une-fois', '--state-dir', str(self.store.directory)]
        with patch.object(net, 'connections', return_value=[self.connection]), contextlib.redirect_stdout(io.StringIO()):
            with patch.object(net, 'discover', return_value=[observation()]):
                self.assertEqual(net.main(args), 0)
            with patch.object(net, 'discover', side_effect=OSError('Nmap indisponible simulé')):
                self.assertEqual(net.main(args), 1)
        self.assertEqual(self.row()['scans'], 1)


if __name__ == '__main__':
    unittest.main()
