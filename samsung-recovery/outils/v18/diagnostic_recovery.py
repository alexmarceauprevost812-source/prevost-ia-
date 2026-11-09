"""V18 : collecte USB et métadonnées MTP, sans écriture téléphone."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from outils.v17 import diagnostic_environnement as env
from prevost_v16.core import Diagnostics, parse_adb, read

ROOT = Path(__file__).resolve().parents[2]


def usb_interfaces(sysfs=Path('/sys/bus/usb/devices')):
    result = Diagnostics(sysfs=sysfs).usb()
    for device in result['devices']:
        port = sysfs / device['port']
        interfaces = []
        for p in sorted(port.glob(device['port'] + ':*')):
            attrs = {k: read(p / k) for k in ('bInterfaceNumber', 'bInterfaceClass',
                     'bInterfaceSubClass', 'bInterfaceProtocol', 'interface')}
            triple = tuple(attrs[k] for k in ('bInterfaceClass', 'bInterfaceSubClass', 'bInterfaceProtocol'))
            attrs.update(path=str(p), driver=os.path.basename(os.path.realpath(p / 'driver'))
                         if (p / 'driver').exists() else None,
                         role='ADB annoncé' if triple == ('ff', '42', '01') else
                              'PTP/MTP candidat' if triple == ('06', '01', '01') else 'autre')
            interfaces.append(attrs)
        device['interfaces'] = interfaces
        try:
            node = Path('/dev/bus/usb') / f"{int(device['busnum']):03d}" / f"{int(device['devnum']):03d}"
            device['node'] = {'path': str(node), 'exists': node.exists(),
                              'read_access': os.access(node, os.R_OK), 'write_access': os.access(node, os.W_OK),
                              'limits': 'Permissions apparentes ; ouverture libusb non garantie dans le sandbox.'}
        except (ValueError, TypeError):
            device['node'] = {'status': 'numéro bus/appareil indisponible'}
    return result


def classify(usb, adb):
    states = parse_adb(adb.get('stdout', '')) if adb.get('returncode') == 0 else []
    # Ne jamais fusionner les états de plusieurs téléphones en une certitude.
    recovery = [s for s in states if s['state'] in ('recovery', 'sideload')]
    mtp = any(i['role'] == 'PTP/MTP candidat' for d in usb['devices'] for i in d['interfaces'])
    mode = 'indéterminé'
    if len(states) == 1 and recovery and len(usb['devices']) == 1:
        mode = 'Recovery annoncé par ADB ; association USB à confirmer'
    elif mtp:
        mode = 'Android probable (interface PTP/MTP) ; Recovery et Download non certifiés'
    return {'mode': mode, 'adb_states': states,
            'usb': 'Samsung énuméré' if usb['devices'] else 'aucun Samsung observé ; absence ou accès à vérifier',
            'adb': 'non sondé' if adb.get('status') == 'skipped' else
                   'échec hôte : voir stderr' if adb.get('returncode') != 0 else
                   'liste vide ; aucune preuve de refus RSA' if not states else 'voir états ADB individuels',
            'frp': 'indéterminé ; USB, MTP, liste ADB vide et HTTP 403 ne mesurent pas FRP',
            'limits': 'Le PID seul ne certifie aucun mode. Confirmer visuellement l’écran sans changer de mode. '
                      'ADB device indique un transport, pas une preuve de démarrage Android complet.'}


def collect(root=ROOT, sysfs=Path('/sys/bus/usb/devices'), runner=env.run_command, label='local',
            probe_mtp=True, probe_adb=True, timeout=15):
    before = env.inventory(root)
    usb = usb_interfaces(sysfs)
    def skipped(key, reason):
        return {'id': key, 'status': 'skipped', 'returncode': None, 'stdout': '', 'stderr': reason}
    probes = [runner('usb', ['lsusb', '-d', '04e8:'], timeout=timeout),
              runner('adb', ['adb', 'devices', '-l'], timeout=timeout) if probe_adb else
              skipped('adb', 'Sonde ADB désactivée par paramètre'),
              runner('mtp_mounts', ['gio', 'mount', '-li'], timeout=timeout)]
    # Session libmtp de lecture de métadonnées uniquement, sans parcours de fichiers.
    # Évite une prise concurrente lorsqu’un montage MTP est déjà annoncé.
    if probe_mtp and 'mtp://' not in probes[2]['stdout'] and len(usb['devices']) == 1:
        probes.append(runner('mtp_metadata', ['mtp-detect'], timeout=timeout))
    else:
        probes.append({'id': 'mtp_metadata', 'status': 'skipped', 'returncode': None,
                       'stdout': '', 'stderr': 'Sonde désactivée, montage MTP annoncé ou cible Samsung non unique ; pas de session concurrente.'})
    old = []
    for p in sorted((root / 'rapports/v17').glob('environnement-*.json')):
        try:
            data = json.loads(p.read_text())
            old.append({'path': str(p.relative_to(root)), 'sha256': env.digest(p),
                        'started_at': data.get('started_at'), 'label': data.get('label'),
                        'tests': data.get('tests', [])})
        except (OSError, ValueError) as exc:
            old.append({'path': str(p), 'error': str(exc)})
    return {'version': 18, 'started_at': env.utc(), 'label': label,
            'parameters': {'probe_mtp': probe_mtp, 'probe_adb': probe_adb, 'timeout': timeout},
            'label_is_user_declared': True, 'script_sha256': env.digest(Path(__file__)),
            'usb': usb, 'probes': probes, 'v17_evidence': old,
            'findings': classify(usb, probes[1]),
            'mtp_limits': 'Interface annoncée ≠ stockage accessible. Échec libmtp : outil absent, '
                          'permissions, verrouillage ou session occupée possibles ; pas une preuve FRP. '
                          'Aucun fichier utilisateur listé ou copié.',
            'preservation': env.verify_inventory(root, before)}


def save(report, root=ROOT):
    directory = root / 'rapports/v18'
    directory.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='recovery-' + report['label'] + '-', suffix='.json', dir=directory)
    path = Path(name)
    with os.fdopen(fd, 'w') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    with path.with_suffix('.txt').open('x') as stream:
        stream.write('PRÉVOST V18 — DIAGNOSTIC RECOVERY\n' + json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    with path.with_suffix('.json.sha256').open('x') as stream:
        stream.write(env.digest(path) + '  ' + path.name + '\n')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', choices=('codex', 'ubuntu', 'local'), default='local')
    parser.add_argument('--sans-mtp', action='store_true', help='Omettre la session mtp-detect ; conserver les descripteurs et montages')
    parser.add_argument('--sans-adb', action='store_true', help='Omettre ADB et son éventuel démarrage de serveur local')
    parser.add_argument('--delai', type=int, choices=range(1, 61), default=15, metavar='1..60', help='Délai maximal de chaque sonde en secondes')
    args = parser.parse_args(argv)
    report = collect(label=args.label, probe_mtp=not args.sans_mtp,
                     probe_adb=not args.sans_adb, timeout=args.delai)
    print(json.dumps(report['findings'], ensure_ascii=False, indent=2))
    print(save(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
