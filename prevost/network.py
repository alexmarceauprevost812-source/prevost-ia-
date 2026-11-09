"""Inventaire réseau consenti, séparé des outils d’audit et du modèle."""
import argparse
from contextlib import closing, contextmanager
import fcntl
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from .app import UI
from .guardian import now
from .tools import process

DEFAULT_STATE = Path.home()/'.local/share/prevost-ia-local/networks'
MAC = re.compile(r'^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$', re.I)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def run(argv, cancel=None, timeout=8):
    result = process(argv, timeout=timeout, cancel=cancel, limit=2_000_000)
    if result['status'] != 'ok':
        raise OSError(f"Collecte indisponible ({result['status']}) : {result.get('error', '')} {result['stderr']}")
    return result['stdout']


def connections():
    """Métadonnées locales seulement ; ni secrets NM ni requête aux voisins."""
    addresses = json.loads(run(['ip', '-j', '-4', 'address', 'show', 'up']))
    result = []
    for item in addresses:
        interface = item['ifname']
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,64}', interface) or interface == 'lo':
            continue
        text = run(['nmcli', '-t', '--escape', 'no', '-f',
                    'GENERAL.CON-UUID,GENERAL.TYPE,GENERAL.CONNECTION,GENERAL.CON-PATH,IP4.GATEWAY',
                    'device', 'show', interface])
        fields = dict(line.split(':', 1) for line in text.splitlines() if ':' in line)
        uuid = fields.get('GENERAL.CON-UUID', '')
        kind = fields.get('GENERAL.TYPE', '')
        if uuid in ('', '--') or kind not in ('ethernet', 'wifi'):
            continue
        subnets = sorted({str(ipaddress.IPv4Interface(f"{a['local']}/{a['prefixlen']}").network)
                          for a in item.get('addr_info', []) if a.get('scope') == 'global'})
        if not subnets:
            continue
        bssid = None
        if kind == 'wifi':
            wifi = run(['nmcli', '-t', '--escape', 'no', '-f', 'IN-USE,BSSID',
                        'device', 'wifi', 'list', '--rescan', 'no', 'ifname', interface])
            active = [line[2:].lower() for line in wifi.splitlines() if line.startswith('*:')]
            if len(active) != 1 or not MAC.fullmatch(active[0]):
                raise ValueError('Point d’accès Wi-Fi non identifiable ; aucune découverte autorisée.')
            bssid = active[0]
        gateway = fields.get('IP4.GATEWAY', '')
        neighbors = json.loads(run(['ip', '-j', '-4', 'neigh', 'show', 'dev', interface]))
        gateway_macs = {n['lladdr'].lower() for n in neighbors
                        if n.get('dst') == gateway and MAC.fullmatch(n.get('lladdr', ''))
                        and not set(n.get('state', [])) & {'FAILED', 'INCOMPLETE'}}
        gateway_mac = next(iter(gateway_macs)) if len(gateway_macs) == 1 else None
        if kind == 'ethernet' and not gateway_mac:
            raise ValueError('Passerelle Ethernet non identifiable dans le cache local ; aucune découverte.')
        identity = {'uuid': uuid, 'interface': interface, 'type': kind,
                    'gateway': gateway, 'gateway_mac': gateway_mac, 'subnets': subnets, 'bssid': bssid}
        result.append({'id': digest(identity), 'identity': identity,
                       'name': fields.get('GENERAL.CONNECTION', uuid),
                       'activation': fields.get('GENERAL.CON-PATH', '')})
    return result


def scope_for(connection, value):
    scope = ipaddress.ip_network(value, strict=True)
    if scope.version != 4 or scope.num_addresses > 4096 or scope.is_loopback or scope.is_multicast or scope.is_unspecified:
        raise ValueError('CIDR IPv4 directement connecté requis, maximum 4096 adresses.')
    if not any(scope.subnet_of(ipaddress.IPv4Network(net)) for net in connection['identity']['subnets']):
        raise ValueError('Le périmètre doit être inclus dans un sous-réseau directement connecté.')
    return str(scope)


