"""Sondes à liste de commandes fermée ; aucune commande d'écriture téléphone."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PROPERTIES = ('ro.product.manufacturer', 'ro.product.model', 'ro.product.device',
              'ro.product.board', 'ro.hardware', 'ro.build.version.release',
              'ro.build.version.sdk', 'ro.build.version.security_patch',
              'ro.build.fingerprint', 'ro.bootmode', 'ro.boot.verifiedbootstate',
              'ro.boot.flash.locked', 'ro.frp.pst')
SETTINGS = (('global', 'device_provisioned'), ('secure', 'user_setup_complete'),
            ('global', 'secure_frp_mode'), ('secure', 'secure_frp_mode'))


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class Runner:
    def __call__(self, args):
        if not shutil.which(args[0]):
            return {'status': 'outil_absent', 'output': '', 'code': None}
        try:
            p = subprocess.run(args, capture_output=True, text=True,
                               errors='replace', timeout=12, check=False)
            # stderr non conservé : peut contenir des informations étrangères au diagnostic.
            status = 'ok' if p.returncode == 0 else 'erreur_commande'
            if p.returncode and args[0] == 'adb':
                if 'Operation not permitted' in p.stderr or 'Permission denied' in p.stderr:
                    status = 'adb_permission_refusee'
                elif 'cannot connect to daemon' in p.stderr or 'failed to start daemon' in p.stderr:
                    status = 'serveur_adb_indisponible'
            return {'status': status, 'output': p.stdout[:262144], 'code': p.returncode}
        except subprocess.TimeoutExpired:
            return {'status': 'delai_depasse', 'output': '', 'code': None}
        except OSError as exc:
            return {'status': type(exc).__name__, 'output': '', 'code': None}


def read(path):
    try:
        return Path(path).read_text(errors='replace').strip()[:512]
    except OSError:
        return None


def parse_adb(output):
    result = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0] == 'List' or line.startswith('*'):
            continue
        if parts[1] not in ('device', 'recovery', 'sideload', 'offline', 'unauthorized', 'no'):
            continue
        attrs = dict(p.split(':', 1) for p in parts[2:] if ':' in p)
        result.append({'serial': parts[0], 'state': 'no_permissions' if parts[1] == 'no' else parts[1],
                       'model_announced': attrs.get('model'), 'usb': attrs.get('usb')})
    return result


def interpret(properties, settings):
    facts, clues = [], []
    for key in ('device_provisioned', 'user_setup_complete'):
        item = settings.get(key, {})
        if item.get('status') == 'ok' and item.get('value') in ('0', '1'):
            facts.append({'source': key, 'value': item['value'],
                          'meaning': 'configuration déclarée terminée' if item['value'] == '1'
                          else 'configuration déclarée non terminée'})
    for namespace in ('global', 'secure'):
        frp = settings.get(namespace + '.secure_frp_mode', {})
        if frp.get('status') == 'ok' and frp.get('value') in ('0', '1'):
            facts.append({'source': namespace + '.secure_frp_mode', 'value': frp['value'],
                          'meaning': 'valeur du drapeau système observée'})
            if frp['value'] == '1':
                clues.append(namespace + '.secure_frp_mode vaut 1 : indice de mode FRP actif.')
    pst = properties.get('ro.frp.pst', {})
    if pst.get('status') == 'ok' and pst.get('value'):
        clues.append('ro.frp.pst est défini : support FRP annoncé, sans lecture de partition.')
    return {'facts': facts, 'clues': clues,
            'conclusion': 'Protection FRP au prochain démarrage ou après réinitialisation : indéterminée.',
            'limits': 'Aucun compte collecté. Drapeau absent ou à 0 ne prouve pas une absence de FRP. '
                      'Les indicateurs de configuration ne constituent pas un historique de première activation.'}


class Diagnostics:
    def __init__(self, runner=None, sysfs='/sys/bus/usb/devices'):
        self.runner = runner or Runner()
        self.sysfs = Path(sysfs)
        self.errors = []

    def command(self, args):
        result = self.runner(args)
        if result['status'] != 'ok':
            self.errors.append({'time': now(), 'operation': args, 'status': result['status'],
                                'code': result.get('code')})
        return result

    def usb(self):
        devices = []
        try:
            entries = sorted(self.sysfs.iterdir())
        except OSError as exc:
            self.errors.append({'time': now(), 'operation': 'sysfs_usb', 'status': type(exc).__name__})
            return {'status': 'inaccessible', 'devices': []}
        for path in entries:
            if read(path / 'idVendor') != '04e8':
                continue
            interfaces = []
            for interface in sorted(path.glob(path.name + ':*')):
                interfaces.append({k: read(interface / k) for k in
                                   ('bInterfaceClass', 'bInterfaceSubClass', 'bInterfaceProtocol')})
            # Sur certains noyaux les interfaces sont uniquement exposées comme entrées voisines.
            for interface in entries:
                if interface.name.startswith(path.name + ':'):
                    item = {k: read(interface / k) for k in
                            ('bInterfaceClass', 'bInterfaceSubClass', 'bInterfaceProtocol')}
                    if item not in interfaces:
                        interfaces.append(item)
            devices.append({'port': path.name, 'vendor_id': '04e8',
                            'product_id': read(path / 'idProduct'),
                            'manufacturer': read(path / 'manufacturer'), 'product': read(path / 'product'),
                            'serial': read(path / 'serial'),
                            'busnum': read(path / 'busnum'), 'devnum': read(path / 'devnum'),
                            'interfaces': interfaces})
        return {'status': 'ok', 'devices': devices,
                'limits': 'Le VID Samsung identifie le fabricant USB, pas le modèle exact ni le mode Recovery.'}

    def mtp(self, usb):
        response = self.command(['gio', 'mount', '-li'])
        uris = sorted(set(re.findall(r'mtp://[^\s/]+/?', response['output']))) if response['status'] == 'ok' else []
        mounts = []
        for uri in uris:
            authority = unquote(uri.split('://', 1)[1].rstrip('/'))
            matched = []
            bus_address = re.fullmatch(r'\[usb:(\d+),(\d+)\]', authority)
            for d in usb['devices']:
                serial_match = d.get('serial') and (authority == d['serial'] or
                                                       authority.endswith('_' + d['serial']))
                address_match = bool(bus_address and d.get('busnum') and d.get('devnum') and
                                     d['busnum'].isdigit() and d['devnum'].isdigit() and
                                     int(bus_address[1]) == int(d['busnum']) and
                                     int(bus_address[2]) == int(d['devnum']))
                if serial_match or address_match:
                    matched.append(d['port'])
            # Ne conserve ni autres disques ni contenu utilisateur.
            mounts.append({'uri': uri, 'samsung_ports': matched,
                           'association': ('adresse_usb' if bus_address else 'serial_usb') if len(matched) == 1 else 'non_etablie'})
        image_ports = [d['port'] for d in usb['devices'] if any(
            i.get('bInterfaceClass') == '06' for i in d['interfaces'])]
        return {'status': response['status'], 'mounts': mounts,
                'image_interface_clues': image_ports,
                'limits': 'Une interface image peut être PTP ou MTP. Un montage ne prouve pas '
                          'que le stockage est déverrouillé. Aucun fichier du téléphone parcouru.'}

    def adb(self):
        response = self.command(['adb', 'devices', '-l'])
        return {'status': response['status'],
                'devices': parse_adb(response['output']) if response['status'] == 'ok' else []}

    def value(self, serial, *args):
        result = self.command(['adb', '-s', serial, 'shell', *args])
        value = result['output'].strip()
        if result['status'] != 'ok':
            return {'status': result['status'], 'value': None}
        if not value or value == 'null':
            return {'status': 'non_disponible', 'value': None}
        if '\n' in value or any(s in value.lower() for s in
                ('permission denial', 'permission denied', 'securityexception', 'not found', 'error:')):
            return {'status': 'refuse_ou_invalide', 'value': None}
        return {'status': 'ok', 'value': value[:512]}

    def collect(self, usb, adb, serial=None):
        candidates = []
        for d in adb['devices']:
            associated = any((u.get('serial') and d['serial'] == u['serial']) or
                             (d.get('usb') and d['usb'] == u['port']) for u in usb['devices'])
            if associated or (d.get('model_announced') or '').upper() == 'SM_G990W2':
                candidates.append(d)
        if serial:
            candidates = [d for d in adb['devices'] if d['serial'] == serial]
        if len(candidates) != 1:
            return {'status': 'selection_ambigue' if len(candidates) > 1 else 'aucun_adb_samsung_associe',
                    'properties': {}, 'settings': {}, 'target': None}
        target = candidates[0]
        if target['state'] not in ('device', 'recovery'):
            return {'status': target['state'], 'properties': {}, 'settings': {}, 'target': target}
        properties = {k: self.value(target['serial'], 'getprop', k) for k in PROPERTIES[:2]}
        maker = properties['ro.product.manufacturer'].get('value')
        if (maker or '').lower() != 'samsung':
            return {'status': 'fabricant_non_confirme', 'properties': properties, 'settings': {}, 'target': target}
        properties.update({k: self.value(target['serial'], 'getprop', k) for k in PROPERTIES[2:]})
        settings = {(scope + '.' + key if key == 'secure_frp_mode' else key):
                    dict(self.value(target['serial'], 'settings', 'get', scope, key), source=scope + '.' + key)
                    for scope, key in SETTINGS} if target['state'] == 'device' else {}
        return {'status': 'ok', 'properties': properties, 'settings': settings, 'target': target}

    def run(self, serial=None):
        self.errors = []
        start = now()
        usb = self.usb()
        adb = self.adb()
        mtp = self.mtp(usb)
        android = self.collect(usb, adb, serial)
        props = android['properties']
        model = props.get('ro.product.model', {}).get('value')
        manufacturer = props.get('ro.product.manufacturer', {}).get('value')
        exact = bool(model == 'SM-G990W2' and (manufacturer or '').lower() == 'samsung')
        identification = {'expected_model': 'SM-G990W2', 'observed_model': model,
                          'confidence': 'elevee_proprietes_android' if exact else
                          ('modele_different_observe' if model else 'insuffisante'),
                          'match': exact if model else None,
                          'source': 'ADB ciblé : ro.product.model et ro.product.manufacturer' if model else
                          'USB ou annonces ADB uniquement',
                          'limits': 'Propriétés déclarées par le système ; aucune authentification matérielle cryptographique.'}
        recovery = {'confirmed_adb': [d['serial'] for d in adb['devices'] if d['state'] == 'recovery'],
                    'sideload': [d['serial'] for d in adb['devices'] if d['state'] == 'sideload'],
                    'scope': 'Transports ADB observés ; association Samsung à vérifier dans USB et android.target.',
                    'bootmode': props.get('ro.bootmode', {}),
                    'limits': 'Sans transport ADB ou propriété explicite, Recovery reste indéterminé. '
                              'Aucun redémarrage ni sideload exécuté.'}
        return {'version': '16.0.0', 'started_at': start, 'finished_at': now(),
                'usb': usb, 'mtp': mtp, 'adb': adb, 'android': android,
                'identification': identification, 'recovery': recovery,
                'frp_setup': interpret(props, android['settings']), 'errors': self.errors.copy()}


def technical_text(report):
    return 'PRÉVOST SAMSUNG RECOVERY V16\nDiagnostic en lecture seule\n' + json.dumps(
        report, ensure_ascii=False, indent=2) + '\n'


class Store:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.directory = self.root / 'rapports' / 'v16'

    def save(self, report):
        self.directory.mkdir(parents=True, exist_ok=True)
        # Nom créé exclusivement, sans écrasement d'un diagnostic existant.
        fd, name = tempfile.mkstemp(prefix='diagnostic-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-',
                                    suffix='.json', dir=self.directory)
        path = Path(name)
        with os.fdopen(fd, 'w') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        path.with_suffix('.txt').write_text(technical_text(report), encoding='utf-8')
        self.append('historique.jsonl', {'time': report['finished_at'], 'report': path.name,
                                       'usb': report['usb'], 'adb': report['adb'],
                                       'identification': report['identification']})
        for error in report['errors']:
            self.append('erreurs.jsonl', error)
        return path

    def append(self, name, record):
        with (self.directory / name).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    def history(self):
        path = self.directory / 'historique.jsonl'
        return path.read_text(encoding='utf-8') if path.exists() else 'Aucun diagnostic V16 enregistré.\n'

    def reports(self):
        return sorted(self.directory.glob('diagnostic-*.json'))

    def export(self):
        outdir = self.root / 'exports'
        outdir.mkdir(parents=True, exist_ok=True)
        name = 'prevost-samsung-v19-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.zip'
        out = outdir / name
        paths = []
        for folder in ('prevost_v16', 'outils', 'tests', 'rapports/v16', 'rapports/v17', 'rapports/v18', 'rapports/v19'):
            paths.extend(p for p in (self.root / folder).rglob('*')
                         if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts)
        paths.extend(p for p in (self.root / 'prevost-samsung', self.root / 'README-V16.md',
                                self.root / 'README-V17.md', self.root / 'README-V18.md',
                                self.root / 'README-V19.md') if p.is_file())
        manifest = {str(p.relative_to(self.root)): sha256(p) for p in sorted(paths)}
        with zipfile.ZipFile(out, 'x', zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(paths):
                archive.write(p, p.relative_to(self.root))
            archive.writestr('MANIFEST-SHA256.json', json.dumps(manifest, indent=2))
        with zipfile.ZipFile(out) as archive:
            if archive.testzip() is not None:
                raise OSError('Archive ZIP invalide')
            for member, digest in manifest.items():
                if hashlib.sha256(archive.read(member)).hexdigest() != digest:
                    raise OSError('Empreinte interne incorrecte : ' + member)
        checksum = out.with_suffix('.zip.sha256')
        checksum.write_text(sha256(out) + '  ' + out.name + '\n', encoding='utf-8')
        return out, checksum