class Store:
    def __init__(self, directory=DEFAULT_STATE):
        self.directory = Path(directory).expanduser().absolute()
        for parent in (self.directory, *self.directory.parents):
            if (parent.is_symlink() or (parent/'.git').is_file()
                    or (parent/'.git/HEAD').exists() or parent.name == '.git'):
                raise ValueError('État privé requis hors Git et sans lien symbolique.')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.path = self.directory/'inventory.json'
        self.stop_path = self.directory/'stop'

    def open_private(self, name):
        fd = os.open(self.directory/name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        return os.fdopen(fd, 'r+')

    @contextmanager
    def transaction(self):
        with self.open_private('state.lock') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.path.is_symlink():
                raise ValueError('Lien symbolique refusé pour l’inventaire.')
            data = json.loads(self.path.read_text()) if self.path.exists() else {'version': 1, 'networks': {}}
            if self.path.exists():
                self.path.chmod(0o600)
            yield data
            fd, name = tempfile.mkstemp(dir=self.directory, prefix='inventory-')
            try:
                with os.fdopen(fd, 'w') as stream:
                    json.dump(data, stream, ensure_ascii=False, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, self.path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)

    def read(self):
        with self.transaction() as data:
            return data

    def remember(self, connection):
        with self.transaction() as data:
            fresh = connection['id'] not in data['networks']
            if fresh:
                data['networks'][connection['id']] = {
                    **connection, 'decision': 'pending', 'scope': None,
                    'first_seen': now(), 'devices': {}, 'previous': [], 'scans': 0}
            data['networks'][connection['id']]['last_seen'] = now()
        return fresh

    def decide(self, connection, scope=None):
        with self.transaction() as data:
            row = data['networks'][connection['id']]
            row['decision'] = 'approved' if scope else 'denied'
            row['scope'] = scope_for(connection, scope) if scope else None
            row['decision_at'] = now()

    def revoke(self, network):
        with self.transaction() as data:
            row = data['networks'][network]
            row.update(decision='revoked', scope=None, decision_at=now())

    def stop(self):
        with self.open_private('stop'):
            pass

    def record(self, connection, scope, observations, date=None):
        date = date or now()
        new = []
        with self.transaction() as data:
            network = data['networks'][connection['id']]
            if network['decision'] != 'approved' or network['scope'] != scope:
                raise ValueError('Autorisation retirée ou modifiée ; résultat non enregistré.')
            current = set()
            for observation in observations:
                ip = str(ipaddress.IPv4Address(observation['ip']))
                if ipaddress.IPv4Address(ip) not in ipaddress.IPv4Network(scope):
                    raise ValueError('Observation hors périmètre.')
                mac = observation.get('mac')
                if mac is not None:
                    mac = mac.lower()
                    if not MAC.fullmatch(mac):
                        raise ValueError('MAC invalide.')
                # Une IP seule, ou une MAC seule, ne prouve jamais une identité.
                key = digest([ip, mac])
                current.add(key)
                devices = network['devices']
                if key not in devices:
                    devices[key] = {'id': key, 'ip': ip, 'mac': mac, 'names': [], 'sources': {},
                                    'first_seen': date, 'status': 'a_valider',
                                    'identity_confidence': 'association IP/MAC observée, identité non prouvée' if mac else 'incertaine : IP seule'}
                    new.append(devices[key])
                device = devices[key]
                device['last_seen'] = date
                if observation.get('name') and observation['name'] not in device['names']:
                    device['names'].append(observation['name'])
                source = observation['source']
                evidence = device['sources'].setdefault(source, {'first_seen': date})
                evidence.update(last_seen=date, certainty=observation.get('certainty', 'incertaine'))
            comparison = {'new': [d['id'] for d in new],
                          'reappeared': sorted(current - set(network['previous']) - {d['id'] for d in new}),
                          'not_observed': sorted(set(network['previous']) - current)}
            network.update(previous=sorted(current), last_scan=date, last_comparison=comparison,
                           scans=network['scans'] + 1)
        return new


def device_inventory(data):
    """Vue des observations enregistrées, sans collecte réseau supplémentaire."""
    rows = []
    for network_id, network in sorted(data['networks'].items()):
        for device in network['devices'].values():
            rows.append({**device, 'network_id': network_id, 'network_name': network['name'],
                         'observed_last_scan': device['id'] in network['previous']})
    return sorted(rows, key=lambda row: (row['network_id'],
                  int(ipaddress.IPv4Address(row['ip'])), row['mac'] or ''))


def parse_hosts(xml, scope):
    root = ET.fromstring(xml)
    finished = root.find('runstats/finished')
    if finished is None or finished.get('exit') != 'success':
        raise ValueError('Découverte Nmap incomplète ; inventaire précédent conservé.')
    result = []
    for host in root.findall('host'):
        status = host.find('status')
        if status is None or status.get('state') != 'up':
            continue
        addresses = {a.get('addrtype'): a.get('addr') for a in host.findall('address')}
        ip = addresses.get('ipv4')
        if not ip or ipaddress.IPv4Address(ip) not in ipaddress.IPv4Network(scope):
            raise ValueError('Résultat Nmap hors périmètre.')
        names = host.findall('hostnames/hostname')
        result.append({'ip': ip, 'mac': addresses.get('mac'),
                       'name': names[0].get('name') if names else None,
                       'source': 'nmap -sn -n', 'certainty': status.get('reason', 'réponse de découverte')})
    return result


class Guard:
    """Annule la collecte à l’arrêt, à la révocation ou au changement de connexion."""
    def __init__(self, store, connection, scope, connected=connections):
        self.store, self.connection, self.scope, self.connected = store, connection, scope, connected
        self.cancelled = False
        self.checked = 0

    def is_set(self):
        if self.cancelled:
            return True
        if time.monotonic() - self.checked < .5:
            return False
        self.checked = time.monotonic()
        try:
            row = self.store.read()['networks'].get(self.connection['id'], {})
            self.cancelled = (self.store.stop_path.exists() or row.get('decision') != 'approved'
                              or row.get('scope') != self.scope
                              or self.connection['id'] not in {c['id'] for c in self.connected()})
        except (OSError, ValueError):
            self.cancelled = True
        return self.cancelled

    def set(self):
        self.cancelled = True
        self.store.stop()


def discover(connection, scope, cancel, execute=run):
    scope = scope_for(connection, scope)
    if cancel.is_set():
        raise ValueError('Découverte annulée.')
    interface = connection['identity']['interface']
    # Aucune option fournie par le modèle : pas de ports/services/scripts/OS/DNS.
    xml = execute(['nmap', '-sn', '-n', '-PR', '--send-eth', '--privileged', '-e', interface, '--max-retries', '1',
                   '--max-rate', '32', '--host-timeout', '3s', '-oX', '-', scope],
                  cancel=cancel, timeout=180)
    observations = parse_hosts(xml, scope)
    # Le cache voisin n’est pas une preuve de présence actuelle : le conserver comme tel.
    try:
        neighbors = json.loads(execute(['ip', '-j', '-4', 'neigh', 'show', 'dev', interface], cancel=cancel))
        for item in neighbors:
            ip = ipaddress.IPv4Address(item['dst'])
            if ip in ipaddress.IPv4Network(scope) and item.get('lladdr') and MAC.fullmatch(item['lladdr']):
                observations.append({'ip': str(ip), 'mac': item['lladdr'], 'name': None,
                                     'source': 'ip neigh (cache local)',
                                     'certainty': 'incertaine : cache ' + ','.join(item.get('state', []))})
    except (OSError, ValueError, KeyError):
        pass
    # Noms déjà présents localement seulement ; aucune résolution DNS externe.
    try:
        with Path('/etc/hosts').open() as hosts:
            names = {}
            for line in hosts.read(200000).splitlines():
                parts = line.split('#', 1)[0].split()
                if len(parts) >= 2:
                    names.setdefault(parts[0], []).extend(parts[1:])
        named = []
        for observation in observations:
            for name in names.get(observation['ip'], []):
                named.append({**observation, 'name': name, 'source': '/etc/hosts local',
                              'certainty': 'incertaine : nom déclaré localement'})
        observations.extend(named)
    except OSError:
        pass
    if cancel.is_set():
        raise ValueError('Connexion ou autorisation modifiée ; collecte abandonnée.')
    return observations


def approve(store, connection, ui, scope=None):
    ui.show(f"Connexion : {connection['name']} — {connection['id']}\n" + json.dumps(connection['identity'], ensure_ascii=False))
    try:
        scope = scope_for(connection, scope or ui.read('Périmètre CIDR autorisé (vide = refus) > ').strip())
        allowed = ui.confirm(f'Autoriser uniquement la découverte d’hôtes sur {scope}, interface '
                             f"{connection['identity']['interface']} ? Aucun audit, fichier distant ou secret collecté.")
    except (EOFError, KeyboardInterrupt):
        store.decide(connection)
        raise
    except ValueError as error:
        ui.show('Autorisation non enregistrée : ' + str(error))
        allowed = False
    store.decide(connection, scope if allowed else None)
    ui.show('Inventaire autorisé pour ce périmètre.' if allowed else 'Inventaire refusé ; aucune découverte autorisée.')


class NetworkUI(UI):
    """Saisie terminal interruptible aussi par la commande arreter."""
    def __init__(self, store):
        super().__init__()
        self.store = store

    def read(self, prompt=''):
        if not sys.stdin.isatty():
            return super().read(prompt)
        from .app import safe
        try:
            print(('\033[' + self.WHITE + 'm' if self.color else '') + safe(prompt), end='', flush=True)
            with selectors.DefaultSelector() as selector:
                selector.register(sys.stdin, selectors.EVENT_READ)
                while not self.store.stop_path.exists():
                    if selector.select(.25):
                        line = sys.stdin.readline()
                        if not line:
                            raise EOFError()
                        return line.rstrip('\n')
            raise KeyboardInterrupt()
        finally:
            self.reset()


def cycle(store, ui, connected=None, scan=None, interactive=None):
    connected = connected or connections
    scan = scan or discover
    healthy = True
    interactive = sys.stdin.isatty() if interactive is None else interactive
    for connection in connected():
        if store.stop_path.exists():
            break
        fresh = store.remember(connection)
        if fresh:
            if interactive:
                approve(store, connection, ui)
            else:
                ui.show(f"Connexion inconnue {connection['id']} : en attente, aucune découverte. Utiliser approuver.")
        row = store.read()['networks'][connection['id']]
        if row['decision'] != 'approved':
            continue
        scope = scope_for(connection, row['scope'])
        guard = Guard(store, connection, scope, connected)
        try:
            observations = scan(connection, scope, guard)
            if guard.is_set():
                continue
            new = store.record(connection, scope, observations)
            ui.show(f"Inventaire {connection['name']} : {len(observations)} observation(s), {len(new)} nouveau(x) candidat(s).")
            for device in new:
                ui.show(f"NOUVEL APPAREIL À VALIDER : ID {device['id']} ; réseau {connection['id']} ; "
                        f"{device['ip']} — {device['mac'] or 'MAC inconnue'} ; {device['identity_confidence']}")
        except (OSError, ValueError, ET.ParseError) as error:
            healthy = False
            ui.show('Découverte indisponible ; inventaire précédent conservé : ' + str(error))
    return healthy


def events(store, interval):
    """Événements NM et rafraîchissement périodique, sans service installé."""
    child = subprocess.Popen(['nmcli', 'monitor'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             start_new_session=True, env={**os.environ, 'LC_ALL': 'C'})
    try:
        os.set_blocking(child.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            yield
            deadline = time.monotonic() + interval
            while not store.stop_path.exists():
                if child.poll() is not None:
                    raise OSError('Moniteur NetworkManager arrêté ; veille interrompue.')
                ready = selector.select(min(.25, max(0, deadline - time.monotonic())))
                if ready:
                    os.read(child.stdout.fileno(), 65536)
                if ready or time.monotonic() >= deadline:
                    yield
                    deadline = time.monotonic() + interval
    finally:
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        child.stdout.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='PRÉVOST — inventaire des réseaux explicitement approuvés')
    parser.add_argument('mode', choices=['connexions', 'liste', 'appareils', 'approuver', 'retirer', 'une-fois', 'veille', 'arreter'])
    parser.add_argument('--network', help='Identifiant exact affiché par connexions ou liste')
    parser.add_argument('--scope', help='Un CIDR IPv4 directement connecté, maximum 4096 adresses')
    parser.add_argument('--interval', type=float, default=60)
    parser.add_argument('--state-dir', default=str(DEFAULT_STATE))
    args = parser.parse_args(argv)
    ui = UI()
    try:
        if not math.isfinite(args.interval) or args.interval < 1:
            raise ValueError('Intervalle fini >= 1 seconde requis.')
        if args.mode == 'connexions':
            ui.raw(json.dumps(connections(), ensure_ascii=False, indent=2))
            return 0
        store = Store(args.state_dir)
        ui = NetworkUI(store)
        if args.mode == 'liste':
            ui.raw(json.dumps(store.read(), ensure_ascii=False, indent=2))
        elif args.mode == 'appareils':
            ui.raw(json.dumps(device_inventory(store.read()), ensure_ascii=False, indent=2))
        elif args.mode == 'arreter':
            store.stop()
            ui.show('Arrêt demandé ; la collecte en cours sera annulée et la veille terminée.')
        elif args.mode == 'retirer':
            if not args.network:
                raise ValueError('--network requis.')
            store.revoke(args.network)
            ui.show('Autorisation retirée ; observations conservées, aucune nouvelle découverte autorisée.')
        elif args.mode == 'approuver':
            current = {c['id']: c for c in connections()}
            if args.network not in current:
                raise ValueError('--network doit identifier une connexion actuellement visible.')
            connection = current[args.network]
            store.remember(connection)
            approve(store, connection, ui, args.scope)
        else:
            with store.open_private('watch.lock') as lease:
                try:
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError('Une veille utilise déjà cet inventaire.')
                store.stop_path.unlink(missing_ok=True)
                if args.mode == 'une-fois':
                    if not cycle(store, ui):
                        return 1
                else:
                    ui.show('Veille réseau active au premier plan. Ctrl+C ou commande arreter pour terminer.')
                    with closing(events(store, args.interval)) as updates:
                        for _ in updates:
                            cycle(store, ui)
                    ui.show('Veille réseau arrêtée.')
        return 0
    except KeyboardInterrupt:
        ui.show('Veille réseau interrompue ; aucune nouvelle découverte.')
        return 130
    except (OSError, ValueError, KeyError) as error:
        ui.show('Inventaire réseau indisponible : ' + str(error))
        return 1
    finally:
        ui.reset()


if __name__ == '__main__':
    raise SystemExit(main())
